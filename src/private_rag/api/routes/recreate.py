from __future__ import annotations

import json
from typing import Annotated

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from pydantic import ValidationError

from private_rag.api.routes.repositories import DbSession
from private_rag.api.routes.vector import EmbeddingProviderDependency, VectorStoreDependency
from private_rag.exports.schemas import (
    ExportBundleSourceMapping,
    ExportBundleValidationResponse,
    RecreateBundleOptions,
    RecreateBundleResponse,
)
from private_rag.exports.service import recreate_export_bundle_data, validate_export_bundle_data
from private_rag.vector.store import VectorStoreError

router = APIRouter(prefix="/repositories/recreate", tags=["recreate"])


@router.post("/bundle/validate", response_model=ExportBundleValidationResponse)
async def validate_recreate_bundle(
    file: Annotated[UploadFile, File()],
    available_models_json: Annotated[str | None, Form()] = None,
    source_mappings_json: Annotated[str | None, Form()] = None,
) -> ExportBundleValidationResponse:
    available_models = _parse_available_models(available_models_json)
    source_mappings = _parse_source_mappings(source_mappings_json)
    return validate_export_bundle_data(
        data=await file.read(),
        available_models=available_models,
        source_mappings=source_mappings,
    )


@router.post("/bundle", response_model=RecreateBundleResponse)
async def recreate_from_bundle(
    file: Annotated[UploadFile, File()],
    session: DbSession,
    store: VectorStoreDependency,
    embedder: EmbeddingProviderDependency,
    repository_name: Annotated[str | None, Form()] = None,
    target_repository_id: Annotated[str | None, Form()] = None,
    available_models_json: Annotated[str | None, Form()] = None,
    source_mappings_json: Annotated[str | None, Form()] = None,
) -> RecreateBundleResponse:
    try:
        return recreate_export_bundle_data(
            session=session,
            data=await file.read(),
            store=store,
            embedder=embedder,
            options=RecreateBundleOptions(
                repository_name=repository_name,
                target_repository_id=target_repository_id,
                available_models=_parse_available_models(available_models_json),
                source_mappings=_parse_source_mappings(source_mappings_json),
            ),
        )
    except VectorStoreError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


def _parse_available_models(raw: str | None) -> list[str] | None:
    if raw is None:
        return None
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise HTTPException(
            status_code=400,
            detail=f"available_models_json must be valid JSON: {exc.msg}",
        ) from exc
    if not isinstance(parsed, list) or not all(isinstance(item, str) for item in parsed):
        raise HTTPException(status_code=400, detail="available_models_json must be a string list")
    return parsed


def _parse_source_mappings(raw: str | None) -> list[ExportBundleSourceMapping]:
    if raw is None:
        return []
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise HTTPException(
            status_code=400,
            detail=f"source_mappings_json must be valid JSON: {exc.msg}",
        ) from exc
    try:
        return [ExportBundleSourceMapping.model_validate(item) for item in parsed]
    except (TypeError, ValidationError) as exc:
        raise HTTPException(
            status_code=400,
            detail="source_mappings_json must be a list of source mapping objects",
        ) from exc
