from __future__ import annotations

import hashlib
from pathlib import Path

from private_rag.exports.schemas import ExportBundleManifest
from private_rag.exports.service import sha256_file, source_bundle_path


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
