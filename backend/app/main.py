"""StripeFit API."""

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from app.ai.client import AIError
from app.config import UPLOAD_DIR, settings
from app.db import init_db
from app.routers import debug, gmail, ingest, items, me, outfits, review, stripe

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger("stripefit")


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    init_db()
    log.info("StripeFit API ready (mock AI: %s)", settings.USE_MOCK_AI)
    yield


app = FastAPI(title="StripeFit API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.FRONTEND_URL, "http://localhost:5173", "http://127.0.0.1:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---- errors: always the {"detail": {"code", "message", "next_step"}} shape, never a raw exception


@app.exception_handler(AIError)
async def ai_error_handler(_: Request, exc: AIError) -> JSONResponse:
    log.warning("AI error: %s", exc)
    return JSONResponse(
        status_code=503,
        content={"detail": {"code": f"ai_{exc.kind}", "message": exc.user_message, "next_step": "Try again in a minute."}},
    )


@app.exception_handler(RequestValidationError)
async def validation_error_handler(_: Request, exc: RequestValidationError) -> JSONResponse:
    first = exc.errors()[0] if exc.errors() else {}
    field = ".".join(str(p) for p in first.get("loc", []) if p != "body")
    return JSONResponse(
        status_code=422,
        content={"detail": {"code": "invalid_input", "message": f"Please check {field or 'your input'}: {first.get('msg', 'invalid value')}."}},
    )


@app.exception_handler(Exception)
async def unexpected_error_handler(_: Request, exc: Exception) -> JSONResponse:
    log.exception("Unhandled error", exc_info=exc)
    return JSONResponse(
        status_code=500,
        content={"detail": {"code": "internal_error", "message": "Something went wrong on our side.", "next_step": "Please try again."}},
    )


# ---- routes


@app.get("/api/health")
def health() -> dict[str, bool]:
    return {"ok": True, "mock_ai": settings.USE_MOCK_AI}


for module in (items, me, review, ingest, outfits, stripe, gmail, debug):
    app.include_router(module.router)

UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
app.mount("/uploads", StaticFiles(directory=UPLOAD_DIR), name="uploads")
