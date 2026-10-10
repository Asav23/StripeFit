"""Application settings, loaded from backend/.env (never hard-code secrets or model names)."""

from functools import lru_cache
from pathlib import Path
from zoneinfo import ZoneInfo

from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parent.parent
ENV_FILE = BACKEND_DIR / ".env"
UPLOAD_DIR = BACKEND_DIR / "uploads"
DB_PATH = BACKEND_DIR / "stripefit.db"
GMAIL_TOKEN_PATH = BACKEND_DIR / ".gmail_token.json"
GMAIL_PENDING_PATH = BACKEND_DIR / ".gmail_oauth_pending.json"  # in-flight sign-ins (PKCE), survives reloads
MOCKS_DIR = Path(__file__).resolve().parent / "ai" / "mocks"


def _split(value: str) -> list[str]:
    return [part.strip() for part in value.split(",") if part.strip()]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=ENV_FILE, env_file_encoding="utf-8", extra="ignore")

    # AI
    OPENROUTER_API_KEY: str = ""
    OPENROUTER_APP_NAME: str = "StripeFit"
    MODEL_VISION: str = ""
    MODEL_VISION_FALLBACKS: str = ""
    MODEL_FAST: str = ""
    MODEL_FAST_FALLBACKS: str = ""
    MODEL_STYLIST: str = ""
    MODEL_STYLIST_FALLBACKS: str = ""
    USE_MOCK_AI: bool = True
    AI_TIMEOUT_SECONDS: float = 45

    # Stripe (test mode only)
    STRIPE_SECRET_KEY: str = ""
    STRIPE_PUBLISHABLE_KEY: str = ""
    STRIPE_WEBHOOK_SECRET: str = ""
    STRIPE_PRICE_ID: str = ""
    FRONTEND_URL: str = "http://localhost:5173"

    # Gmail
    GOOGLE_CLIENT_ID: str = ""
    GOOGLE_CLIENT_SECRET: str = ""
    GOOGLE_REDIRECT_URI: str = "http://localhost:8000/api/gmail/callback"

    # Defaults
    DEFAULT_LOCATION_NAME: str = "Dublin"
    DEFAULT_LAT: float = 53.3498
    DEFAULT_LON: float = -6.2603
    TIMEZONE: str = "Europe/Dublin"
    FREE_ITEM_LIMIT: int = 20
    DEMO_CONTROLS: bool = True  # /api/debug/* (AI log, demo switches). Set false if this is ever deployed.

    @property
    def tz(self) -> ZoneInfo:
        return ZoneInfo(self.TIMEZONE)

    def models_for(self, task_kind: str) -> tuple[str, list[str]]:
        """Return (primary, fallbacks) for 'vision' | 'fast' | 'stylist'."""
        primary = getattr(self, f"MODEL_{task_kind.upper()}")
        fallbacks = _split(getattr(self, f"MODEL_{task_kind.upper()}_FALLBACKS"))
        return primary, fallbacks

    @property
    def stripe_configured(self) -> bool:
        return self.STRIPE_SECRET_KEY.startswith("sk_test_") or self.STRIPE_SECRET_KEY.startswith("rk_test_")

    @property
    def gmail_configured(self) -> bool:
        return bool(self.GOOGLE_CLIENT_ID and self.GOOGLE_CLIENT_SECRET)


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
