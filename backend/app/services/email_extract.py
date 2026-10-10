"""Order emails -> pending wardrobe items.

Pipeline per file:  read -> pre-filter (no AI) -> redact -> extract (AI) -> reconcile -> log.
Email content is untrusted: personal data is removed before the model sees it, the text is
fenced and labelled as data, and only extracted item fields are stored (never the email body).
"""

import email
import io
import logging
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from email import policy
from email.utils import parseaddr, parsedate_to_datetime
from pathlib import Path
from typing import Optional

from bs4 import BeautifulSoup
from pypdf import PdfReader
from pypdf.errors import PdfReadError
from sqlmodel import Session

from app.ai import prompts
from app.ai.client import AIError, call_json, image_part
from app.config import settings
from app.models import IngestLog
from app.schemas import FileIngestResult, IngestSummary, OrderExtraction
from app.services import reconcile
from app.services.images import ImageRejected, open_photo
from app.services.redact import redact

log = logging.getLogger("stripefit.email")

MAX_FILE_BYTES = 10 * 1024 * 1024
MAX_TEXT_CHARS = 12_000  # plenty for an order email; keeps prompts small
MAX_PDF_PAGES = 5
TEXT_TYPES = {".eml", ".html", ".htm", ".txt", ".pdf"}
IMAGE_TYPES = {".png", ".jpg", ".jpeg", ".webp"}

# Shops we accept order emails from (sender domain must contain one of these as a label).
RETAILER_ALLOWLIST = [
    "zalando", "asos", "zara", "hm", "uniqlo", "nike", "adidas", "jdsports", "boohoo", "shein", "vinted", "depop",
    "ebay", "arnotts", "brownthomas", "primark", "very", "next", "schuh", "riverisland", "mango", "cos", "arket",
    "urbanoutfitters", "pullandbear", "bershka", "stradivarius", "massimodutti", "lululemon", "gymshark",
    "thenorthface", "patagonia",
]
RETAILER_DISPLAY = {
    "asos": "ASOS", "hm": "H&M", "jdsports": "JD Sports", "brownthomas": "Brown Thomas", "riverisland": "River Island",
    "cos": "COS", "urbanoutfitters": "Urban Outfitters", "pullandbear": "Pull&Bear", "massimodutti": "Massimo Dutti",
    "thenorthface": "The North Face", "ebay": "eBay", "shein": "SHEIN",
}

# Pre-filter: (reason, patterns). Subjects are checked against all; bodies only against the
# strongest phrases, because real order emails often carry marketing footers.
SKIP_PATTERNS: list[tuple[str, list[str]]] = [
    ("basket reminder", [r"left (something|items?|it) in your (basket|bag|cart)", r"still in your (basket|bag|cart)",
                         r"your (basket|bag|cart) (is waiting|misses you)", r"forget something", r"complete your purchase"]),
    ("price drop", [r"price drop", r"prices? (have |has )?(dropped|fallen)", r"now reduced", r"back in stock"]),
    ("wishlist", [r"wish ?list", r"saved items"]),
    ("newsletter", [r"newsletter", r"new arrivals", r"new in\b", r"\d+% off", r"\bsale (starts|ends|is on)"]),
    ("review request", [r"review your (order|purchase)", r"rate your", r"how did we do", r"write a review"]),
]
BODY_SKIP_REASONS = {"basket reminder", "price drop"}


class UnsupportedFile(Exception):
    pass


@dataclass
class EmailDoc:
    ref: str
    source: str  # "email" | "gmail"
    subject: Optional[str] = None
    sender_domain: Optional[str] = None
    date: Optional[datetime] = None
    text: Optional[str] = None
    image: Optional[bytes] = None  # screenshot
    retailer_hint: Optional[str] = None  # allowlist key from the sender domain (trusted)
    from_eml: bool = False


# --------------------------------------------------------------------------- read


def html_to_text(html: str) -> str:
    """HTML -> readable text, keeping <img> alt text and product image URLs."""
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style", "head", "noscript"]):
        tag.decompose()
    for img in soup.find_all("img"):
        alt = (img.get("alt") or "").strip()
        src = (img.get("src") or "").strip()
        width = str(img.get("width") or "")
        if width in ("0", "1") or not src.startswith("http"):  # tracking pixels, inline logos
            img.replace_with(f" [image: {alt}] " if alt else " ")
        else:
            img.replace_with(f" [image: {alt or 'product'} | {src}] ")
    text = soup.get_text(separator="\n")
    lines = [re.sub(r"[ \t\xa0]+", " ", line).strip() for line in text.splitlines()]
    return re.sub(r"\n{3,}", "\n\n", "\n".join(lines)).strip()


def matched_retailer(domain: Optional[str]) -> Optional[str]:
    if not domain:
        return None
    labels = domain.lower().split(".")
    return next((r for r in RETAILER_ALLOWLIST if r in labels), None)


def read_eml(data: bytes, ref: str, source: str) -> EmailDoc:
    msg = email.message_from_bytes(data, policy=policy.default)
    sender = parseaddr(str(msg.get("From", "")))[1]
    domain = sender.split("@")[-1].lower() if "@" in sender else None
    try:
        date = parsedate_to_datetime(str(msg["Date"])) if msg["Date"] else None
    except (TypeError, ValueError):
        date = None

    plain = msg.get_body(preferencelist=("plain",))
    html = msg.get_body(preferencelist=("html",))
    text = plain.get_content() if plain is not None else ""
    if html is not None:
        html_text = html_to_text(html.get_content())
        if not text.strip():
            text = html_text
        else:  # keep product image URLs, which usually only exist in the HTML part
            image_lines = re.findall(r"\[image: [^\]]*\|[^\]]*\]", html_text)
            text += "\n" + "\n".join(image_lines)
    return EmailDoc(
        ref=ref, source=source, subject=str(msg.get("Subject", "")) or None, sender_domain=domain, date=date,
        text=text, retailer_hint=matched_retailer(domain), from_eml=True,
    )


def read_upload(filename: str, data: bytes) -> EmailDoc:
    suffix = Path(filename).suffix.lower()
    if len(data) > MAX_FILE_BYTES:
        raise UnsupportedFile("File is over 10 MB.")
    if suffix == ".eml":
        return read_eml(data, filename, "email")
    if suffix in (".html", ".htm"):
        return EmailDoc(ref=filename, source="email", text=html_to_text(data.decode("utf-8", errors="replace")))
    if suffix == ".txt":
        return EmailDoc(ref=filename, source="email", text=data.decode("utf-8", errors="replace"))
    if suffix == ".pdf":
        try:
            reader = PdfReader(io.BytesIO(data))
            text = "\n".join((page.extract_text() or "") for page in reader.pages[:MAX_PDF_PAGES])
        except (PdfReadError, ValueError, OSError):
            raise UnsupportedFile("That PDF couldn't be read.")
        if not text.strip():
            raise UnsupportedFile("That PDF has no text in it (it's probably scanned). Upload a screenshot instead.")
        return EmailDoc(ref=filename, source="email", text=text)
    if suffix in IMAGE_TYPES:
        try:
            open_photo(data)
        except ImageRejected as exc:
            raise UnsupportedFile(str(exc))
        return EmailDoc(ref=filename, source="email", image=data)
    raise UnsupportedFile("Unsupported file type. Use .eml, .html, .txt, .pdf or a screenshot (.png/.jpg).")


# --------------------------------------------------------------------------- pre-filter (no AI)


def prefilter(doc: EmailDoc) -> Optional[str]:
    """Return a skip reason, or None if the email should go to the extractor."""
    subject = (doc.subject or "").lower()
    body = (doc.text or "")[:3000].lower()
    for reason, patterns in SKIP_PATTERNS:
        if any(re.search(p, subject) for p in patterns):
            return reason
        if reason in BODY_SKIP_REASONS and any(re.search(p, body) for p in patterns):
            return reason
    if doc.from_eml and not doc.retailer_hint:
        return "unknown sender"
    if doc.image is None and len((doc.text or "").strip()) < 40:
        return "empty email"
    return None


# --------------------------------------------------------------------------- extract (AI)


def extract(doc: EmailDoc) -> OrderExtraction:
    if doc.image is not None:
        model, fallbacks = settings.models_for("vision")
        messages = prompts.extract_image_messages(image_part(doc.image))
        return call_json("extract_order_image", model, fallbacks, messages, OrderExtraction,
                         mock_input=doc.ref, max_tokens=1500)
    model, fallbacks = settings.models_for("fast")
    safe_text = redact(doc.text or "")[:MAX_TEXT_CHARS]
    meta = {"subject": redact(doc.subject or ""), "sender_domain": doc.sender_domain}
    return call_json("extract_order", model, fallbacks, prompts.extract_messages(safe_text, meta), OrderExtraction,
                     mock_input=safe_text, max_tokens=1500)


def retailer_name(doc: EmailDoc, extraction: OrderExtraction) -> str:
    """Trust the sender domain over anything the model read from the email body."""
    key = doc.retailer_hint or reconcile._norm(extraction.retailer) or "unknown"
    if doc.retailer_hint:
        return RETAILER_DISPLAY.get(key, key.capitalize())
    return extraction.retailer or "Unknown shop"


# --------------------------------------------------------------------------- ingest


def ingest_doc(session: Session, doc: EmailDoc) -> FileIngestResult:
    result = FileIngestResult(filename=doc.ref)
    skip = prefilter(doc)
    if skip:
        result.notes.append(skip)
        _log(session, doc, None, 0, 1, [skip])
        return result

    try:
        extraction = extract(doc)
    except AIError as exc:
        result.notes.append("AI unavailable")
        _log(session, doc, None, 0, 0, [f"AI unavailable ({exc.kind})"])
        return result

    retailer = retailer_name(doc, extraction)
    order_id = (extraction.order_id or "").strip() or f"no-order-id:{doc.ref}"
    outcome = reconcile.apply(session, extraction, retailer, order_id, doc.source)

    result.email_type = extraction.email_type
    result.retailer = retailer
    result.order_id = extraction.order_id
    result.items_created = outcome.created
    result.items_updated = outcome.updated
    result.items_skipped = len(outcome.skipped)
    result.notes = outcome.skipped
    _log(session, doc, extraction.email_type, outcome.created + outcome.updated, len(outcome.skipped), outcome.skipped)
    return result


def _log(session: Session, doc: EmailDoc, email_type: Optional[str], found: int, skipped: int, notes: list[str]) -> None:
    session.add(IngestLog(source=doc.source, ref=doc.ref, email_type=email_type, items_found=found,
                          items_skipped=skipped, notes=notes))
    session.commit()


def summarise(results: list[FileIngestResult]) -> IngestSummary:
    created = sum(r.items_created for r in results)
    updated = sum(r.items_updated for r in results)
    skipped: dict[str, int] = {}
    for r in results:
        for note in r.notes:
            skipped[note] = skipped.get(note, 0) + 1
    parts = [f"{created} new item{'s' if created != 1 else ''} to review"]
    if updated:
        parts.append(f"{updated} updated")
    parts += [f"{count} skipped: {reason}" for reason, count in skipped.items()]
    return IngestSummary(files=results, items_created=created, items_updated=updated, skipped=skipped,
                         summary=" · ".join(parts))


def _sort_key(doc: EmailDoc) -> tuple[datetime, str]:
    # Oldest first, so an order is always processed before its dispatch/refund emails.
    return doc.date.astimezone(timezone.utc) if doc.date else datetime.max.replace(tzinfo=timezone.utc), doc.ref


def ingest_files(session: Session, uploads: list[tuple[str, bytes]]) -> IngestSummary:
    results: list[FileIngestResult] = []
    docs: list[EmailDoc] = []
    for filename, data in uploads:
        try:
            docs.append(read_upload(filename, data))
        except UnsupportedFile as exc:
            results.append(FileIngestResult(filename=filename, notes=[f"unsupported file: {exc}"]))
    for doc in sorted(docs, key=_sort_key):
        results.append(ingest_doc(session, doc))
    return summarise(results)
