"""
sidecar/analysis/semantic_bible.py
Semantic Bible verse search — delegates load/query to SemanticBaseEngine.
"""

from __future__ import annotations

from typing import Any

from .semantic_base import SemanticBaseEngine, make_suggestion_id


class SemanticBibleEngine(SemanticBaseEngine):

    def _format_result(
        self, meta: dict, score: float, trigger_text: str
    ) -> dict[str, Any] | None:
        ref_str = f"{meta['book']} {meta['chapter']}:{meta['verse']}"
        return {
            "id": make_suggestion_id("sem", f"{ref_str}:{meta.get('translation', 'KJV')}"),
            "kind": "semantic",
            "verse": {
                "reference": {
                    "book": meta["book"],
                    "chapter": meta["chapter"],
                    "verse": meta["verse"],
                    "verseEnd": meta.get("verse_end"),
                },
                "translation": meta.get("translation", "KJV"),
                "text": meta["text"],
            },
            "score": score,
            "triggerText": trigger_text[:120],
        }
