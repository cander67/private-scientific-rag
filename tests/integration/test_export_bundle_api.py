from __future__ import annotations

import hashlib
import json
from collections.abc import Generator
from io import BytesIO
from pathlib import Path
from zipfile import ZipFile

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from private_rag.api.app import create_app
from private_rag.api.routes.repositories import get_db_session
from private_rag.chat.models import ChatMessageRow, ChatSession
from private_rag.core.settings import Settings
from private_rag.db.base import Base
from private_rag.ingestion.models import Document, DocumentChunk, DocumentVersion
from private_rag.prompt_sandbox.models import SandboxComparison, SandboxPromptVersion, SandboxRun
from private_rag.repositories import models as repository_models  # noqa: F401
from private_rag.repositories.service import ensure_default_repository
from private_rag.retrieval.models import RetrievalResult, RetrievalRun


def _client_with_database() -> tuple[TestClient, sessionmaker[Session], Path]:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine, autoflush=False, autocommit=False, class_=Session)

    def override_session() -> Generator[Session, None, None]:
        with session_factory() as session:
            yield session

    app = create_app()
    app.dependency_overrides[get_db_session] = override_session
    return TestClient(app), session_factory, Path("unused")


def test_export_bundle_zip_contains_default_payloads_and_sources(tmp_path: Path) -> None:
    client, session_factory, _ = _client_with_database()
    repository_id, source_digest = _seed_repository(session_factory, tmp_path)

    response = client.post(f"/repositories/{repository_id}/exports/bundle")

    assert response.status_code == 200
    assert response.headers["content-type"] == "application/zip"
    archive_path = tmp_path / "export.zip"
    archive_path.write_bytes(response.content)

    with ZipFile(archive_path) as archive:
        names = set(archive.namelist())
        assert "manifest.json" in names
        assert "payloads/settings.json" in names
        assert "payloads/prompts.json" in names
        assert "payloads/documents.json" in names
        assert "payloads/chunks.json" in names
        assert "payloads/chat.json" in names
        assert "payloads/retrieval.json" in names
        assert "payloads/sandbox.json" not in names

        manifest = json.loads(archive.read("manifest.json"))
        source_entry = manifest["sources"][0]
        assert manifest["bundle_schema_version"] == 1
        assert manifest["export_options"]["include_sources"] is True
        assert manifest["export_options"]["include_sandbox"] is False
        assert source_entry["sha256"] == source_digest
        assert source_entry["bundle_path"] == f"sources/{source_digest}/paper.txt"
        assert archive.read(source_entry["bundle_path"]) == b"alpha beta gamma"
        assert manifest["counts"]["chunks"] == 1
        assert manifest["counts"]["chat_citations"] == 1

        chat_payload = json.loads(archive.read("payloads/chat.json"))
        retrieval_payload = json.loads(archive.read("payloads/retrieval.json"))
        chunks_payload = json.loads(archive.read("payloads/chunks.json"))
        assert (
            chat_payload["messages"][1]["citations"][0]["chunk_id"]
            == chunks_payload["chunks"][0]["id"]
        )
        assert retrieval_payload["results"][0]["chunk_id"] == chunks_payload["chunks"][0]["id"]


def test_export_bundle_can_exclude_sources_and_opt_into_sandbox(
    tmp_path: Path,
) -> None:
    client, session_factory, _ = _client_with_database()
    repository_id, source_digest = _seed_repository(session_factory, tmp_path)

    response = client.post(
        f"/repositories/{repository_id}/exports/bundle",
        params={"include_sources": "false", "include_sandbox": "true"},
    )

    assert response.status_code == 200
    archive_path = tmp_path / "export-with-sandbox.zip"
    archive_path.write_bytes(response.content)

    with ZipFile(archive_path) as archive:
        names = set(archive.namelist())
        assert "payloads/sandbox.json" in names
        assert f"sources/{source_digest}/paper.txt" not in names

        manifest = json.loads(archive.read("manifest.json"))
        assert manifest["export_options"]["include_sources"] is False
        assert manifest["export_options"]["include_sandbox"] is True
        assert manifest["sources"][0]["sha256"] == source_digest
        assert manifest["sources"][0]["bundle_path"] is None
        assert manifest["sources"][0]["included"] is False
        assert manifest["counts"]["sandbox_runs"] == 1


def test_validate_bundle_endpoint_accepts_valid_bundle_and_reports_summary(
    tmp_path: Path,
) -> None:
    client, session_factory, _ = _client_with_database()
    repository_id, _ = _seed_repository(session_factory, tmp_path)
    bundle = client.post(f"/repositories/{repository_id}/exports/bundle").content

    response = client.post(
        "/repositories/recreate/bundle/validate",
        files={"file": ("export.zip", bundle, "application/zip")},
        data={"available_models_json": json.dumps([])},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["can_recreate"] is True
    assert payload["counts"]["sources"] == 1
    assert payload["counts"]["chunks"] == 1
    assert {issue["code"] for issue in payload["warnings"]} == {"missing_model"}
    assert "source_hash_verified" in {issue["code"] for issue in payload["informational"]}
    assert "parser_fingerprint" in {issue["code"] for issue in payload["informational"]}


def test_validate_bundle_endpoint_reports_missing_payload(
    tmp_path: Path,
) -> None:
    client, session_factory, _ = _client_with_database()
    repository_id, _ = _seed_repository(session_factory, tmp_path)
    bundle = _remove_zip_member(
        client.post(f"/repositories/{repository_id}/exports/bundle").content,
        "payloads/chunks.json",
    )

    response = client.post(
        "/repositories/recreate/bundle/validate",
        files={"file": ("export.zip", bundle, "application/zip")},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["can_recreate"] is False
    assert "missing_payload" in {issue["code"] for issue in payload["blocking_errors"]}


def test_validate_bundle_endpoint_reports_included_source_hash_mismatch(
    tmp_path: Path,
) -> None:
    client, session_factory, _ = _client_with_database()
    repository_id, source_digest = _seed_repository(session_factory, tmp_path)
    bundle = _replace_zip_member(
        client.post(f"/repositories/{repository_id}/exports/bundle").content,
        f"sources/{source_digest}/paper.txt",
        b"changed bytes",
    )

    response = client.post(
        "/repositories/recreate/bundle/validate",
        files={"file": ("export.zip", bundle, "application/zip")},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["can_recreate"] is False
    assert "source_hash_mismatch" in {issue["code"] for issue in payload["blocking_errors"]}


def test_validate_bundle_endpoint_accepts_external_source_mapping(
    tmp_path: Path,
) -> None:
    client, session_factory, _ = _client_with_database()
    repository_id, source_digest = _seed_repository(session_factory, tmp_path)
    bundle = client.post(
        f"/repositories/{repository_id}/exports/bundle",
        params={"include_sources": "false"},
    ).content
    mapped_source = tmp_path / "renamed-paper.txt"
    mapped_source.write_bytes(b"alpha beta gamma")

    response = client.post(
        "/repositories/recreate/bundle/validate",
        files={"file": ("export.zip", bundle, "application/zip")},
        data={
            "available_models_json": json.dumps([]),
            "source_mappings_json": json.dumps(
                [{"sha256": source_digest, "path": str(mapped_source)}]
            ),
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["can_recreate"] is True
    assert "external_source_renamed" in {issue["code"] for issue in payload["warnings"]}
    assert "external_source_hash_verified" in {issue["code"] for issue in payload["informational"]}


def test_validate_bundle_endpoint_reports_external_source_failures(
    tmp_path: Path,
) -> None:
    client, session_factory, _ = _client_with_database()
    repository_id, source_digest = _seed_repository(session_factory, tmp_path)
    bundle = client.post(
        f"/repositories/{repository_id}/exports/bundle",
        params={"include_sources": "false"},
    ).content
    wrong_source = tmp_path / "paper.txt"
    wrong_source.write_bytes(b"wrong")

    missing_mapping_response = client.post(
        "/repositories/recreate/bundle/validate",
        files={"file": ("export.zip", bundle, "application/zip")},
    )
    mismatch_response = client.post(
        "/repositories/recreate/bundle/validate",
        files={"file": ("export.zip", bundle, "application/zip")},
        data={
            "source_mappings_json": json.dumps(
                [{"sha256": source_digest, "path": str(wrong_source)}]
            ),
        },
    )

    assert missing_mapping_response.status_code == 200
    assert mismatch_response.status_code == 200
    assert "missing_external_source_mapping" in {
        issue["code"] for issue in missing_mapping_response.json()["blocking_errors"]
    }
    assert "external_source_hash_mismatch" in {
        issue["code"] for issue in mismatch_response.json()["blocking_errors"]
    }


def _seed_repository(
    session_factory: sessionmaker[Session],
    tmp_path: Path,
) -> tuple[str, str]:
    source_path = tmp_path / "paper.txt"
    source_path.write_bytes(b"alpha beta gamma")
    source_digest = hashlib.sha256(b"alpha beta gamma").hexdigest()

    with session_factory() as session:
        repository_with_settings = ensure_default_repository(
            session,
            Settings(data_dir=tmp_path, database_url="sqlite://"),
        )
        repository_id = repository_with_settings.repository.id

        document = Document(repository_id=repository_id, display_name="paper.txt")
        session.add(document)
        session.flush()

        version = DocumentVersion(
            document_id=document.id,
            repository_id=repository_id,
            original_filename="paper.txt",
            content_type="text/plain",
            source_type="text",
            sha256=source_digest,
            byte_size=len(b"alpha beta gamma"),
            storage_path=str(source_path),
            status="parsed",
            parser_name="private-rag-built-in",
            parser_version="prd3-v1",
            ocr_required=False,
            page_count=None,
            line_count=1,
            section_count=1,
            chunk_count=1,
            warnings=[],
            extra_metadata={"document_kind": "note"},
        )
        session.add(version)
        session.flush()

        chunk = DocumentChunk(
            repository_id=repository_id,
            document_id=document.id,
            document_version_id=version.id,
            chunk_index=0,
            text="alpha beta gamma",
            section="Abstract",
            page_start=None,
            page_end=None,
            line_start=1,
            line_end=1,
            char_start=0,
            char_end=16,
            parser_version="prd3-v1",
            extra_metadata={"source_hash": source_digest},
        )
        session.add(chunk)
        session.flush()

        document.current_version_id = version.id
        session.add(document)

        retrieval_run = RetrievalRun(
            repository_id=repository_id,
            mode="full_text",
            query="alpha",
            filters={},
            top_k=3,
            candidate_pool_size=15,
            rrf_constant=60,
            embedding_model=None,
            embedding_run_id=None,
            vector_collection_name=None,
            reranker_strategy="none",
            reranker_model=None,
            metadata_boosts={},
            settings_snapshot=repository_with_settings.settings.model_dump(mode="json"),
        )
        session.add(retrieval_run)
        session.flush()

        session.add(
            RetrievalResult(
                run_id=retrieval_run.id,
                repository_id=repository_id,
                document_id=document.id,
                document_version_id=version.id,
                chunk_id=chunk.id,
                chunk_index=chunk.chunk_index,
                rank=1,
                final_score=1.0,
                score_breakdown={"bm25": 1.0},
                source_ranks={"full_text": 1},
                matched_fields=["body"],
                result_metadata={"source_type": "text"},
            )
        )

        chat_session = ChatSession(
            repository_id=repository_id,
            title="Export test chat",
            model=repository_with_settings.settings.model.ollama_chat_model,
            retrieval_settings={"mode": "full_text", "top_k": 3, "reranker_strategy": "none"},
            prompt_id=repository_with_settings.settings.prompt.active_chat_prompt_id,
        )
        session.add(chat_session)
        session.flush()
        session.add_all(
            [
                ChatMessageRow(
                    session_id=chat_session.id,
                    repository_id=repository_id,
                    sequence=1,
                    role="user",
                    content="What mentions alpha?",
                    retrieval_run_id=None,
                    citations=[],
                    extra_metadata={},
                ),
                ChatMessageRow(
                    session_id=chat_session.id,
                    repository_id=repository_id,
                    sequence=2,
                    role="assistant",
                    content="The source mentions alpha. [1]",
                    retrieval_run_id=retrieval_run.id,
                    citations=[
                        {
                            "citation_id": 1,
                            "chunk_id": chunk.id,
                            "document_id": document.id,
                            "document_version_id": version.id,
                        }
                    ],
                    extra_metadata={},
                ),
            ]
        )

        prompt_version = SandboxPromptVersion(
            repository_id=repository_id,
            name="Sandbox prompt",
            body="Answer carefully.",
            notes=None,
            source_chat_prompt_id=None,
            used_by_run=True,
        )
        session.add(prompt_version)
        session.flush()
        comparison = SandboxComparison(
            repository_id=repository_id,
            query="alpha",
            status="completed",
            expected_run_count=1,
        )
        session.add(comparison)
        session.flush()
        session.add(
            SandboxRun(
                repository_id=repository_id,
                prompt_version_id=prompt_version.id,
                comparison_id=comparison.id,
                comparison_index=0,
                label="full text",
                query="alpha",
                model=repository_with_settings.settings.model.ollama_chat_model,
                retrieval_settings={"mode": "full_text"},
                prompt_snapshot={"body": prompt_version.body},
                context_entries=[],
                retrieval_run_id=retrieval_run.id,
                answer="alpha",
                citations=[],
                metrics={},
                latency_ms=10,
                status="completed",
            )
        )

        session.commit()
        return repository_id, source_digest


def _remove_zip_member(data: bytes, removed_path: str) -> bytes:
    buffer = BytesIO()
    with ZipFile(BytesIO(data)) as source_archive, ZipFile(buffer, "w") as target_archive:
        for name in source_archive.namelist():
            if name != removed_path:
                target_archive.writestr(name, source_archive.read(name))
    return buffer.getvalue()


def _replace_zip_member(data: bytes, replaced_path: str, replacement: bytes) -> bytes:
    buffer = BytesIO()
    with ZipFile(BytesIO(data)) as source_archive, ZipFile(buffer, "w") as target_archive:
        for name in source_archive.namelist():
            target_archive.writestr(
                name,
                replacement if name == replaced_path else source_archive.read(name),
            )
    return buffer.getvalue()
