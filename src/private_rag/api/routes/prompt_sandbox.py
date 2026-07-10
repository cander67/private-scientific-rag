from __future__ import annotations

from fastapi import APIRouter, HTTPException

from private_rag.api.routes.repositories import DbSession
from private_rag.prompt_sandbox.schemas import (
    SandboxPromptCopyToChatLibraryRequest,
    SandboxPromptCopyToChatLibraryResponse,
    SandboxPromptVersionCreate,
    SandboxPromptVersionRead,
)
from private_rag.prompt_sandbox.service import (
    SandboxPromptSourceMissingError,
    copy_sandbox_prompt_to_chat_library,
    create_sandbox_prompt_version,
    get_sandbox_prompt_version,
    list_sandbox_prompt_versions,
)

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
