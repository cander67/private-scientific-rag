from __future__ import annotations

from io import BytesIO
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse

from private_rag.api.routes.repositories import DbSession
from private_rag.exports.schemas import ExportBundleOptions
from private_rag.exports.service import build_export_bundle

router = APIRouter(prefix="/repositories/{repository_id}/exports", tags=["exports"])


@router.post("/bundle")
def export_repository_bundle(
    repository_id: str,
    session: DbSession,
    options: Annotated[ExportBundleOptions, Depends()],
) -> StreamingResponse:
    bundle = build_export_bundle(session, repository_id, options)
    if bundle is None:
        raise HTTPException(status_code=404, detail="Repository not found")
    headers = {"Content-Disposition": f'attachment; filename="{bundle.filename}"'}
    return StreamingResponse(BytesIO(bundle.data), media_type="application/zip", headers=headers)
