"""
sidecar/analysis/semantic_lyrics.py
Semantic worship lyric search — delegates load/query to SemanticBaseEngine.

Copyright note: meta.json stores only title, artist, and matched line groups.
No full copyrighted lyric text is stored. See scripts/build_lyrics_index.py.
"""

from __future__ import annotations

from typing import Any

from .semantic_base import SemanticBaseEngine, make_suggestion_id


class SemanticLyricsEngine(SemanticBaseEngine):

    def __init__(self, *args: Any, enabled: bool = True, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.enabled = enabled

    def load(self) -> None:
        if not self.enabled:
            return
        super().load()

    def _format_result(
        self, meta: dict, score: float, trigger_text: str
    ) -> dict[str, Any] | None:
        return {
            "id": make_suggestion_id("lyric", f"{meta.get('title', '')}:{score}"),
            "kind": "lyric",
            "songTitle": meta.get("title", "Unknown Song"),
            "artist": meta.get("artist"),
            "lines": meta.get("lines", []),
            "score": score,
            "triggerText": trigger_text[:120],
        }
