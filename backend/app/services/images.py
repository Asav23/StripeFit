"""Image storage: uploaded photos, thumbnails, perceptual hashes and placeholder tiles."""

import io
import ipaddress
import socket
import textwrap
import uuid
from pathlib import Path
from urllib.parse import urlparse

import httpx
import imagehash
from PIL import Image, ImageDraw, ImageFont, ImageOps, UnidentifiedImageError

from app.config import UPLOAD_DIR

ALLOWED_PHOTO_FORMATS = {"JPEG", "PNG", "WEBP", "MPO"}  # MPO = some phone JPEGs
MAX_PHOTO_BYTES = 10 * 1024 * 1024
MAX_DOWNLOAD_BYTES = 5 * 1024 * 1024
ORIGINAL_MAX_PX = 2048
THUMB_PX = 480


class ImageRejected(Exception):
    """User-facing reason a file can't be used as a photo."""


# --------------------------------------------------------------------------- photos


def open_photo(data: bytes) -> Image.Image:
    if len(data) > MAX_PHOTO_BYTES:
        raise ImageRejected("That photo is over 10 MB. Try a smaller photo or a screenshot of it.")
    try:
        img = Image.open(io.BytesIO(data))
        img.load()
    except (UnidentifiedImageError, OSError):
        raise ImageRejected("That file isn't a photo we can read. Use a JPEG, PNG or WebP image.")
    if img.format not in ALLOWED_PHOTO_FORMATS:
        raise ImageRejected(f"{img.format or 'This'} images aren't supported. Use a JPEG, PNG or WebP image.")
    return ImageOps.exif_transpose(img).convert("RGB")


def save_photo(img: Image.Image) -> tuple[str, str, str]:
    """Save original + thumbnail. Returns (image_path, thumb_path, phash) relative to uploads/."""
    name = f"{uuid.uuid4().hex}.jpg"
    original = img.copy()
    original.thumbnail((ORIGINAL_MAX_PX, ORIGINAL_MAX_PX))
    original.save(UPLOAD_DIR / "originals" / name, format="JPEG", quality=88)
    thumb = img.copy()
    thumb.thumbnail((THUMB_PX, THUMB_PX))
    thumb.save(UPLOAD_DIR / "thumbs" / name, format="JPEG", quality=82)
    return f"originals/{name}", f"thumbs/{name}", str(imagehash.phash(img))


def hash_distance(a: str | None, b: str | None) -> int | None:
    if not a or not b:
        return None
    return imagehash.hex_to_hash(a) - imagehash.hex_to_hash(b)


def delete_files(*relative_paths: str | None) -> None:
    for rel in relative_paths:
        if rel:
            (UPLOAD_DIR / rel).unlink(missing_ok=True)


def url_for(relative_path: str | None) -> str | None:
    return f"/uploads/{relative_path}" if relative_path else None


# --------------------------------------------------------------------------- safe download (email image URLs)


def _is_public_host(host: str) -> bool:
    """Block SSRF: email content is untrusted, so never fetch localhost/private network URLs."""
    try:
        infos = socket.getaddrinfo(host, None)
    except socket.gaierror:
        return False
    for info in infos:
        ip = ipaddress.ip_address(info[4][0])
        if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved or ip.is_multicast:
            return False
    return True


def download_image(url: str) -> Image.Image | None:
    """Fetch a product image from an email (https only, public hosts, 5 MB cap). None on any failure."""
    parsed = urlparse(url)
    if parsed.scheme != "https" or not parsed.hostname or not _is_public_host(parsed.hostname):
        return None
    try:
        with httpx.Client(timeout=5.0, follow_redirects=False) as client:
            with client.stream("GET", url) as response:
                if response.status_code != 200 or not response.headers.get("content-type", "").startswith("image/"):
                    return None
                chunks, total = [], 0
                for chunk in response.iter_bytes():
                    total += len(chunk)
                    if total > MAX_DOWNLOAD_BYTES:
                        return None
                    chunks.append(chunk)
        return open_photo(b"".join(chunks))
    except (httpx.HTTPError, ImageRejected):
        return None


# --------------------------------------------------------------------------- placeholders

COLOUR_RGB: dict[str, tuple[int, int, int]] = {
    "black": (33, 33, 36), "white": (245, 245, 242), "grey": (140, 144, 150), "gray": (140, 144, 150),
    "charcoal": (70, 72, 78), "navy": (31, 45, 84), "blue": (52, 101, 180), "light blue": (150, 190, 230),
    "denim": (72, 102, 140), "red": (196, 48, 48), "burgundy": (110, 28, 44), "pink": (232, 150, 175),
    "purple": (110, 70, 150), "green": (60, 130, 80), "olive": (110, 112, 60), "khaki": (176, 160, 110),
    "yellow": (238, 200, 60), "mustard": (205, 160, 40), "orange": (228, 120, 40), "brown": (110, 72, 44),
    "tan": (196, 150, 100), "camel": (193, 154, 107), "beige": (220, 200, 170), "cream": (240, 230, 205),
    "ecru": (232, 224, 200), "stone": (200, 190, 170), "silver": (190, 192, 196), "gold": (210, 175, 70),
    "teal": (40, 128, 128),
}
_FALLBACK_RGB = (180, 186, 196)
_BACKGROUND = (241, 243, 247)

_SHAPES: dict[str, list[tuple[float, float]]] = {
    "top": [(.30, .18), (.42, .14), (.46, .19), (.54, .19), (.58, .14), (.70, .18), (.84, .32), (.76, .40),
            (.70, .35), (.70, .74), (.30, .74), (.30, .35), (.24, .40), (.16, .32)],
    "bottom": [(.34, .12), (.66, .12), (.71, .78), (.56, .78), (.50, .34), (.44, .78), (.29, .78)],
    "one_piece": [(.42, .12), (.46, .16), (.54, .16), (.58, .12), (.62, .16), (.60, .34), (.75, .78),
                  (.25, .78), (.40, .34), (.38, .16)],
    "outerwear": [(.30, .16), (.44, .12), (.50, .22), (.56, .12), (.70, .16), (.84, .40), (.86, .70),
                  (.76, .70), (.72, .44), (.72, .80), (.28, .80), (.28, .44), (.24, .70), (.14, .70), (.16, .40)],
    "shoes": [(.16, .50), (.20, .36), (.36, .36), (.44, .46), (.66, .52), (.82, .57), (.84, .66), (.16, .66)],
    "accessory": [(.46, .14), (.54, .14), (.56, .20), (.52, .24), (.60, .66), (.50, .76), (.40, .66),
                  (.48, .24), (.44, .20)],
    "shorts": [(.30, .22), (.70, .22), (.75, .62), (.54, .64), (.50, .44), (.46, .64), (.25, .62)],
}
_SHORTS_WORDS = ("short", "legging", "jogger", "bottoms", "tights")


def _font(size: int) -> ImageFont.ImageFont:
    for candidate in ("/System/Library/Fonts/Supplemental/Arial Bold.ttf", "/System/Library/Fonts/Helvetica.ttc",
                      "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"):
        if Path(candidate).exists():
            return ImageFont.truetype(candidate, size)
    return ImageFont.load_default(size=size)


def _rgb(colour: str) -> tuple[int, int, int]:
    colour = colour.lower()
    if colour in COLOUR_RGB:
        return COLOUR_RGB[colour]
    for name, rgb in COLOUR_RGB.items():  # "dark navy" -> navy
        if name in colour:
            return rgb
    return _FALLBACK_RGB


def make_placeholder(name: str, category: str, colours: list[str]) -> tuple[str, str]:
    """Draw a simple silhouette tile in the item's colour. Returns (image_path, thumb_path)."""
    size = 600
    img = Image.new("RGB", (size, size), _BACKGROUND)
    draw = ImageDraw.Draw(img)
    shape_key = category
    if category == "sportswear":
        shape_key = "shorts" if any(w in name.lower() for w in _SHORTS_WORDS) else "top"
    points = [(x * size, y * size) for x, y in _SHAPES.get(shape_key, _SHAPES["top"])]
    known = [c for c in colours if c != "unknown"]
    fill = _rgb(known[0]) if known else _FALLBACK_RGB
    outline = tuple(max(0, int(c * 0.6)) for c in fill)
    draw.polygon(points, fill=fill, outline=outline, width=4)
    if len(known) > 1:  # second colour as a stripe
        draw.rectangle([size * .30, size * .45, size * .70, size * .50], fill=_rgb(known[1]))
    if category == "sportswear":
        draw.rectangle([size * .30, size * .40, size * .70, size * .43], fill=(255, 255, 255))
    if category == "outerwear":
        draw.line([(size * .5, size * .22), (size * .5, size * .80)], fill=outline, width=4)
    if not known:
        draw.text((size * .5, size * .45), "?", fill=(255, 255, 255), font=_font(90), anchor="mm")

    lines = textwrap.wrap(name, width=26)[:2]
    font = _font(30)
    draw.rounded_rectangle([size * .06, size * .83, size * .94, size * .97], radius=18, fill=(255, 255, 255))
    for i, line in enumerate(lines):
        y = size * (.90 if len(lines) == 1 else .865 + i * .065)
        draw.text((size / 2, y), line, fill=(40, 44, 52), font=font, anchor="mm")

    file_name = f"{uuid.uuid4().hex}.png"
    img.save(UPLOAD_DIR / "placeholders" / file_name)
    thumb = img.copy()
    thumb.thumbnail((THUMB_PX, THUMB_PX))
    thumb.save(UPLOAD_DIR / "thumbs" / file_name)
    return f"placeholders/{file_name}", f"thumbs/{file_name}"
