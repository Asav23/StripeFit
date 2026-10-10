"""A tiny in-process scheduler: once a minute, send the morning casual-fit notification if it's due.

Good enough for a local single-user prototype: the API is the only process, and daily.run_if_due()
records the date it last sent, so restarts never send twice. A deployed version would use a real
job runner (cron, Cloud Scheduler) calling the same function.
"""

import logging
import threading

from sqlmodel import Session

from app import db
from app.config import settings
from app.services import daily

log = logging.getLogger("stripefit.scheduler")

CHECK_EVERY_SECONDS = 60

_stop = threading.Event()
_thread: threading.Thread | None = None


def start() -> None:
    global _thread
    if not settings.DAILY_SCHEDULER_ENABLED or (_thread and _thread.is_alive()):
        return
    _stop.clear()
    _thread = threading.Thread(target=_loop, name="daily-fit-scheduler", daemon=True)
    _thread.start()
    log.info("Daily fit scheduler started (checks every %ss)", CHECK_EVERY_SECONDS)


def stop() -> None:
    _stop.set()


def _loop() -> None:
    while not _stop.is_set():
        try:
            with Session(db.engine) as session:
                daily.run_if_due(session)
        except Exception:  # noqa: BLE001 - the scheduler must keep running whatever happens
            log.exception("Daily fit check failed")
        _stop.wait(CHECK_EVERY_SECONDS)
