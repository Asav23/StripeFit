"""Gmail connection and import (Pro)."""

import logging
from typing import Any, Optional

from fastapi import APIRouter, Depends
from fastapi.responses import RedirectResponse
from pydantic import BaseModel, Field
from sqlmodel import Session

from app.config import settings
from app.db import get_session
from app.errors import api_error
from app.services import gmail
from app.services.limits import require_pro

router = APIRouter(prefix="/api/gmail", tags=["gmail"])
log = logging.getLogger("stripefit.gmail")


def _require_configured() -> None:
    if not settings.gmail_configured:
        raise api_error(503, "gmail_not_configured", "Gmail import isn't set up yet.",
                        "Add GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET to backend/.env and restart the API.")


@router.get("/status")
def status() -> dict[str, Any]:
    connected = settings.gmail_configured and gmail.credentials() is not None
    return {"configured": settings.gmail_configured, "connected": connected, "job": gmail.job_status()}


@router.get("/auth-url")
def auth_url(session: Session = Depends(get_session)) -> dict[str, str]:
    require_pro(session, "Gmail import")
    _require_configured()
    return {"url": gmail.auth_url()}


@router.get("/callback")
def callback(code: Optional[str] = None, state: Optional[str] = None, error: Optional[str] = None) -> RedirectResponse:
    """Google redirects here after consent. We always send the browser back to the app."""
    target = f"{settings.FRONTEND_URL}/add?tab=gmail"
    if error or not code or not state:
        return RedirectResponse(f"{target}&gmail=cancelled")
    try:
        gmail.finish_auth(state, code)
    except Exception as exc:  # noqa: BLE001 - any OAuth failure becomes a friendly redirect
        log.warning("Gmail OAuth failed: %s", exc)
        return RedirectResponse(f"{target}&gmail=error")
    return RedirectResponse(f"{target}&gmail=connected")


@router.post("/disconnect")
def disconnect() -> dict[str, bool]:
    gmail.disconnect()
    return {"connected": False}


class ImportRequest(BaseModel):
    months: int = Field(default=12, ge=1, le=24)


@router.post("/import")
def start_import(body: ImportRequest, session: Session = Depends(get_session)) -> dict[str, Any]:
    require_pro(session, "Gmail import")
    _require_configured()
    if gmail.credentials() is None:
        raise api_error(409, "gmail_not_connected", "Gmail isn't connected.", "Tap “Connect Gmail” first.")
    if not gmail.start_import(body.months):
        raise api_error(409, "import_running", "An import is already running.", "Wait for it to finish.")
    return {"started": True, "job": gmail.job_status()}


@router.get("/import/status")
def import_status() -> dict[str, Any]:
    return gmail.job_status()
