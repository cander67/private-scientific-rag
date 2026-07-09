from __future__ import annotations

from sqlalchemy import delete, func, select, text
from sqlalchemy.orm import Session

from private_rag.chat.citations import map_citations
from private_rag.chat.llm import MODEL_REGISTRY, ChatLLM, ChatMessage
from private_rag.chat.models import ChatMessageRow, ChatSession
from private_rag.chat.schemas import (
    ChatCitation,
    ChatMessageRead,
    ChatModelRegistryResponse,
    ChatQuestionResponse,
    ChatReadinessItem,
    ChatReadinessResponse,
    ChatRetrievalSettings,
    ChatSessionRead,
)
from private_rag.ingestion.models import DocumentChunk
from private_rag.repositories.models import Repository
from private_rag.repositories.schemas import RepositorySettings
from private_rag.retrieval.rerankers import RerankerProvider
from private_rag.retrieval.schemas import RetrievalSearchRequest, RetrievalSearchResult
from private_rag.retrieval.service import search_retrieval
from private_rag.search.service import FTS_TABLE
from private_rag.vector.embeddings import EmbeddingProvider
from private_rag.vector.models import EmbeddingRun
from private_rag.vector.store import VectorStore

DEFAULT_CHAT_TOP_K = 6
MAX_HISTORY_MESSAGES = 8


def model_registry(default_model: str) -> ChatModelRegistryResponse:
    return ChatModelRegistryResponse(default_model=default_model, models=MODEL_REGISTRY)


def create_chat_session(
    session: Session,
    *,
    repository_id: str,
    title: str | None,
    model: str | None,
    retrieval_settings: ChatRetrievalSettings | None = None,
) -> ChatSessionRead | None:
    repository = session.get(Repository, repository_id)
    if repository is None or repository.settings is None:
        return None
    settings = RepositorySettings.model_validate(repository.settings.settings)
    chat_session = ChatSession(
        repository_id=repository_id,
        title=title or "New chat",
        model=model or settings.model.ollama_chat_model,
        retrieval_settings=(retrieval_settings or ChatRetrievalSettings()).model_dump(mode="json"),
        prompt_id=settings.prompt.active_chat_prompt_id,
    )
    session.add(chat_session)
    session.commit()
    session.refresh(chat_session)
    return _session_read(chat_session)


def list_chat_sessions(session: Session, *, repository_id: str) -> list[ChatSessionRead] | None:
    repository = session.get(Repository, repository_id)
    if repository is None:
        return None
    chat_sessions = list(
        session.scalars(
            select(ChatSession)
            .where(ChatSession.repository_id == repository_id)
            .order_by(ChatSession.updated_at.desc(), ChatSession.created_at.desc())
        )
    )
    return [_session_read(chat_session, include_messages=False) for chat_session in chat_sessions]


def get_chat_session(
    session: Session,
    *,
    repository_id: str,
    chat_session_id: str,
) -> ChatSessionRead | None:
    chat_session = session.get(ChatSession, chat_session_id)
    if chat_session is None or chat_session.repository_id != repository_id:
        return None
    return _session_read(chat_session)


def delete_chat_session(
    session: Session,
    *,
    repository_id: str,
    chat_session_id: str,
) -> bool | None:
    repository = session.get(Repository, repository_id)
    if repository is None:
        return None
    chat_session = session.get(ChatSession, chat_session_id)
    if chat_session is None or chat_session.repository_id != repository_id:
        return False
    session.delete(chat_session)
    session.commit()
    return True


def clear_chat_sessions(session: Session, *, repository_id: str) -> int | None:
    repository = session.get(Repository, repository_id)
    if repository is None:
        return None
    session_ids = list(
        session.scalars(select(ChatSession.id).where(ChatSession.repository_id == repository_id))
    )
    session.execute(delete(ChatSession).where(ChatSession.repository_id == repository_id))
    session.commit()
    return len(session_ids)


def ask_chat_question(
    session: Session,
    *,
    repository_id: str,
    chat_session_id: str,
    question: str,
    store: VectorStore,
    embedder: EmbeddingProvider,
    reranker: RerankerProvider,
    llm: ChatLLM,
    retrieval_settings: ChatRetrievalSettings | None = None,
) -> ChatQuestionResponse | None:
    chat_session = session.get(ChatSession, chat_session_id)
    repository = session.get(Repository, repository_id)
    if (
        chat_session is None
        or repository is None
        or repository.settings is None
        or chat_session.repository_id != repository_id
    ):
        return None

    settings = RepositorySettings.model_validate(repository.settings.settings)
    resolved_retrieval_settings = retrieval_settings or ChatRetrievalSettings.model_validate(
        chat_session.retrieval_settings
    )
    chat_session.retrieval_settings = resolved_retrieval_settings.model_dump(mode="json")
    session.add(chat_session)
    session.commit()
    session.refresh(chat_session)
    user_message = _append_message(
        session,
        chat_session=chat_session,
        role="user",
        content=question,
        retrieval_run_id=None,
        citations=[],
    )

    retrieval = search_retrieval(
        session=session,
        repository_id=repository_id,
        request=RetrievalSearchRequest(
            query=question,
            mode=resolved_retrieval_settings.mode,
            top_k=resolved_retrieval_settings.top_k,
            reranker_strategy=resolved_retrieval_settings.reranker_strategy,
        ),
        store=store,
        embedder=embedder,
        reranker=reranker,
    )
    if retrieval is None:
        return None

    prompt_messages = build_chat_prompt(
        system_prompt=settings.prompt.active_chat_prompt.text,
        history=[
            ChatMessage(role=message.role, content=message.content)
            for message in chat_session.messages
            if message.id != user_message.id
        ],
        question=question,
        context_results=retrieval.results,
    )
    completion = llm.complete(model=chat_session.model, messages=prompt_messages)
    citations = map_citations(completion.content, retrieval.results)
    assistant_message = _append_message(
        session,
        chat_session=chat_session,
        role="assistant",
        content=completion.content,
        retrieval_run_id=retrieval.run_id,
        citations=[citation.model_dump(mode="json") for citation in citations],
    )
    session.refresh(chat_session)
    return ChatQuestionResponse(
        session=_session_read(chat_session),
        user_message=_message_read(user_message),
        assistant_message=_message_read(assistant_message),
    )


def build_chat_prompt(
    *,
    system_prompt: str,
    history: list[ChatMessage],
    question: str,
    context_results: list[RetrievalSearchResult],
) -> list[ChatMessage]:
    context_lines = [
        _context_line(index=index, result=result)
        for index, result in enumerate(context_results, start=1)
    ]
    messages = [
        ChatMessage(
            role="system",
            content=(
                f"{system_prompt}\n\n"
                "Repository context follows. Cite facts using only these citation IDs.\n"
                + "\n".join(context_lines)
            ),
        )
    ]
    messages.extend(history[-MAX_HISTORY_MESSAGES:])
    messages.append(ChatMessage(role="user", content=question))
    return messages


def chat_readiness(
    session: Session,
    *,
    repository_id: str,
    llm: ChatLLM,
    model: str,
) -> ChatReadinessResponse | None:
    repository = session.get(Repository, repository_id)
    if repository is None:
        return None

    parsed_chunks = _parsed_chunk_count(session, repository_id)
    full_text_count = _full_text_count(session, repository_id)
    embedding_run = session.scalar(
        select(EmbeddingRun).where(EmbeddingRun.repository_id == repository_id)
    )
    vector_ready = (
        parsed_chunks > 0
        and embedding_run is not None
        and embedding_run.status == "indexed"
        and embedding_run.chunk_count > 0
    )
    try:
        completion = llm.smoke(model=model)
        local_model = ChatReadinessItem(
            ready=bool(completion.content.strip()),
            message=f"{completion.model} responded",
            model=completion.model,
        )
    except RuntimeError as exc:
        local_model = ChatReadinessItem(ready=False, message=str(exc), model=model)

    full_text = ChatReadinessItem(
        ready=parsed_chunks > 0 and full_text_count > 0,
        message=_full_text_readiness_message(parsed_chunks, full_text_count),
        indexed_chunks=full_text_count,
    )
    vector = ChatReadinessItem(
        ready=vector_ready,
        message=_vector_readiness_message(parsed_chunks, embedding_run),
        indexed_chunks=embedding_run.chunk_count if embedding_run is not None else 0,
        model=embedding_run.model if embedding_run is not None else None,
    )
    return ChatReadinessResponse(
        repository_id=repository_id,
        parsed_chunks=parsed_chunks,
        full_text=full_text,
        vector=vector,
        local_model=local_model,
        ready_for_chat=parsed_chunks > 0 and full_text.ready and vector.ready and local_model.ready,
    )


def _context_line(*, index: int, result: RetrievalSearchResult) -> str:
    text = result.snippet or result.text_preview or ""
    page = _page_label(result.page_start, result.page_end)
    section_label = f", section {result.section}" if result.section else ""
    return (
        f"[{index}] {result.document_title}, chunk {result.chunk_index}"
        f"{page}{section_label}: {text}"
    )


def _page_label(page_start: object, page_end: object) -> str:
    if page_start is None:
        return ""
    if page_end is None or page_end == page_start:
        return f", page {page_start}"
    return f", pages {page_start}-{page_end}"


def _append_message(
    session: Session,
    *,
    chat_session: ChatSession,
    role: str,
    content: str,
    retrieval_run_id: str | None,
    citations: list[dict[str, object]],
) -> ChatMessageRow:
    message = ChatMessageRow(
        session_id=chat_session.id,
        repository_id=chat_session.repository_id,
        sequence=len(chat_session.messages) + 1,
        role=role,
        content=content,
        retrieval_run_id=retrieval_run_id,
        citations=citations,
    )
    session.add(message)
    session.commit()
    session.refresh(message)
    session.refresh(chat_session)
    return message


def _default_retrieval_settings() -> dict[str, object]:
    return ChatRetrievalSettings(top_k=DEFAULT_CHAT_TOP_K).model_dump(mode="json")


def _full_text_count(session: Session, repository_id: str) -> int:
    try:
        value = session.scalar(
            text(f"SELECT COUNT(*) FROM {FTS_TABLE} WHERE repository_id = :repository_id"),
            {"repository_id": repository_id},
        )
    except Exception:
        session.rollback()
        return 0
    return int(value or 0)


def _parsed_chunk_count(session: Session, repository_id: str) -> int:
    value = session.scalar(
        select(func.count())
        .select_from(DocumentChunk)
        .where(DocumentChunk.repository_id == repository_id)
    )
    return int(value or 0)


def _full_text_readiness_message(parsed_chunks: int, indexed_chunks: int) -> str:
    if parsed_chunks == 0:
        return "No parsed chunks are available to index"
    if indexed_chunks == 0:
        return "Full-text index has not been rebuilt"
    if indexed_chunks < parsed_chunks:
        return f"{indexed_chunks} of {parsed_chunks} full-text chunks indexed"
    return f"{indexed_chunks} full-text chunks indexed"


def _vector_readiness_message(parsed_chunks: int, embedding_run: EmbeddingRun | None) -> str:
    if parsed_chunks == 0:
        return "No parsed chunks are available to embed/index"
    if embedding_run is None:
        return "Vector index has not been rebuilt"
    if embedding_run.status != "indexed":
        return f"Vector index status is {embedding_run.status}"
    if embedding_run.chunk_count == 0:
        return "Vector index exists but contains zero chunks"
    if embedding_run.chunk_count < parsed_chunks:
        return f"{embedding_run.chunk_count} of {parsed_chunks} vector chunks indexed"
    return f"{embedding_run.chunk_count} vector chunks indexed"


def _session_read(
    chat_session: ChatSession,
    *,
    include_messages: bool = True,
) -> ChatSessionRead:
    return ChatSessionRead(
        id=chat_session.id,
        repository_id=chat_session.repository_id,
        title=chat_session.title,
        model=chat_session.model,
        retrieval_settings=ChatRetrievalSettings.model_validate(chat_session.retrieval_settings),
        prompt_id=chat_session.prompt_id,
        created_at=chat_session.created_at,
        updated_at=chat_session.updated_at,
        messages=(
            [_message_read(message) for message in chat_session.messages]
            if include_messages
            else []
        ),
    )


def _message_read(message: ChatMessageRow) -> ChatMessageRead:
    return ChatMessageRead(
        id=message.id,
        session_id=message.session_id,
        sequence=message.sequence,
        role="assistant" if message.role == "assistant" else "user",
        content=message.content,
        retrieval_run_id=message.retrieval_run_id,
        citations=[ChatCitation.model_validate(citation) for citation in message.citations],
        created_at=message.created_at,
    )
