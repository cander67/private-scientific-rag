from __future__ import annotations

from collections.abc import Mapping
from typing import Any, TypeVar, cast, overload

from pydantic import BaseModel

from private_rag.retrieval.schemas import (
    EffectiveRetrievalSettings,
    MetadataBoostSettings,
    RetrievalDefaults,
    RetrievalSettingsSource,
)
from private_rag.search.schemas import FullTextSearchFilters

TDefaults = TypeVar("TDefaults", bound=RetrievalDefaults)


@overload
def normalize_retrieval_defaults(
    value: Mapping[str, Any] | RetrievalDefaults | None,
) -> RetrievalDefaults: ...


@overload
def normalize_retrieval_defaults(
    value: Mapping[str, Any] | RetrievalDefaults | None,
    *,
    defaults_type: type[TDefaults],
) -> TDefaults: ...


def normalize_retrieval_defaults(
    value: Mapping[str, Any] | RetrievalDefaults | None,
    *,
    defaults_type: type[RetrievalDefaults] = RetrievalDefaults,
) -> RetrievalDefaults:
    return defaults_type.model_validate(value or {})


def resolve_effective_retrieval_settings(
    *,
    fallback_defaults: RetrievalDefaults,
    repository_defaults: Mapping[str, Any] | RetrievalDefaults | None = None,
    session_defaults: Mapping[str, Any] | RetrievalDefaults | None = None,
    run_overrides: Mapping[str, Any] | RetrievalDefaults | None = None,
) -> EffectiveRetrievalSettings:
    values = fallback_defaults.model_dump(mode="json")
    sources = _fallback_sources(values)
    for source, layer in (
        ("repository_defaults", repository_defaults),
        ("session_defaults", session_defaults),
        ("run_override", run_overrides),
    ):
        if layer is None:
            continue
        source_name = cast(RetrievalSettingsSource, source)
        normalized = RetrievalDefaults.model_validate(layer).model_dump(mode="json")
        for field in _explicit_fields(layer):
            if field not in values:
                continue
            if field == "metadata_boosts":
                nested_fields = _explicit_nested_fields(layer, field)
                nested = values["metadata_boosts"]
                for nested_field in nested_fields:
                    nested[nested_field] = normalized["metadata_boosts"][nested_field]
                    sources[f"metadata_boosts.{nested_field}"] = source_name
                values["metadata_boosts"] = nested
            elif field == "filters":
                nested_fields = _explicit_nested_fields(layer, field)
                nested = values["filters"]
                for nested_field in nested_fields:
                    nested[nested_field] = normalized["filters"][nested_field]
                    sources[f"filters.{nested_field}"] = source_name
                values["filters"] = nested
            else:
                values[field] = normalized[field]
                sources[field] = source_name

    return EffectiveRetrievalSettings(
        settings=RetrievalDefaults.model_validate(values),
        sources=sources,
    )


def retrieval_request_payload(settings: RetrievalDefaults) -> dict[str, Any]:
    return settings.model_dump(mode="json")


def _fallback_sources(values: dict[str, Any]) -> dict[str, RetrievalSettingsSource]:
    sources: dict[str, RetrievalSettingsSource] = {}
    for field, value in values.items():
        if isinstance(value, dict) and field in {"metadata_boosts", "filters"}:
            for nested_field in value:
                sources[f"{field}.{nested_field}"] = "fallback_defaults"
        else:
            sources[field] = "fallback_defaults"
    return sources


def _explicit_fields(value: Mapping[str, Any] | RetrievalDefaults) -> set[str]:
    if isinstance(value, Mapping):
        return set(value.keys())
    return set(value.model_fields_set)


def _explicit_nested_fields(value: Mapping[str, Any] | RetrievalDefaults, field: str) -> set[str]:
    nested = value.get(field) if isinstance(value, Mapping) else getattr(value, field)
    if isinstance(nested, Mapping):
        return set(nested.keys())
    if isinstance(nested, FullTextSearchFilters | RetrievalDefaults | MetadataBoostSettings):
        return set(nested.model_fields_set)
    if isinstance(nested, BaseModel):
        return set(nested.model_fields_set)
    return set()
