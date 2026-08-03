"""Sync a Google Photos public shared album into photos/ for the slideshow.

Scrapes the album's share page — no Google login — and downloads each image at
a bounded size. Files land in PHOTOS_DIR behind PHOTO_SYNC_PREFIX, so the
existing /api/photos listing serves them unchanged and manual drops are never
touched. Serve-stale: a failed sync, or one that finds no photos (private link,
changed markup), leaves the last good set on the wall rather than blanking it.
"""

import hashlib
import logging
import re
from pathlib import Path

import httpx

from app.config import (
    FETCH_TIMEOUT_SECONDS,
    PHOTO_SYNC_HEIGHT,
    PHOTO_SYNC_MAX,
    PHOTO_SYNC_PREFIX,
    PHOTO_SYNC_WIDTH,
    PHOTOS_ALBUM_URL,
    PHOTOS_DIR,
)
from app.db import connect, record_attempt, record_failure, record_success

log = logging.getLogger("dashboard.photos")

JOB_NAME = "photos"

#: Media items on the album page are serialised as ["<lh3 base url>", w, h, ...].
#: Matching the trailing width/height avoids picking up avatars and other chrome
#: that use the same host without those dimensions.
_MEDIA_RE = re.compile(
    r'\["(https://lh3\.googleusercontent\.com/[\w\-/]+)",(\d+),(\d+)'
)

#: Google serves the share page differently to a bare client; look like Chrome.
_BROWSER_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
)


def run() -> None:
    """Sync the album once. Never raises — the scheduler must survive."""
    if not PHOTOS_ALBUM_URL:
        return

    with connect() as conn:
        record_attempt(conn, JOB_NAME)

    try:
        _sync(PHOTOS_ALBUM_URL)
    except Exception as exc:
        log.exception("Google Photos sync failed")
        with connect() as conn:
            record_failure(conn, JOB_NAME, f"{type(exc).__name__}: {exc}")
        return

    with connect() as conn:
        record_success(conn, JOB_NAME)


def _sync(album_url: str) -> None:
    with httpx.Client(
        timeout=FETCH_TIMEOUT_SECONDS,
        follow_redirects=True,
        headers={"User-Agent": _BROWSER_UA},
    ) as client:
        page = client.get(album_url)
        page.raise_for_status()

        bases = _extract_photo_urls(page.text)
        if not bases:
            # Refuse to prune a good set just because the page had nothing we
            # recognised — most likely the link is not public.
            raise RuntimeError(
                "no photos found on the album page — is the link set to "
                "'anyone with the link'?"
            )
        if PHOTO_SYNC_MAX > 0:
            bases = bases[:PHOTO_SYNC_MAX]

        # Stable name per photo (hash of its base URL) so re-syncs are cheap:
        # an already-downloaded photo is skipped, not fetched again.
        wanted: dict[str, str] = {
            f"{PHOTO_SYNC_PREFIX}{_hash(base)}.jpg": (
                f"{base}=w{PHOTO_SYNC_WIDTH}-h{PHOTO_SYNC_HEIGHT}"
            )
            for base in bases
        }

        PHOTOS_DIR.mkdir(parents=True, exist_ok=True)
        downloaded = 0
        for name, url in wanted.items():
            dest = PHOTOS_DIR / name
            if dest.exists():
                continue
            try:
                _download(client, url, dest)
                downloaded += 1
            except Exception as exc:  # one bad image must not fail the sync
                log.warning("Skipping photo %s: %s", name, exc)

    removed = _prune(set(wanted))
    log.info(
        "Google Photos: %d in album, %d downloaded, %d pruned",
        len(wanted),
        downloaded,
        removed,
    )


def _extract_photo_urls(html: str) -> list[str]:
    """Ordered, de-duplicated photo base URLs from the album page."""
    seen: set[str] = set()
    ordered: list[str] = []
    for match in _MEDIA_RE.finditer(html):
        base = match.group(1)
        if base not in seen:
            seen.add(base)
            ordered.append(base)
    return ordered


def _download(client: httpx.Client, url: str, dest: Path) -> None:
    resp = client.get(url)
    resp.raise_for_status()
    # Write to a sidecar first, then swap in — the slideshow never sees a
    # half-written file (and .part is not a served extension anyway).
    tmp = dest.with_suffix(".part")
    tmp.write_bytes(resp.content)
    tmp.replace(dest)


def _prune(keep: set[str]) -> int:
    """Delete synced files (and stray .part sidecars) no longer in the album."""
    removed = 0
    for path in PHOTOS_DIR.glob(f"{PHOTO_SYNC_PREFIX}*"):
        if path.is_file() and path.name not in keep:
            path.unlink(missing_ok=True)
            removed += 1
    return removed


def _hash(text: str) -> str:
    return hashlib.sha1(text.encode()).hexdigest()[:16]
