from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class ExportBundleOptions(BaseModel):
    include_sources: bool | None = None
    include_sandbox: bool = False


class ExportBundleSource(BaseModel):
    document_id: str
    document_version_id: str
    original_filename: str
    content_type: str | None = None
    source_type: str
    sha256: str
    byte_size: int
    original_storage_path: str
    bundle_path: str | None = None
    included: bool
    missing: bool


class ExportBundleManifest(BaseModel):
    bundle_schema_version: Literal[1] = 1
    bundle_format: Literal["private-rag-repository-export"] = "private-rag-repository-export"
    generated_at: str
    repository: dict[str, object]
    export_options: dict[str, object]
    settings: dict[str, object]
    required_models: list[str]
    payloads: dict[str, str]
    sources: list[ExportBundleSource] = Field(default_factory=list)
    counts: dict[str, int]
    warnings: list[str] = Field(default_factory=list)


class ExportBundleBuildResult(BaseModel):
    filename: str
    data: bytes
    manifest: ExportBundleManifest


class ExportBundleSourceMapping(BaseModel):
    sha256: str
    path: str
    document_version_id: str | None = None


class ExportBundleValidationIssue(BaseModel):
    severity: Literal["error", "warning", "info"]
    code: str
    message: str
    path: str | None = None
    setting: str | None = None
    source_sha256: str | None = None
    document_version_id: str | None = None


class ExportBundleValidationResponse(BaseModel):
    can_recreate: bool
    manifest: ExportBundleManifest | None = None
    counts: dict[str, int] = Field(default_factory=dict)
    required_models: list[str] = Field(default_factory=list)
    blocking_errors: list[ExportBundleValidationIssue] = Field(default_factory=list)
    warnings: list[ExportBundleValidationIssue] = Field(default_factory=list)
    informational: list[ExportBundleValidationIssue] = Field(default_factory=list)

    @property
    def issues(self) -> list[ExportBundleValidationIssue]:
        return [*self.blocking_errors, *self.warnings, *self.informational]
