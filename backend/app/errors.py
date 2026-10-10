"""One error shape for the whole API: {"detail": {"code", "message", "next_step"}}.

The frontend shows `message` (and `next_step` when present) and never a raw exception.
"""

from typing import Any

from fastapi import HTTPException


def api_error(status: int, code: str, message: str, next_step: str | None = None, **extra: Any) -> HTTPException:
    detail: dict[str, Any] = {"code": code, "message": message}
    if next_step:
        detail["next_step"] = next_step
    detail.update(extra)
    return HTTPException(status_code=status, detail=detail)


def not_found(what: str = "Item") -> HTTPException:
    return api_error(404, "not_found", f"{what} not found. It may have been deleted.", "Refresh the page.")
