from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from private_rag.db.base import Base


def new_uuid() -> str:
    return str(uuid.uuid4())


class SandboxPromptVersion(Base):
    __tablename__ = "sandbox_prompt_versions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    repository_id: Mapped[str] = mapped_column(
        ForeignKey("repositories.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    source_chat_prompt_id: Mapped[str | None] = mapped_column(String(120), nullable=True)
    used_by_run: Mapped[bool] = mapped_column(default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
