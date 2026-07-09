from __future__ import annotations

from typing import Protocol

from private_rag.retrieval.schemas import RetrievalSearchResult


class CrossEncoderModelMissingError(RuntimeError):
    def __init__(self, model_name: str) -> None:
        super().__init__(
            "Cross-encoder reranking requires a downloaded local model. "
            f"Download/cache '{model_name}' before using cross-encoder reranking, for example "
            '`uv run python -c "from sentence_transformers import CrossEncoder; '
            f"CrossEncoder('{model_name}')\"`."
        )


class RerankerProvider(Protocol):
    def score(
        self,
        query: str,
        results: list[RetrievalSearchResult],
        model_name: str,
    ) -> list[float]: ...


class SentenceTransformersCrossEncoderProvider:
    def score(
        self,
        query: str,
        results: list[RetrievalSearchResult],
        model_name: str,
    ) -> list[float]:
        try:
            from sentence_transformers import CrossEncoder

            model = CrossEncoder(model_name, local_files_only=True)
        except OSError as exc:
            raise CrossEncoderModelMissingError(model_name) from exc
        pairs = [(query, _result_text(result)) for result in results]
        scores = model.predict(pairs)
        return [float(score) for score in scores]


def _result_text(result: RetrievalSearchResult) -> str:
    return result.text_preview or _strip_marks(result.snippet or "") or result.document_title


def _strip_marks(value: str) -> str:
    return value.replace("<mark>", "").replace("</mark>", "")
