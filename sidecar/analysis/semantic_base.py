"""
sidecar/analysis/semantic_base.py
Shared base for FAISS-backed semantic search engines.
"""

from __future__ import annotations

import hashlib
import json
import logging
from pathlib import Path
from typing import Any

log = logging.getLogger("verseflow.semantic")

# multi-qa-MiniLM-L6-cos-v1 is trained for asymmetric semantic search:
# query (speech) vs document (Bible verse / lyric). Much better than the
# general-purpose all-MiniLM-L6-v2 for retrieval tasks.
DEFAULT_MODEL = "multi-qa-MiniLM-L6-cos-v1"


def make_suggestion_id(prefix: str, key: str) -> str:
    return hashlib.md5(f"{prefix}:{key}".encode()).hexdigest()[:12]


class SemanticBaseEngine:
    """
    Loads a FAISS IndexFlatIP + JSON metadata file and exposes a query()
    method.  Subclasses override `_format_result` to shape the output dict.
    """

    def __init__(
        self,
        index_path: str,
        meta_path: str,
        model_name: str = DEFAULT_MODEL,
        threshold: float = 0.60,
    ) -> None:
        self.index_path = Path(index_path)
        self.meta_path = Path(meta_path)
        self.model_name = model_name
        self.threshold = threshold
        self._index = None
        self._meta: list[dict] = []
        self._model = None
        self._ready = False

    # ── Startup ───────────────────────────────────────────────────────────────

    def load(self) -> None:
        if not self.index_path.exists() or not self.meta_path.exists():
            log.warning(
                "%s index not found at %s — run the appropriate build script.",
                self.__class__.__name__,
                self.index_path,
            )
            return

        try:
            import faiss  # type: ignore[import]
            from sentence_transformers import SentenceTransformer  # type: ignore[import]

            log.info("Loading FAISS index from %s", self.index_path)
            self._index = faiss.read_index(str(self.index_path))

            with open(self.meta_path, encoding="utf-8") as f:
                self._meta = json.load(f)

            log.info("Loading embedding model '%s'", self.model_name)
            self._model = SentenceTransformer(self.model_name)
            self._ready = True
            log.info(
                "%s ready — %d entries indexed",
                self.__class__.__name__,
                self._index.ntotal,
            )
        except Exception as e:
            log.error("Failed to load %s: %s", self.__class__.__name__, e)

    # ── Query ─────────────────────────────────────────────────────────────────

    def query(
        self, text: str, top_k: int = 5, threshold: float | None = None
    ) -> list[dict[str, Any]]:
        if not self._ready:
            return []

        cutoff = threshold if threshold is not None else self.threshold
        embedding = self._model.encode(  # type: ignore[union-attr]
            [text], normalize_embeddings=True, show_progress_bar=False
        ).astype("float32")

        scores, indices = self._index.search(embedding, top_k)  # type: ignore[union-attr]

        results = []
        for score, idx in zip(scores[0], indices[0]):
            if idx < 0 or float(score) < cutoff:
                continue
            result = self._format_result(self._meta[idx], float(score), text)
            if result:
                results.append(result)
        return results

    # ── Subclass hook ─────────────────────────────────────────────────────────

    def _format_result(
        self, meta: dict, score: float, trigger_text: str
    ) -> dict[str, Any] | None:
        raise NotImplementedError
