"""Adding clothes: photos (free) and order emails / screenshots (Pro)."""

from fastapi import APIRouter, Depends, File, UploadFile
from sqlmodel import Session

from app.config import BACKEND_DIR, settings
from app.db import get_session
from app.errors import api_error
from app.schemas import IngestSummary, PhotoResult
from app.services import email_extract, images, labelling
from app.services.limits import UPGRADE_NEXT_STEP, confirmed_count, is_premium, require_pro
from app.services.serialize import item_out

router = APIRouter(prefix="/api/ingest", tags=["ingest"])

MAX_FILES_PER_UPLOAD = 20
SAMPLES_DIR = BACKEND_DIR / "samples" / "emails"


@router.post("/photo", response_model=list[PhotoResult])
def ingest_photos(files: list[UploadFile] = File(...), session: Session = Depends(get_session)) -> list[PhotoResult]:
    """Photos -> labelled items in the review queue. Sync def: FastAPI runs it in a worker thread."""
    if not is_premium(session) and confirmed_count(session) >= settings.FREE_ITEM_LIMIT:
        raise api_error(402, "upgrade_required",
                        f"Your wardrobe is full on the free plan ({settings.FREE_ITEM_LIMIT} items).", UPGRADE_NEXT_STEP)
    if len(files) > MAX_FILES_PER_UPLOAD:
        raise api_error(422, "too_many_files", f"Upload up to {MAX_FILES_PER_UPLOAD} photos at a time.")

    results: list[PhotoResult] = []
    for upload in files:
        name = upload.filename or "photo"
        try:
            img = images.open_photo(upload.file.read(images.MAX_PHOTO_BYTES + 1))
            item = labelling.ingest_photo(session, img)
        except images.ImageRejected as exc:
            results.append(PhotoResult(filename=name, ok=False, message=str(exc)))
            continue
        except labelling.NotClothing as exc:
            results.append(PhotoResult(filename=name, ok=False, message=f"Not added: {exc}"))
            continue
        message = "Labelled. Check it in Review." if item.confidence else labelling.AI_DOWN_NOTE
        results.append(PhotoResult(filename=name, ok=True, item=item_out(item), message=message))
    return results


@router.post("/email", response_model=IngestSummary)
def ingest_email(files: list[UploadFile] = File(...), session: Session = Depends(get_session)) -> IngestSummary:
    """Order emails (.eml/.html/.txt/.pdf) or screenshots -> pending items, reconciled per order."""
    require_pro(session, "Importing order emails")
    if len(files) > MAX_FILES_PER_UPLOAD:
        raise api_error(422, "too_many_files", f"Upload up to {MAX_FILES_PER_UPLOAD} files at a time.")
    uploads = [(f.filename or "upload", f.file.read(email_extract.MAX_FILE_BYTES + 1)) for f in files]
    return email_extract.ingest_files(session, uploads)


@router.post("/samples", response_model=IngestSummary)
def ingest_samples(session: Session = Depends(get_session)) -> IngestSummary:
    """Demo helper: run the synthetic sample emails in backend/samples/emails through the same pipeline."""
    require_pro(session, "Importing order emails")
    allowed = email_extract.TEXT_TYPES | email_extract.IMAGE_TYPES
    uploads = [(p.name, p.read_bytes()) for p in sorted(SAMPLES_DIR.glob("*")) if p.suffix.lower() in allowed]
    if not uploads:
        raise api_error(404, "no_samples", "No sample emails found on the server.")
    return email_extract.ingest_files(session, uploads)
