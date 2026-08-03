"""FastAPI entrypoint: /api/* for data, /photos for images, / for the display."""

import logging
from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app import scheduler
from app.api import router as api_router
from app.config import CALENDAR_FEEDS, DATA_DIR, PHOTOS_DIR, STATIC_DIR
from app.db import init_db

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
log = logging.getLogger("dashboard")

# Created at import time because StaticFiles refuses to mount a missing folder.
for _directory in (DATA_DIR, PHOTOS_DIR):
    _directory.mkdir(parents=True, exist_ok=True)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    init_db()
    log.info("Dashboard up — static=%s photos=%s", STATIC_DIR, PHOTOS_DIR)
    log.info("Calendar feeds: %s", [feed.key for feed in CALENDAR_FEEDS] or "none")

    jobs = scheduler.start()
    try:
        yield
    finally:
        # Don't hold shutdown open for a fetch that is mid-flight; the cache
        # already holds the last good data either way.
        jobs.shutdown(wait=False)
        log.info("Dashboard shutting down")


app = FastAPI(
    title="Family Wall Dashboard",
    docs_url=None,
    redoc_url=None,
    lifespan=lifespan,
)


@app.get("/healthz")
def healthz() -> dict[str, str]:
    return {"status": "ok"}


# Order matters: /api and /photos must be registered before the catch-all
# static mount at "/", or the mount would swallow them.
app.include_router(api_router, prefix="/api")
app.mount("/photos", StaticFiles(directory=PHOTOS_DIR), name="photos")
app.mount("/", StaticFiles(directory=STATIC_DIR, html=True), name="static")
