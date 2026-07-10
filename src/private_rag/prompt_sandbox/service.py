from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from private_rag.prompt_sandbox.models import SandboxPromptVersion
from private_rag.prompt_sandbox.schemas import (
    SandboxPromptCopyToChatLibraryResponse,
    SandboxPromptVersionCreate,
    SandboxPromptVersionRead,
)
from private_rag.repositories.models import Repository
from private_rag.repositories.schemas import PromptLibraryEntry, RepositorySettings


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
