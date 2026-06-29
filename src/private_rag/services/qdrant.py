from __future__ import annotations

import httpx


async def check_qdrant(qdrant_url: str) -> dict[str, object]:
    url = qdrant_url.rstrip("/")
    try:
        async with httpx.AsyncClient(timeout=1.0) as client:
            response = await client.get(f"{url}/")
            response.raise_for_status()
    except httpx.HTTPError as exc:
        return {
            "status": "unavailable",
            "url": url,
            "detail": str(exc),
        }

    return {
        "status": "ok",
        "url": url,
    }
