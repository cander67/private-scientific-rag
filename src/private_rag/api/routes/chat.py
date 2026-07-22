from __future__ import annotations

from collections.abc import Generator
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException

from private_rag.api.routes.repositories import DbSession
from private_rag.api.routes.retrieval import RerankerProviderDependency
from private_rag.api.routes.vector import EmbeddingProviderDependency, VectorStoreDependency
from private_rag.chat.llm import ChatLLM, OllamaChatLLM, OllamaUnavailableError
from private_rag.chat.schemas import (
    ChatModelRegistryResponse,
    ChatModelSmokeResponse,
    ChatQuestionRequest,
    ChatQuestionResponse,
    ChatReadinessResponse,
    ChatSessionCreate,
    ChatSessionRead,
)
from private_rag.chat.service import (
    ask_chat_question,
    chat_readiness,
    clear_chat_sessions,
    create_chat_session,
    delete_chat_session,
    get_chat_session,
    list_chat_sessions,
    model_registry,
)
from private_rag.core.settings import get_settings
from private_rag.retrieval.rerankers import CrossEncoderModelMissingError
from private_rag.vector.service import VectorIndexMissingError
from private_rag.vector.store import VectorStoreError

router = APIRouter(prefix="/repositories/{repository_id}/chat", tags=["chat"])


def get_chat_llm() -> Generator[ChatLLM, None, None]:
    settings = get_settings()
    yield OllamaChatLLM(base_url=settings.ollama_base_url)


ChatLLMDependency = Annotated[ChatLLM, Depends(get_chat_llm)]


@router.get("/models", response_model=ChatModelRegistryResponse)
def read_chat_models() -> ChatModelRegistryResponse:
    return model_registry(get_settings().default_llm)


@router.post("/models/smoke", response_model=ChatModelSmokeResponse)
def smoke_chat_model(llm: ChatLLMDependency) -> ChatModelSmokeResponse:
    model = get_settings().default_llm
    try:
        completion = llm.smoke(model=model)
    except OllamaUnavailableError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return ChatModelSmokeResponse(model=completion.model, ok=True, response=completion.content)


@router.get("/readiness", response_model=ChatReadinessResponse)
def read_chat_readiness(
    repository_id: str,
    session: DbSession,
    llm: ChatLLMDependency,
) -> ChatReadinessResponse:
    response = chat_readiness(
        session,
        repository_id=repository_id,
        llm=llm,
    )
    if response is None:
        raise HTTPException(status_code=404, detail="Repository not found")
    return response


@router.get("/sessions", response_model=list[ChatSessionRead])
def read_chat_sessions(repository_id: str, session: DbSession) -> list[ChatSessionRead]:
    sessions = list_chat_sessions(session, repository_id=repository_id)
    if sessions is None:
        raise HTTPException(status_code=404, detail="Repository not found")
    return sessions


@router.post("/sessions", response_model=ChatSessionRead)
def create_repository_chat_session(
    repository_id: str,
    request: ChatSessionCreate,
    session: DbSession,
) -> ChatSessionRead:
    chat_session = create_chat_session(
        session,
        repository_id=repository_id,
        title=request.title,
        model=request.model,
        retrieval_settings=request.retrieval_settings,
    )
    if chat_session is None:
        raise HTTPException(status_code=404, detail="Repository not found")
    return chat_session


@router.delete("/sessions", status_code=204)
def clear_repository_chat_sessions(repository_id: str, session: DbSession) -> None:
    deleted = clear_chat_sessions(session, repository_id=repository_id)
    if deleted is None:
        raise HTTPException(status_code=404, detail="Repository not found")


@router.get("/sessions/{chat_session_id}", response_model=ChatSessionRead)
def read_chat_session(
    repository_id: str,
    chat_session_id: str,
    session: DbSession,
) -> ChatSessionRead:
    chat_session = get_chat_session(
        session,
        repository_id=repository_id,
        chat_session_id=chat_session_id,
    )
    if chat_session is None:
        raise HTTPException(status_code=404, detail="Chat session not found")
    return chat_session


@router.delete("/sessions/{chat_session_id}", status_code=204)
def delete_repository_chat_session(
    repository_id: str,
    chat_session_id: str,
    session: DbSession,
) -> None:
    deleted = delete_chat_session(
        session,
        repository_id=repository_id,
        chat_session_id=chat_session_id,
    )
    if deleted is None:
        raise HTTPException(status_code=404, detail="Repository not found")
    if deleted is False:
        raise HTTPException(status_code=404, detail="Chat session not found")


@router.post("/sessions/{chat_session_id}/messages", response_model=ChatQuestionResponse)
def ask_repository_chat_question(
    repository_id: str,
    chat_session_id: str,
    request: ChatQuestionRequest,
    session: DbSession,
    store: VectorStoreDependency,
    embedder: EmbeddingProviderDependency,
    reranker: RerankerProviderDependency,
    llm: ChatLLMDependency,
) -> ChatQuestionResponse:
    try:
        response = ask_chat_question(
            session,
            repository_id=repository_id,
            chat_session_id=chat_session_id,
            question=request.content,
            store=store,
            embedder=embedder,
            reranker=reranker,
            llm=llm,
            retrieval_settings=request.retrieval_settings,
        )
    except CrossEncoderModelMissingError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except VectorIndexMissingError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except (OllamaUnavailableError, RuntimeError, VectorStoreError) as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    if response is None:
        raise HTTPException(status_code=404, detail="Chat session not found")
    return response
