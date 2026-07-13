from __future__ import annotations

import hashlib
import json
from io import BytesIO
from pathlib import Path
from zipfile import ZipFile

from private_rag.exports.schemas import ExportBundleManifest
from private_rag.exports.service import (
    MANIFEST_PATH,
    sha256_file,
    source_bundle_path,
    validate_export_bundle_data,
)


def test_source_bundle_path_is_stable_and_sanitized() -> None:
    assert (
        source_bundle_path("abc123", "../Patent Example (draft).pdf")
        == "sources/abc123/Patent_Example_draft_.pdf"
    )


def test_sha256_file_uses_file_bytes(tmp_path: Path) -> None:
    source = tmp_path / "paper.txt"
    source.write_bytes(b"deterministic source bytes")

    assert sha256_file(source) == hashlib.sha256(b"deterministic source bytes").hexdigest()


def test_export_bundle_manifest_schema_accepts_phase_one_contract() -> None:
    manifest = ExportBundleManifest.model_validate(
        {
            "generated_at": "2026-07-13T12:00:00+00:00",
            "repository": {"id": "repo-1", "name": "Repository"},
            "export_options": {"include_sources": True, "include_sandbox": False},
            "settings": {"export": {"include_sources": True}},
            "required_models": ["gemma3:4b"],
            "payloads": {"settings": "payloads/settings.json"},
            "sources": [],
            "counts": {"sources": 0},
            "warnings": [],
        }
    )

    assert manifest.bundle_schema_version == 1
    assert manifest.bundle_format == "private-rag-repository-export"


def test_validate_export_bundle_rejects_invalid_zip() -> None:
    result = validate_export_bundle_data(b"not a zip")

    assert result.can_recreate is False
    assert result.blocking_errors[0].code == "invalid_zip"


def test_validate_export_bundle_rejects_unsupported_schema_version() -> None:
    buffer = BytesIO()
    with ZipFile(buffer, "w") as archive:
        archive.writestr(
            MANIFEST_PATH,
            json.dumps(
                {
                    "bundle_schema_version": 2,
                    "bundle_format": "private-rag-repository-export",
                }
            ),
        )

    result = validate_export_bundle_data(buffer.getvalue())

    assert result.can_recreate is False
    assert result.blocking_errors[0].code == "unsupported_schema_version"
