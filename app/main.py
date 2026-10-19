"""FastAPI entrypoint: /api/* for data, /photos for images, / for the display."""

import logging
import time
from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app import scheduler
from app.api import router as api_router
from app.config import CALENDAR_FEEDS, DATA_DIR, PHOTOS_DIR, STATIC_DIR
from app.db import init_db
from app.logging_setup import configure_logging

# Configure logging before anything else so startup lines land in the log file.
configure_logging()
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


#: Changes on every process start, so the admin page's "Save & restart" can
#: tell the relaunched server apart from the old one still answering.
_BOOT_ID = str(time.time_ns())


@app.get("/healthz")
def healthz() -> dict[str, str]:
    return {"status": "ok", "boot": _BOOT_ID}


# The static mount serves everything else, but "/admin" (no extension) needs an
# explicit route or the SPA-less mount can't find it. Registered before the "/"
# mount so the catch-all doesn't swallow it.
@app.api_route("/admin", methods=["GET", "HEAD"])
def admin_page() -> FileResponse:
    return _html_page("admin.html")


# The wall: the Phase 7 light layout. Explicit so the "/" mount below never
# falls back to index.html; "/v2" is kept as an alias (the mockup notes use it).
@app.api_route("/", methods=["GET", "HEAD"])
@app.api_route("/v2", methods=["GET", "HEAD"])
def wall_page() -> FileResponse:
    return _html_page("v2.html")


# The previous dark wall; its assets keep their absolute /css, /js paths.
@app.api_route("/v1", methods=["GET", "HEAD"])
def v1_page() -> FileResponse:
    return _html_page("index.html")


# Pages are revalidated on every load, so a kiosk relaunch after a deploy never
# shows a heuristically-cached old page. Assets under the mounts stay cacheable.
# HEAD is routed too, or `curl -I` would fall through to the mount's index.html.
def _html_page(name: str) -> FileResponse:
    return FileResponse(STATIC_DIR / name, headers={"Cache-Control": "no-cache"})


# Order matters: /api and /photos must be registered before the catch-all
# static mount at "/", or the mount would swallow them.
app.include_router(api_router, prefix="/api")
app.mount("/photos", StaticFiles(directory=PHOTOS_DIR), name="photos")
app.mount("/", StaticFiles(directory=STATIC_DIR, html=True), name="static")
