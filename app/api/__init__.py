"""API routers, all mounted under /api by app.main."""

from fastapi import APIRouter

from app.api import (
    admin,
    admin_logs,
    alerts,
    backgrounds,
    events,
    importer,
    photos,
    settings,
    status,
    weather,
)

router = APIRouter()
router.include_router(settings.router)
router.include_router(photos.router)
router.include_router(backgrounds.router)
router.include_router(events.router)
router.include_router(weather.router)
router.include_router(alerts.router)
router.include_router(admin.router)
router.include_router(admin_logs.router)
router.include_router(importer.router)
router.include_router(status.router)
