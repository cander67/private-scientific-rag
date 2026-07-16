from __future__ import annotations

from time import perf_counter

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from private_rag.chat.citations import map_citations
from private_rag.chat.llm import ChatLLM
from private_rag.chat.schemas import ChatCitation, ChatRetrievalSettings
from private_rag.chat.service import build_chat_prompt
from private_rag.prompt_sandbox.models import SandboxComparison, SandboxPromptVersion, SandboxRun
from private_rag.prompt_sandbox.schemas import (
    SandboxComparisonCreate,
    SandboxComparisonRead,
    SandboxComparisonRunExecute,
    SandboxPromptCopyToChatLibraryResponse,
    SandboxPromptVersionCreate,
    SandboxPromptVersionRead,
    SandboxRunCreate,
    SandboxRunRead,
)
from private_rag.repositories.models import Repository
from private_rag.repositories.schemas import PromptLibraryEntry, RepositorySettings
from private_rag.retrieval.rerankers import RerankerProvider
from private_rag.retrieval.schemas import RetrievalSearchRequest, RetrievalSearchResult
from private_rag.retrieval.service import search_retrieval
from private_rag.vector.embeddings import EmbeddingProviderSource
from private_rag.vector.store import VectorStore


def create_sandbox_prompt_version(
    session: Session,
    *,
    repository_id: str,
    request: SandboxPromptVersionCreate,
) -> SandboxPromptVersionRead | None:
    repository = session.get(Repository, repository_id)
    if repository is None or repository.settings is None:
        return None

    settings = RepositorySettings.model_validate(repository.settings.settings)
    body = request.body
    if request.source_chat_prompt_id is not None:
        source_prompt = _find_chat_prompt(settings, request.source_chat_prompt_id)
        if source_prompt is None:
            raise SandboxPromptSourceMissingError(request.source_chat_prompt_id)
        body = source_prompt.text
    if body is None:
        raise ValueError("body or source_chat_prompt_id is required")

    prompt = SandboxPromptVersion(
        repository_id=repository_id,
        name=request.name,
        body=body,
        notes=request.notes,
        source_chat_prompt_id=request.source_chat_prompt_id,
    )
    session.add(prompt)
    session.commit()
    session.refresh(prompt)
    return _prompt_read(prompt)


def list_sandbox_prompt_versions(
    session: Session,
    *,
    repository_id: str,
) -> list[SandboxPromptVersionRead] | None:
    repository = session.get(Repository, repository_id)
    if repository is None:
        return None
    prompts = list(
        session.scalars(
            select(SandboxPromptVersion)
            .where(SandboxPromptVersion.repository_id == repository_id)
            .order_by(SandboxPromptVersion.created_at, SandboxPromptVersion.name)
        )
    )
    return [_prompt_read(prompt) for prompt in prompts]


def get_sandbox_prompt_version(
    session: Session,
    *,
    repository_id: str,
    prompt_id: str,
) -> SandboxPromptVersionRead | None:
    prompt = session.get(SandboxPromptVersion, prompt_id)
    if prompt is None or prompt.repository_id != repository_id:
        return None
    return _prompt_read(prompt)


def delete_sandbox_prompt_version(
    session: Session,
    *,
    repository_id: str,
    prompt_id: str,
) -> bool | None:
    repository = session.get(Repository, repository_id)
    prompt = session.get(SandboxPromptVersion, prompt_id)
    if repository is None:
        return None
    if prompt is None or prompt.repository_id != repository_id:
        return False

    session.delete(prompt)
    session.commit()
    return True


def copy_sandbox_prompt_to_chat_library(
    session: Session,
    *,
    repository_id: str,
    prompt_id: str,
    name: str | None,
) -> SandboxPromptCopyToChatLibraryResponse | None:
    repository = session.get(Repository, repository_id)
    prompt = session.get(SandboxPromptVersion, prompt_id)
    if (
        repository is None
        or repository.settings is None
        or prompt is None
        or prompt.repository_id != repository_id
    ):
        return None

    settings = RepositorySettings.model_validate(repository.settings.settings)
    copied = PromptLibraryEntry(
        id=f"sandbox-{prompt.id}",
        name=name or prompt.name,
        text=prompt.body,
    )
    settings.prompt.library.append(copied)
    repository.settings.settings = settings.model_dump(mode="json")
    session.add(repository.settings)
    session.commit()
    return SandboxPromptCopyToChatLibraryResponse.model_validate(copied.model_dump())


def create_sandbox_run(
    session: Session,
    *,
    repository_id: str,
    request: SandboxRunCreate,
    store: VectorStore,
    embedder: EmbeddingProviderSource,
    reranker: RerankerProvider,
    llm: ChatLLM,
    comparison_id: str | None = None,
    comparison_index: int | None = None,
    label: str | None = None,
) -> SandboxRunRead | None:
    repository = session.get(Repository, repository_id)
    prompt = session.get(SandboxPromptVersion, request.prompt_version_id)
    if repository is None or prompt is None or prompt.repository_id != repository_id:
        return None

    started = perf_counter()
    retrieval_request = RetrievalSearchRequest(
        query=request.query,
        mode=request.retrieval_settings.mode,
        top_k=request.retrieval_settings.top_k,
        reranker_strategy=request.retrieval_settings.reranker_strategy,
    )
    retrieval = search_retrieval(
        session=session,
        repository_id=repository_id,
        request=retrieval_request,
        store=store,
        embedder=embedder,
        reranker=reranker,
    )
    if retrieval is None:
        return None

    completion = llm.complete(
        model=request.model,
        messages=build_chat_prompt(
            system_prompt=prompt.body,
            history=[],
            question=request.query,
            context_results=retrieval.results,
        ),
    )
    citations = map_citations(completion.content, retrieval.results)
    latency_ms = int((perf_counter() - started) * 1000)
    run = SandboxRun(
        repository_id=repository_id,
        prompt_version_id=prompt.id,
        comparison_id=comparison_id,
        comparison_index=comparison_index,
        label=label,
        query=request.query,
        model=completion.model,
        retrieval_settings=retrieval_request.model_dump(mode="json"),
        prompt_snapshot=_prompt_snapshot(prompt),
        context_entries=[result.model_dump(mode="json") for result in retrieval.results],
        retrieval_run_id=retrieval.run_id,
        answer=completion.content,
        citations=[citation.model_dump(mode="json") for citation in citations],
        metrics={
            "context_count": len(retrieval.results),
            "citation_count": len(citations),
        },
        latency_ms=latency_ms,
        status="completed",
    )
    prompt.used_by_run = True
    session.add(prompt)
    session.add(run)
    session.commit()
    session.refresh(run)
    return _run_read(run)


def create_sandbox_comparison(
    session: Session,
    *,
    repository_id: str,
    request: SandboxComparisonCreate,
    store: VectorStore,
    embedder: EmbeddingProviderSource,
    reranker: RerankerProvider,
    llm: ChatLLM,
) -> SandboxComparisonRead | None:
    repository = session.get(Repository, repository_id)
    if repository is None:
        return None

    comparison = SandboxComparison(
        repository_id=repository_id,
        query=request.query,
        status="running",
        expected_run_count=len(request.runs),
    )
    session.add(comparison)
    session.commit()
    session.refresh(comparison)

    runs: list[SandboxRunRead] = []
    if not request.execute_immediately:
        return _comparison_read(comparison, runs)

    for index, run_request in enumerate(request.runs):
        run = create_sandbox_comparison_run(
            session,
            repository_id=repository_id,
            comparison_id=comparison.id,
            request=SandboxComparisonRunExecute(
                label=run_request.label,
                comparison_index=index,
                prompt_version_id=run_request.prompt_version_id,
                model=run_request.model,
                retrieval_settings=run_request.retrieval_settings,
            ),
            store=store,
            embedder=embedder,
            reranker=reranker,
            llm=llm,
        )
        if run is None:
            return None
        runs.append(run)

    return _comparison_read(comparison, runs)


def create_sandbox_comparison_run(
    session: Session,
    *,
    repository_id: str,
    comparison_id: str,
    request: SandboxComparisonRunExecute,
    store: VectorStore,
    embedder: EmbeddingProviderSource,
    reranker: RerankerProvider,
    llm: ChatLLM,
) -> SandboxRunRead | None:
    comparison = session.get(SandboxComparison, comparison_id)
    if comparison is None or comparison.repository_id != repository_id:
        return None

    run = create_sandbox_run(
        session,
        repository_id=repository_id,
        request=SandboxRunCreate(
            prompt_version_id=request.prompt_version_id,
            query=comparison.query,
            model=request.model,
            retrieval_settings=request.retrieval_settings,
        ),
        store=store,
        embedder=embedder,
        reranker=reranker,
        llm=llm,
        comparison_id=comparison.id,
        comparison_index=request.comparison_index,
        label=request.label,
    )
    if run is None:
        return None

    completed_count = session.scalar(
        select(func.count())
        .select_from(SandboxRun)
        .where(SandboxRun.comparison_id == comparison.id)
    )
    if completed_count is not None and completed_count >= comparison.expected_run_count:
        comparison.status = "completed"
        session.add(comparison)
        session.commit()
        session.refresh(comparison)

    return run


def get_sandbox_run(
    session: Session,
    *,
    repository_id: str,
    run_id: str,
) -> SandboxRunRead | None:
    run = session.get(SandboxRun, run_id)
    if run is None or run.repository_id != repository_id:
        return None
    return _run_read(run)


def get_sandbox_comparison(
    session: Session,
    *,
    repository_id: str,
    comparison_id: str,
) -> SandboxComparisonRead | None:
    comparison = session.get(SandboxComparison, comparison_id)
    if comparison is None or comparison.repository_id != repository_id:
        return None
    run_rows = list(
        session.scalars(
            select(SandboxRun)
            .where(SandboxRun.comparison_id == comparison_id)
            .order_by(SandboxRun.comparison_index, SandboxRun.created_at)
        )
    )
    return _comparison_read(comparison, [_run_read(run) for run in run_rows])


class SandboxPromptSourceMissingError(ValueError):
    def __init__(self, prompt_id: str) -> None:
        super().__init__(f"Chat prompt not found: {prompt_id}")
        self.prompt_id = prompt_id


def _find_chat_prompt(
    settings: RepositorySettings,
    prompt_id: str,
) -> PromptLibraryEntry | None:
    for prompt in settings.prompt.library:
        if prompt.id == prompt_id:
            return prompt
    return None


def _prompt_read(prompt: SandboxPromptVersion) -> SandboxPromptVersionRead:
    return SandboxPromptVersionRead(
        id=prompt.id,
        repository_id=prompt.repository_id,
        name=prompt.name,
        body=prompt.body,
        notes=prompt.notes,
        source_chat_prompt_id=prompt.source_chat_prompt_id,
        used_by_run=prompt.used_by_run,
        created_at=prompt.created_at,
    )


def _prompt_snapshot(prompt: SandboxPromptVersion) -> dict[str, object]:
    return {
        "id": prompt.id,
        "name": prompt.name,
        "body": prompt.body,
        "notes": prompt.notes,
        "source_chat_prompt_id": prompt.source_chat_prompt_id,
        "created_at": prompt.created_at.isoformat(),
    }


def _run_read(run: SandboxRun) -> SandboxRunRead:
    return SandboxRunRead(
        id=run.id,
        repository_id=run.repository_id,
        prompt_version_id=run.prompt_version_id,
        comparison_id=run.comparison_id,
        comparison_index=run.comparison_index,
        label=run.label,
        query=run.query,
        model=run.model,
        retrieval_settings=ChatRetrievalSettings.model_validate(run.retrieval_settings),
        prompt_snapshot=run.prompt_snapshot,
        context_entries=[
            RetrievalSearchResult.model_validate(result) for result in run.context_entries
        ],
        retrieval_run_id=run.retrieval_run_id,
        answer=run.answer,
        citations=[ChatCitation.model_validate(citation) for citation in run.citations],
        metrics=run.metrics,
        latency_ms=run.latency_ms,
        status=run.status,
        created_at=run.created_at,
    )


def _comparison_read(
    comparison: SandboxComparison,
    runs: list[SandboxRunRead],
) -> SandboxComparisonRead:
    return SandboxComparisonRead(
        id=comparison.id,
        repository_id=comparison.repository_id,
        query=comparison.query,
        status=comparison.status,
        expected_run_count=comparison.expected_run_count,
        runs=runs,
        created_at=comparison.created_at,
    )
