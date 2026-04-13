"""
sidecar/tests/test_bible_lookup.py
───────────────────────────────────────────────────────────────────────────────
Unit tests for BibleLookup.

Run from the project root:
    py -3.13 -m pytest sidecar/tests/test_bible_lookup.py -v
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from unittest.mock import MagicMock, mock_open, patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from analysis.bible_lookup import BibleLookup

# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------

SAMPLE_VERSES = [
    {"book": "John",    "chapter": 3, "verse": 16, "text": "For God so loved the world, that he gave his only begotten Son", "translation": "KJV"},
    {"book": "John",    "chapter": 3, "verse": 17, "text": "For God sent not his Son into the world to condemn the world",   "translation": "KJV"},
    {"book": "Genesis", "chapter": 1, "verse": 1,  "text": "In the beginning God created the heaven and the earth",          "translation": "KJV"},
    {"book": "Psalms",  "chapter": 23, "verse": 1, "text": "The LORD is my shepherd; I shall not want",                      "translation": "KJV"},
    {"book": "Psalms",  "chapter": 23, "verse": 2, "text": "He maketh me to lie down in green pastures",                    "translation": "KJV"},
]


def _make_loaded_lookup(tmp_path: Path) -> BibleLookup:
    """Write SAMPLE_VERSES to a temp file and return a loaded BibleLookup."""
    meta_file = tmp_path / "meta.json"
    meta_file.write_text(json.dumps(SAMPLE_VERSES), encoding="utf-8")
    lookup = BibleLookup(str(meta_file))
    lookup.load()
    return lookup


# ---------------------------------------------------------------------------
# load()
# ---------------------------------------------------------------------------

class TestLoad:
    def test_loads_all_verses(self, tmp_path):
        lookup = _make_loaded_lookup(tmp_path)
        entry = lookup.get("John", 3, 16)
        assert entry is not None
        assert "God so loved" in entry["text"]

    def test_missing_file_does_not_raise(self, tmp_path):
        lookup = BibleLookup(str(tmp_path / "nonexistent.json"))
        lookup.load()   # should log warning, not raise
        assert lookup.get("John", 3, 16) is None

    def test_uses_kjv_translation_default(self, tmp_path):
        # Verses without explicit translation key get "KJV".
        verses = [{"book": "John", "chapter": 1, "verse": 1, "text": "In the beginning was the Word"}]
        meta_file = tmp_path / "meta.json"
        meta_file.write_text(json.dumps(verses), encoding="utf-8")
        lookup = BibleLookup(str(meta_file))
        lookup.load()
        assert lookup.get("John", 1, 1)["translation"] == "KJV"

    def test_load_is_idempotent(self, tmp_path):
        """Calling load() twice shouldn't raise or double-count."""
        lookup = _make_loaded_lookup(tmp_path)
        lookup.load()
        assert lookup.get("John", 3, 16) is not None


# ---------------------------------------------------------------------------
# get()
# ---------------------------------------------------------------------------

class TestGet:
    def test_exact_lookup(self, tmp_path):
        lookup = _make_loaded_lookup(tmp_path)
        entry = lookup.get("John", 3, 16)
        assert entry["text"].startswith("For God so loved")

    def test_case_insensitive_book(self, tmp_path):
        lookup = _make_loaded_lookup(tmp_path)
        assert lookup.get("john", 3, 16) is not None
        assert lookup.get("JOHN", 3, 16) is not None

    def test_missing_verse_returns_none(self, tmp_path):
        lookup = _make_loaded_lookup(tmp_path)
        assert lookup.get("John", 99, 99) is None

    def test_not_loaded_returns_none(self, tmp_path):
        meta_file = tmp_path / "meta.json"
        meta_file.write_text(json.dumps(SAMPLE_VERSES), encoding="utf-8")
        lookup = BibleLookup(str(meta_file))
        # Don't call load()
        assert lookup.get("John", 3, 16) is None

    def test_genesis_lookup(self, tmp_path):
        lookup = _make_loaded_lookup(tmp_path)
        entry = lookup.get("Genesis", 1, 1)
        assert "beginning" in entry["text"]

    def test_psalms_lookup(self, tmp_path):
        lookup = _make_loaded_lookup(tmp_path)
        entry = lookup.get("Psalms", 23, 1)
        assert "shepherd" in entry["text"]


# ---------------------------------------------------------------------------
# get_range()
# ---------------------------------------------------------------------------

class TestGetRange:
    def test_full_range(self, tmp_path):
        lookup = _make_loaded_lookup(tmp_path)
        entries = lookup.get_range("John", 3, 16, 17)
        assert len(entries) == 2
        assert "God so loved" in entries[0]["text"]
        assert "condemn" in entries[1]["text"]

    def test_single_verse_range(self, tmp_path):
        lookup = _make_loaded_lookup(tmp_path)
        entries = lookup.get_range("John", 3, 16, 16)
        assert len(entries) == 1

    def test_partial_range_skips_missing(self, tmp_path):
        """Verses 1-2 in Psalms 23 exist; verse 3 does not — only 2 returned."""
        lookup = _make_loaded_lookup(tmp_path)
        entries = lookup.get_range("Psalms", 23, 1, 3)
        assert len(entries) == 2

    def test_range_not_loaded_returns_empty(self, tmp_path):
        meta_file = tmp_path / "meta.json"
        meta_file.write_text(json.dumps(SAMPLE_VERSES), encoding="utf-8")
        lookup = BibleLookup(str(meta_file))
        assert lookup.get_range("John", 3, 16, 17) == []

    def test_range_order_is_preserved(self, tmp_path):
        lookup = _make_loaded_lookup(tmp_path)
        entries = lookup.get_range("Psalms", 23, 1, 2)
        assert "shepherd" in entries[0]["text"]
        assert "green pastures" in entries[1]["text"]
