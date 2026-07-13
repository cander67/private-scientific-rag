from __future__ import annotations

from fastapi import APIRouter, HTTPException

from private_rag.api.routes.chat import ChatLLMDependency
from private_rag.api.routes.repositories import DbSession
from private_rag.api.routes.retrieval import RerankerProviderDependency
from private_rag.api.routes.vector import EmbeddingProviderDependency, VectorStoreDependency
from private_rag.prompt_sandbox.schemas import (
    SandboxComparisonCreate,
    SandboxComparisonRead,
    SandboxComparisonRunExecute,
    SandboxPromptCopyToChatLibraryRequest,
    SandboxPromptCopyToChatLibraryResponse,
    SandboxPromptVersionCreate,
    SandboxPromptVersionRead,
    SandboxRunCreate,
    SandboxRunRead,
)
from private_rag.prompt_sandbox.service import (
    SandboxPromptSourceMissingError,
    copy_sandbox_prompt_to_chat_library,
    create_sandbox_comparison,
    create_sandbox_comparison_run,
    create_sandbox_prompt_version,
    create_sandbox_run,
    delete_sandbox_prompt_version,
    get_sandbox_comparison,
    get_sandbox_prompt_version,
    get_sandbox_run,
    list_sandbox_prompt_versions,
)
from private_rag.retrieval.rerankers import CrossEncoderModelMissingError
from private_rag.vector.service import VectorIndexMissingError
from private_rag.vector.store import VectorStoreError

router = APIRouter(
    prefix="/repositories/{repository_id}/prompt-sandbox",
    tags=["prompt-sandbox"],
)


@router.get("/prompts", response_model=list[SandboxPromptVersionRead])
def read_sandbox_prompt_versions(
    repository_id: str,
    session: DbSession,
) -> list[SandboxPromptVersionRead]:
    prompts = list_sandbox_prompt_versions(session, repository_id=repository_id)
    if prompts is None:
        raise HTTPException(status_code=404, detail="Repository not found")
    return prompts


@router.post("/prompts", response_model=SandboxPromptVersionRead)
def create_repository_sandbox_prompt_version(
    repository_id: str,
    request: SandboxPromptVersionCreate,
    session: DbSession,
) -> SandboxPromptVersionRead:
    try:
        prompt = create_sandbox_prompt_version(
            session,
            repository_id=repository_id,
            request=request,
        )
    except SandboxPromptSourceMissingError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    if prompt is None:
        raise HTTPException(status_code=404, detail="Repository not found")
    return prompt


@router.get("/prompts/{prompt_id}", response_model=SandboxPromptVersionRead)
def read_sandbox_prompt_version(
    repository_id: str,
    prompt_id: str,
    session: DbSession,
) -> SandboxPromptVersionRead:
    prompt = get_sandbox_prompt_version(
        session,
        repository_id=repository_id,
        prompt_id=prompt_id,
    )
    if prompt is None:
        raise HTTPException(status_code=404, detail="Sandbox prompt not found")
    return prompt


@router.delete("/prompts/{prompt_id}", status_code=204)
def delete_repository_sandbox_prompt_version(
    repository_id: str,
    prompt_id: str,
    session: DbSession,
) -> None:
    deleted = delete_sandbox_prompt_version(
        session,
        repository_id=repository_id,
        prompt_id=prompt_id,
    )
    if deleted is None:
        raise HTTPException(status_code=404, detail="Repository not found")
    if not deleted:
        raise HTTPException(status_code=404, detail="Sandbox prompt not found")


@router.post(
    "/prompts/{prompt_id}/copy-to-chat-library",
    response_model=SandboxPromptCopyToChatLibraryResponse,
)
def copy_repository_sandbox_prompt_to_chat_library(
    repository_id: str,
    prompt_id: str,
    request: SandboxPromptCopyToChatLibraryRequest,
    session: DbSession,
) -> SandboxPromptCopyToChatLibraryResponse:
    copied = copy_sandbox_prompt_to_chat_library(
        session,
        repository_id=repository_id,
        prompt_id=prompt_id,
        name=request.name,
    )
    if copied is None:
        raise HTTPException(status_code=404, detail="Sandbox prompt not found")
    return copied


@router.post("/runs", response_model=SandboxRunRead)
def create_repository_sandbox_run(
    repository_id: str,
    request: SandboxRunCreate,
    session: DbSession,
    store: VectorStoreDependency,
    embedder: EmbeddingProviderDependency,
    reranker: RerankerProviderDependency,
    llm: ChatLLMDependency,
) -> SandboxRunRead:
    try:
        run = create_sandbox_run(
            session,
            repository_id=repository_id,
            request=request,
            store=store,
            embedder=embedder,
            reranker=reranker,
            llm=llm,
        )
    except CrossEncoderModelMissingError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except VectorIndexMissingError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except (RuntimeError, VectorStoreError) as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    if run is None:
        raise HTTPException(status_code=404, detail="Sandbox prompt not found")
    return run


@router.get("/runs/{run_id}", response_model=SandboxRunRead)
def read_sandbox_run(
    repository_id: str,
    run_id: str,
    session: DbSession,
) -> SandboxRunRead:
    run = get_sandbox_run(
        session,
        repository_id=repository_id,
        run_id=run_id,
    )
    if run is None:
        raise HTTPException(status_code=404, detail="Sandbox run not found")
    return run


@router.post("/comparisons", response_model=SandboxComparisonRead)
def create_repository_sandbox_comparison(
    repository_id: str,
    request: SandboxComparisonCreate,
    session: DbSession,
    store: VectorStoreDependency,
    embedder: EmbeddingProviderDependency,
    reranker: RerankerProviderDependency,
    llm: ChatLLMDependency,
) -> SandboxComparisonRead:
    try:
        comparison = create_sandbox_comparison(
            session,
            repository_id=repository_id,
            request=request,
            store=store,
            embedder=embedder,
            reranker=reranker,
            llm=llm,
        )
    except CrossEncoderModelMissingError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except VectorIndexMissingError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except (RuntimeError, VectorStoreError) as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    if comparison is None:
        raise HTTPException(status_code=404, detail="Sandbox comparison not found")
    return comparison


@router.post("/comparisons/{comparison_id}/runs", response_model=SandboxRunRead)
def create_repository_sandbox_comparison_run(
    repository_id: str,
    comparison_id: str,
    request: SandboxComparisonRunExecute,
    session: DbSession,
    store: VectorStoreDependency,
    embedder: EmbeddingProviderDependency,
    reranker: RerankerProviderDependency,
    llm: ChatLLMDependency,
) -> SandboxRunRead:
    try:
        run = create_sandbox_comparison_run(
            session,
            repository_id=repository_id,
            comparison_id=comparison_id,
            request=request,
            store=store,
            embedder=embedder,
            reranker=reranker,
            llm=llm,
        )
    except CrossEncoderModelMissingError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except VectorIndexMissingError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except (RuntimeError, VectorStoreError) as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    if run is None:
        raise HTTPException(status_code=404, detail="Sandbox comparison or prompt not found")
    return run


@router.get("/comparisons/{comparison_id}", response_model=SandboxComparisonRead)
def read_sandbox_comparison(
    repository_id: str,
    comparison_id: str,
    session: DbSession,
) -> SandboxComparisonRead:
    comparison = get_sandbox_comparison(
        session,
        repository_id=repository_id,
        comparison_id=comparison_id,
    )
    if comparison is None:
        raise HTTPException(status_code=404, detail="Sandbox comparison not found")
    return comparison
