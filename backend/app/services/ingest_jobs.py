"""Background jobs for order-email uploads.

With real models, 18 emails can take 30-60 s, which risks browser and proxy timeouts if the
request waits. So the upload request only reads the files into memory and starts a job; the
page then polls GET /api/ingest/jobs/{id} for progress and the final summary.
"""

import logging
import threading
import uuid
from dataclasses import asdict, dataclass, field
from typing import Any, Optional

from sqlmodel import Session

from app.db import engine
from app.schemas import FileIngestResult
from app.services import email_extract, gmail

log = logging.getLogger("stripefit.ingest")

MAX_KEPT_JOBS = 10  # finished jobs are kept briefly so the page can read the result


@dataclass
class EmailJob:
    id: str
    running: bool = True
    total: int = 0
    done: int = 0
    error: Optional[str] = None
    results: list[dict[str, Any]] = field(default_factory=list)
    summary: Optional[dict[str, Any]] = None


_jobs: dict[str, EmailJob] = {}
_lock = threading.Lock()


class ImportBusy(Exception):
    """Another import is running; reconciling two at once could create duplicate items."""


def any_running() -> bool:
    return any(job.running for job in _jobs.values())


def get(job_id: str) -> Optional[dict[str, Any]]:
    job = _jobs.get(job_id)
    return asdict(job) if job else None


def start(uploads: list[tuple[str, bytes]]) -> dict[str, Any]:
    """Start processing uploaded files in the background. Raises ImportBusy if an import is running."""
    with _lock:
        if any_running() or gmail.job_status()["running"]:
            raise ImportBusy()
        job = EmailJob(id=uuid.uuid4().hex, total=len(uploads))
        _jobs[job.id] = job
        for old_id in list(_jobs)[:-MAX_KEPT_JOBS]:
            _jobs.pop(old_id, None)
    threading.Thread(target=_run, args=(job, uploads), daemon=True).start()
    return asdict(job)


def _run(job: EmailJob, uploads: list[tuple[str, bytes]]) -> None:
    results: list[FileIngestResult] = []
    try:
        docs = []
        for filename, data in uploads:
            try:
                docs.append(email_extract.read_upload(filename, data))
            except email_extract.UnsupportedFile as exc:
                results.append(FileIngestResult(filename=filename, notes=[f"unsupported file: {exc}"]))
                job.done += 1
        with Session(engine) as session:
            for doc in sorted(docs, key=email_extract.sort_key):  # oldest first: orders before refunds
                results.append(email_extract.ingest_doc(session, doc))
                job.done += 1
                job.results = [r.model_dump() for r in results]
        job.summary = email_extract.summarise(results).model_dump()
    except Exception:  # noqa: BLE001 - background thread: never die silently
        log.exception("Email import failed")
        job.error = "The import stopped unexpectedly. Items found so far are in Review. Try again for the rest."
        job.summary = email_extract.summarise(results).model_dump() if results else None
    finally:
        job.running = False
