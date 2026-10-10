"""Developer views: AI call log, ingest log, and mock-mode switches for testing fallbacks."""

from typing import Any, Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlmodel import Session, col, select

from app.ai import mocks
from app.config import settings
from app.db import get_session
from app.errors import api_error
from app.models import AICall, IngestLog
from app.services import weather
from app.services.limits import get_user

def _demo_controls_on() -> None:
    """These endpoints have no auth (local single-user prototype), so they can be switched off."""
    if not settings.DEMO_CONTROLS:
        raise api_error(404, "not_found", "Demo controls are turned off.", "Set DEMO_CONTROLS=true in backend/.env.")


router = APIRouter(prefix="/api/debug", tags=["debug"], dependencies=[Depends(_demo_controls_on)])


@router.get("/ai-calls")
def ai_calls(limit: int = 100, session: Session = Depends(get_session)) -> dict[str, Any]:
    rows = session.exec(select(AICall).order_by(col(AICall.created_at).desc()).limit(min(limit, 500))).all()
    calls = [r.model_dump(mode="json") for r in rows]
    return {
        "calls": calls,
        "totals": {
            "count": len(calls),
            "failures": sum(1 for c in calls if not c["success"]),
            "cost": round(sum(c["cost"] or 0 for c in calls), 6),
            "avg_latency_ms": int(sum(c["latency_ms"] for c in calls) / len(calls)) if calls else 0,
        },
        "mock_ai": settings.USE_MOCK_AI,
        "models": {kind: settings.models_for(kind) for kind in ("vision", "fast", "stylist")},
    }


@router.get("/ingest-logs")
def ingest_logs(limit: int = 100, session: Session = Depends(get_session)) -> list[dict[str, Any]]:
    rows = session.exec(select(IngestLog).order_by(col(IngestLog.created_at).desc()).limit(min(limit, 500))).all()
    return [r.model_dump(mode="json") for r in rows]


class MockOverride(BaseModel):
    task: str
    variant: Optional[str] = None  # None clears; "error" forces a failure; else loads {task}.{variant}.json


@router.get("/mock-override")
def get_mock_overrides() -> dict[str, Any]:
    return {"overrides": mocks.OVERRIDES, "available": mocks.available_variants()}


@router.post("/mock-override")
def set_mock_override(body: MockOverride) -> dict[str, Any]:
    if not settings.USE_MOCK_AI:
        raise api_error(409, "mock_off", "Mock overrides only work when USE_MOCK_AI=true.")
    if body.variant:
        mocks.OVERRIDES[body.task] = body.variant
    else:
        mocks.OVERRIDES.pop(body.task, None)
    return {"overrides": mocks.OVERRIDES}


@router.post("/reset-premium")
def reset_premium(session: Session = Depends(get_session)) -> dict[str, bool]:
    """Demo helper: go back to the free plan (purchase records are kept)."""
    user = get_user(session)
    user.premium = False
    user.premium_since = None
    session.add(user)
    session.commit()
    return {"premium": False}


class WeatherOverride(BaseModel):
    preset: Optional[str] = None  # "rain" | "cold" | "hot"; None = real forecast


@router.get("/weather-override")
def get_weather_override() -> dict[str, Any]:
    active = next((k for k, v in weather.DEMO_WEATHER.items() if v is weather.OVERRIDE), None)
    return {"preset": active, "presets": list(weather.DEMO_WEATHER)}


@router.post("/weather-override")
def set_weather_override(body: WeatherOverride) -> dict[str, Any]:
    if body.preset and body.preset not in weather.DEMO_WEATHER:
        raise api_error(422, "unknown_preset", f"Use one of: {', '.join(weather.DEMO_WEATHER)}.")
    weather.OVERRIDE = weather.DEMO_WEATHER[body.preset] if body.preset else None
    return {"preset": body.preset}
