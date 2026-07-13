from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from private_rag import __version__
from private_rag.api.routes.chat import router as chat_router
from private_rag.api.routes.documents import router as documents_router
from private_rag.api.routes.health import router as health_router
from private_rag.api.routes.prompt_sandbox import router as prompt_sandbox_router
from private_rag.api.routes.repositories import router as repositories_router
from private_rag.api.routes.retrieval import router as retrieval_router
from private_rag.api.routes.search import router as search_router
from private_rag.api.routes.vector import router as vector_router
from private_rag.core.settings import get_settings


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title="Private Scientific RAG",
        version=__version__,
        docs_url="/docs",
        redoc_url="/redoc",
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(health_router)
    app.include_router(repositories_router)
    app.include_router(documents_router)
    app.include_router(search_router)
    app.include_router(vector_router)
    app.include_router(retrieval_router)
    app.include_router(chat_router)
    app.include_router(prompt_sandbox_router)
    return app


app = create_app()
