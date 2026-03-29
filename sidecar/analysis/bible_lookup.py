"""
sidecar/analysis/bible_lookup.py
───────────────────────────────────────────────────────────────────────────────
Loads meta.json produced by build_bible_index.py into a fast in-memory dict
so the VerseDetector can populate verse text without hitting disk per-lookup.

Key structure:
    {
        "genesis:1:1":  {"text": "In the beginning...", "translation": "KJV"},
        "john:3:16":    {"text": "For God so loved...",  "translation": "KJV"},
        ...
    }

The key is always lowercase: `{book_lower}:{chapter}:{verse}`.

Load time:  ~50 ms for 31 k KJV verses.
Memory:     ~12 MB.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import TypedDict

log = logging.getLogger("verseflow.bible_lookup")


class VerseEntry(TypedDict):
    text: str
    translation: str


class BibleLookup:
    def __init__(self, meta_path: str) -> None:
        self._meta_path = Path(meta_path)
        self._index: dict[str, VerseEntry] = {}
        self._ready = False

    def load(self) -> None:
        if not self._meta_path.exists():
            log.warning("Bible meta not found at %s — verse text lookup disabled", self._meta_path)
            return

        with open(self._meta_path, encoding="utf-8") as f:
            verses: list[dict] = json.load(f)

        for v in verses:
            key = f"{v['book'].lower()}:{v['chapter']}:{v['verse']}"
            self._index[key] = VerseEntry(
                text=v["text"],
                translation=v.get("translation", "KJV"),
            )

        self._ready = True
        log.info("BibleLookup loaded %d verses from %s", len(self._index), self._meta_path)

    def get(self, book: str, chapter: int, verse: int) -> VerseEntry | None:
        """Look up a single verse. book is the full canonical name e.g. 'John'."""
        if not self._ready:
            return None
        return self._index.get(f"{book.lower()}:{chapter}:{verse}")

    def get_range(self, book: str, chapter: int, verse_start: int, verse_end: int) -> list[VerseEntry]:
        """Look up a verse range, e.g. John 3:16-17."""
        if not self._ready:
            return []
        return [
            entry
            for v in range(verse_start, verse_end + 1)
            if (entry := self._index.get(f"{book.lower()}:{chapter}:{v}")) is not None
        ]
