"""Gmail import: read-only OAuth, order-like emails from allowlisted shops only.

We never list the whole inbox: the search query restricts to allowlisted senders and
order-ish subjects. Message bodies are processed in memory and never stored.
"""

import base64
import logging
import os
import threading
from dataclasses import asdict, dataclass, field
from typing import Any, Optional

from google.auth.exceptions import RefreshError
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from sqlmodel import Session, select

from app.config import GMAIL_TOKEN_PATH, settings
from app.db import engine
from app.models import IngestLog
from app.schemas import FileIngestResult
from app.services import email_extract

log = logging.getLogger("stripefit.gmail")

SCOPES = ["https://www.googleapis.com/auth/gmail.readonly"]
MAX_MESSAGES = 100
SUBJECT_TERMS = "order OR confirmation OR receipt OR shipped OR dispatched OR delivered OR refund OR return"

os.environ.setdefault("OAUTHLIB_RELAX_TOKEN_SCOPE", "1")  # Google may echo scopes in a different order

_pending_verifiers: dict[str, Optional[str]] = {}  # OAuth state -> PKCE code verifier


def build_query(months: int) -> str:
    senders = " OR ".join(email_extract.RETAILER_ALLOWLIST)
    return f"newer_than:{months}m subject:({SUBJECT_TERMS}) from:({senders})"


def _flow(state: Optional[str] = None) -> Flow:
    config = {
        "web": {
            "client_id": settings.GOOGLE_CLIENT_ID,
            "client_secret": settings.GOOGLE_CLIENT_SECRET,
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
            "redirect_uris": [settings.GOOGLE_REDIRECT_URI],
        }
    }
    return Flow.from_client_config(config, scopes=SCOPES, state=state, redirect_uri=settings.GOOGLE_REDIRECT_URI)


def auth_url() -> str:
    flow = _flow()
    url, state = flow.authorization_url(access_type="offline", prompt="consent", include_granted_scopes="false")
    _pending_verifiers[state] = flow.code_verifier
    return url


def finish_auth(state: str, code: str) -> None:
    if state not in _pending_verifiers:
        raise ValueError("Unknown or expired sign-in attempt.")
    flow = _flow(state=state)
    flow.code_verifier = _pending_verifiers.pop(state)
    flow.fetch_token(code=code)
    GMAIL_TOKEN_PATH.write_text(flow.credentials.to_json())


def credentials() -> Optional[Credentials]:
    if not GMAIL_TOKEN_PATH.exists():
        return None
    creds = Credentials.from_authorized_user_file(str(GMAIL_TOKEN_PATH), SCOPES)
    if creds.expired and creds.refresh_token:
        try:
            creds.refresh(Request())
        except RefreshError:
            log.warning("Gmail token refresh failed; user needs to reconnect")
            return None
        GMAIL_TOKEN_PATH.write_text(creds.to_json())
    return creds if creds.valid else None


def disconnect() -> None:
    GMAIL_TOKEN_PATH.unlink(missing_ok=True)


# --------------------------------------------------------------------------- background import job


@dataclass
class ImportJob:
    running: bool = False
    total: int = 0
    done: int = 0
    already_imported: int = 0
    error: Optional[str] = None
    results: list[dict[str, Any]] = field(default_factory=list)
    summary: Optional[dict[str, Any]] = None


_job = ImportJob()
_job_lock = threading.Lock()


def job_status() -> dict[str, Any]:
    return asdict(_job)


def start_import(months: int) -> bool:
    """Start a background import. Returns False if one is already running."""
    global _job
    with _job_lock:
        if _job.running:
            return False
        _job = ImportJob(running=True)
    threading.Thread(target=_run_import, args=(months,), daemon=True).start()
    return True


def _run_import(months: int) -> None:
    try:
        creds = credentials()
        if creds is None:
            _job.error = "Gmail isn't connected any more. Connect it again."
            return
        service = build("gmail", "v1", credentials=creds, cache_discovery=False)
        messages = _search(service, build_query(months))
        with Session(engine) as session:
            logs = session.exec(select(IngestLog).where(IngestLog.source == "gmail")).all()
            seen = {row.ref for row in logs if not any("AI unavailable" in n for n in row.notes)}  # retry AI outages
            todo = [m for m in messages if m["id"] not in seen]
            _job.already_imported = len(messages) - len(todo)
            _job.total = len(todo)
            docs = []
            for meta in todo:
                raw = service.users().messages().get(userId="me", id=meta["id"], format="raw").execute()
                data = base64.urlsafe_b64decode(raw["raw"].encode())
                doc = email_extract.read_eml(data, meta["id"], "gmail")
                docs.append((int(raw.get("internalDate", 0)), doc))
            results: list[FileIngestResult] = []
            for _, doc in sorted(docs, key=lambda d: d[0]):  # oldest -> newest: refunds after orders
                results.append(email_extract.ingest_doc(session, doc))
                _job.done += 1
                _job.results = [r.model_dump() for r in results]
            _job.summary = email_extract.summarise(results).model_dump()
    except HttpError as exc:
        log.warning("Gmail API error: %s", exc)
        _job.error = "Gmail returned an error. Try reconnecting."
    except Exception:  # noqa: BLE001 - background thread: never die silently
        log.exception("Gmail import failed")
        _job.error = "The import stopped unexpectedly. Try again."
    finally:
        _job.running = False


def _search(service: Any, query: str) -> list[dict[str, str]]:
    found: list[dict[str, str]] = []
    page_token = None
    while len(found) < MAX_MESSAGES:
        response = service.users().messages().list(
            userId="me", q=query, maxResults=min(100, MAX_MESSAGES - len(found)), pageToken=page_token
        ).execute()
        found += response.get("messages", [])
        page_token = response.get("nextPageToken")
        if not page_token:
            break
    return found[:MAX_MESSAGES]
