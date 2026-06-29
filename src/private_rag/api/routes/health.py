from __future__ import annotations

from fastapi import APIRouter

from private_rag import __version__
from private_rag.core.settings import get_settings
from private_rag.services.qdrant import check_qdrant

router = APIRouter(tags=["health"])


@router.get("/health")
async def health() -> dict[str, object]:
    settings = get_settings()
    qdrant = await check_qdrant(settings.qdrant_url)
    return {
        "status": "ok",
        "app": "private-scientific-rag",
        "version": __version__,
        "environment": settings.environment,
        "local_only": True,
        "data_dir": str(settings.data_dir),
        "database_url": settings.safe_database_url,
        "qdrant": qdrant,
    }
