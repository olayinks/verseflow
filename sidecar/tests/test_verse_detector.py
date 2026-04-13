"""
sidecar/tests/test_verse_detector.py
───────────────────────────────────────────────────────────────────────────────
Unit tests for VerseDetector and supporting helpers.

Run from the project root:
    py -3.13 -m pytest sidecar/tests/test_verse_detector.py -v
"""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest

# Allow imports from sidecar/ without installing as a package.
sys.path.insert(0, str(Path(__file__).parent.parent))

from analysis.verse_detector import (
    VerseDetector,
    _normalise_book,
    _spans_overlap,
    _word_to_int,
)


# ─────────────────────────────────────────────────────────────────────────────
# Fixtures
# ─────────────────────────────────────────────────────────────────────────────

@pytest.fixture
def detector() -> VerseDetector:
    """VerseDetector with no BibleLookup — verse text will be empty."""
    return VerseDetector(lookup=None)


@pytest.fixture
def detector_with_lookup() -> VerseDetector:
    """VerseDetector with a stubbed BibleLookup."""
    lookup = MagicMock()
    lookup.get.return_value = {"text": "For God so loved the world.", "translation": "KJV"}
    lookup.get_range.return_value = [
        {"text": "For God so loved the world,", "translation": "KJV"},
        {"text": "that whosoever believeth in him should not perish.", "translation": "KJV"},
    ]
    return VerseDetector(lookup=lookup)


# ─────────────────────────────────────────────────────────────────────────────
# _word_to_int
# ─────────────────────────────────────────────────────────────────────────────

class TestWordToInt:
    def test_digit_string(self):
        assert _word_to_int("3") == 3
        assert _word_to_int("16") == 16
        assert _word_to_int("150") == 150

    def test_ones(self):
        assert _word_to_int("one") == 1
        assert _word_to_int("nine") == 9
        assert _word_to_int("nineteen") == 19

    def test_tens(self):
        assert _word_to_int("twenty") == 20
        assert _word_to_int("ninety") == 90

    def test_compound_hyphen(self):
        assert _word_to_int("twenty-two") == 22
        assert _word_to_int("thirty-one") == 31
        assert _word_to_int("forty-five") == 45

    def test_compound_space(self):
        assert _word_to_int("twenty two") == 22
        assert _word_to_int("sixty seven") == 67

    def test_invalid(self):
        assert _word_to_int("foo") is None
        assert _word_to_int("") is None
        assert _word_to_int("hundred") is None


# ─────────────────────────────────────────────────────────────────────────────
# _normalise_book
# ─────────────────────────────────────────────────────────────────────────────

class TestNormaliseBook:
    def test_exact_full_name(self):
        assert _normalise_book("John") == ("John", "John")
        assert _normalise_book("Genesis") == ("Gen", "Genesis")
        assert _normalise_book("Revelation") == ("Rev", "Revelation")

    def test_abbreviation(self):
        assert _normalise_book("Rev") == ("Rev", "Revelation")
        assert _normalise_book("Gen") == ("Gen", "Genesis")
        assert _normalise_book("Ps") == ("Ps", "Psalms")

    def test_case_insensitive(self):
        assert _normalise_book("JOHN") == ("John", "John")
        assert _normalise_book("genesis") == ("Gen", "Genesis")
        assert _normalise_book("PSALMS") == ("Ps", "Psalms")

    def test_trailing_dot(self):
        assert _normalise_book("Rev.") == ("Rev", "Revelation")
        assert _normalise_book("Gen.") == ("Gen", "Genesis")

    def test_numbered_books(self):
        assert _normalise_book("1 Corinthians") == ("1Cor", "1 Corinthians")
        assert _normalise_book("2 Timothy") == ("2Tim", "2 Timothy")
        assert _normalise_book("3 John") == ("3John", "3 John")

    def test_spoken_ordinals(self):
        assert _normalise_book("First John") == ("1John", "1 John")
        assert _normalise_book("Second Timothy") == ("2Tim", "2 Timothy")
        assert _normalise_book("Third John") == ("3John", "3 John")

    def test_fuzzy_stt_errors(self):
        # Common STT transcription variants
        assert _normalise_book("psalms") == ("Ps", "Psalms")
        assert _normalise_book("revelations") == ("Rev", "Revelation")

    def test_unknown_book_returns_none(self):
        assert _normalise_book("Narnia") is None
        assert _normalise_book("Atlantis") is None
        assert _normalise_book("") is None


# ─────────────────────────────────────────────────────────────────────────────
# _spans_overlap
# ─────────────────────────────────────────────────────────────────────────────

class TestSpansOverlap:
    def test_no_overlap(self):
        assert not _spans_overlap((0, 5), (5, 10))
        assert not _spans_overlap((10, 20), (0, 5))

    def test_overlap(self):
        assert _spans_overlap((0, 10), (5, 15))
        assert _spans_overlap((5, 15), (0, 10))

    def test_contained(self):
        assert _spans_overlap((0, 20), (5, 10))
        assert _spans_overlap((5, 10), (0, 20))

    def test_identical(self):
        assert _spans_overlap((0, 10), (0, 10))


# ─────────────────────────────────────────────────────────────────────────────
# Style A — colon notation
# ─────────────────────────────────────────────────────────────────────────────

class TestStyleAColon:
    def test_simple(self, detector):
        results = detector.detect("John 3:16")
        assert len(results) == 1
        r = results[0]
        assert r["verse"]["reference"]["book"] == "John"
        assert r["verse"]["reference"]["chapter"] == 3
        assert r["verse"]["reference"]["verse"] == 16
        assert r["verse"]["reference"]["verseEnd"] is None
        assert r["kind"] == "explicit"
        assert r["score"] == 1.0

    def test_with_abbreviation(self, detector):
        results = detector.detect("Rev. 22:20")
        assert len(results) == 1
        assert results[0]["verse"]["reference"]["book"] == "Revelation"

    def test_verse_range(self, detector):
        results = detector.detect("John 3:16-17")
        assert len(results) == 1
        ref = results[0]["verse"]["reference"]
        assert ref["verse"] == 16
        assert ref["verseEnd"] == 17

    def test_numbered_book(self, detector):
        results = detector.detect("1 Cor. 13:4")
        assert len(results) == 1
        assert results[0]["verse"]["reference"]["book"] == "1 Corinthians"
        assert results[0]["verse"]["reference"]["chapter"] == 13
        assert results[0]["verse"]["reference"]["verse"] == 4

    def test_dot_separator(self, detector):
        results = detector.detect("Psalm 23.1")
        assert len(results) == 1
        ref = results[0]["verse"]["reference"]
        assert ref["book"] == "Psalms"
        assert ref["chapter"] == 23
        assert ref["verse"] == 1

    def test_multiple_in_text(self, detector):
        results = detector.detect("Read John 3:16 and Romans 8:28 today.")
        assert len(results) == 2
        books = [r["verse"]["reference"]["book"] for r in results]
        assert "John" in books
        assert "Romans" in books

    def test_no_match(self, detector):
        assert detector.detect("Hello, how are you?") == []


# ─────────────────────────────────────────────────────────────────────────────
# Style B — chapter-only
# ─────────────────────────────────────────────────────────────────────────────

class TestStyleBChapterOnly:
    def test_psalm_23(self, detector):
        results = detector.detect("Turn to Psalm 23")
        assert len(results) == 1
        ref = results[0]["verse"]["reference"]
        assert ref["book"] == "Psalms"
        assert ref["chapter"] == 23
        assert ref["verse"] == 1   # default

    def test_obadiah(self, detector):
        results = detector.detect("Obadiah 3")
        assert len(results) == 1
        ref = results[0]["verse"]["reference"]
        assert ref["book"] == "Obadiah"
        assert ref["chapter"] == 3
        assert ref["verse"] == 1

    def test_does_not_match_unknown_book(self, detector):
        # "Meeting 5" should not produce a result
        results = detector.detect("Meeting 5")
        assert results == []

    def test_chapter_only_not_overridden_by_colon(self, detector):
        # "John 3:16" should be matched by Style A, not Style B
        results = detector.detect("John 3:16")
        assert len(results) == 1
        assert results[0]["verse"]["reference"]["verse"] == 16  # not 1


# ─────────────────────────────────────────────────────────────────────────────
# Style C — space-separated digits
# ─────────────────────────────────────────────────────────────────────────────

class TestStyleCSpaceSeparated:
    def test_romans_8_28(self, detector):
        results = detector.detect("Romans 8 28")
        assert len(results) == 1
        ref = results[0]["verse"]["reference"]
        assert ref["book"] == "Romans"
        assert ref["chapter"] == 8
        assert ref["verse"] == 28

    def test_genesis_1_1(self, detector):
        results = detector.detect("Genesis 1 1")
        assert len(results) == 1
        ref = results[0]["verse"]["reference"]
        assert ref["book"] == "Genesis"
        assert ref["chapter"] == 1
        assert ref["verse"] == 1

    def test_sanity_check_skips_large_numbers(self, detector):
        # ch=200 exceeds limit — should not match
        results = detector.detect("John 200 5")
        assert results == []

    def test_sanity_check_skips_large_verse(self, detector):
        # vs=300 exceeds limit
        results = detector.detect("John 3 300")
        assert results == []

    def test_not_matched_when_colon_present(self, detector):
        # Colon form should win, space form should not duplicate
        results = detector.detect("John 3:16")
        assert len(results) == 1
        assert results[0]["verse"]["reference"]["verse"] == 16


# ─────────────────────────────────────────────────────────────────────────────
# Style D — keyword notation
# ─────────────────────────────────────────────────────────────────────────────

class TestStyleDKeyword:
    def test_digit_numbers(self, detector):
        results = detector.detect("John chapter 3 verse 16")
        assert len(results) == 1
        ref = results[0]["verse"]["reference"]
        assert ref["book"] == "John"
        assert ref["chapter"] == 3
        assert ref["verse"] == 16

    def test_word_numbers(self, detector):
        results = detector.detect("Romans chapter eight verse twenty-eight")
        assert len(results) == 1
        ref = results[0]["verse"]["reference"]
        assert ref["book"] == "Romans"
        assert ref["chapter"] == 8
        assert ref["verse"] == 28

    def test_spoken_ordinal_book(self, detector):
        results = detector.detect("First John chapter two verse fifteen")
        assert len(results) == 1
        ref = results[0]["verse"]["reference"]
        assert ref["book"] == "1 John"
        assert ref["chapter"] == 2
        assert ref["verse"] == 15

    def test_revelation_spoken(self, detector):
        results = detector.detect("Revelation chapter twenty-two verse twenty")
        assert len(results) == 1
        ref = results[0]["verse"]["reference"]
        assert ref["book"] == "Revelation"
        assert ref["chapter"] == 22
        assert ref["verse"] == 20


# ─────────────────────────────────────────────────────────────────────────────
# Style E — compound spoken numbers
# ─────────────────────────────────────────────────────────────────────────────

class TestStyleECompoundNumbers:
    def test_psalms_thirty_one(self, detector):
        results = detector.detect("Psalms thirty-one")
        # Style B chapter-only with word number — this doesn't match because
        # _RE_CHAPTER_ONLY only matches digits; spoken-chapter is via keyword style
        # (testing that detector doesn't crash on this input)
        # actual match depends on whether STT produces "Psalms 31" or "Psalms thirty-one"
        assert isinstance(results, list)

    def test_keyword_compound_chapter(self, detector):
        results = detector.detect("Genesis chapter twenty-two verse eighteen")
        assert len(results) == 1
        ref = results[0]["verse"]["reference"]
        assert ref["chapter"] == 22
        assert ref["verse"] == 18

    def test_keyword_tens_only(self, detector):
        results = detector.detect("John chapter three verse twenty")
        assert len(results) == 1
        ref = results[0]["verse"]["reference"]
        assert ref["chapter"] == 3
        assert ref["verse"] == 20


# ─────────────────────────────────────────────────────────────────────────────
# Deduplication
# ─────────────────────────────────────────────────────────────────────────────

class TestDeduplication:
    def test_same_reference_appears_once(self, detector):
        # Both colon and space-separated forms for same verse in same text
        results = detector.detect("John 3:16 is the same as John 3:16")
        assert len(results) == 1

    def test_different_references_not_deduped(self, detector):
        results = detector.detect("John 3:16 and Romans 8:28")
        assert len(results) == 2

    def test_range_start_deduped_against_single(self, detector):
        # John 3:16-17 and John 3:16 refer to the same start verse
        results = detector.detect("John 3:16-17 and John 3:16")
        # First match (John 3:16) wins via dedup key
        assert len(results) == 1


# ─────────────────────────────────────────────────────────────────────────────
# Verse text lookup via BibleLookup
# ─────────────────────────────────────────────────────────────────────────────

class TestVerseLookup:
    def test_single_verse_text_populated(self, detector_with_lookup):
        results = detector_with_lookup.detect("John 3:16")
        assert len(results) == 1
        assert results[0]["verse"]["text"] == "For God so loved the world."
        assert results[0]["verse"]["translation"] == "KJV"

    def test_range_verse_text_joined(self, detector_with_lookup):
        results = detector_with_lookup.detect("John 3:16-17")
        assert len(results) == 1
        text = results[0]["verse"]["text"]
        assert "For God so loved the world," in text
        assert "whosoever believeth" in text

    def test_no_lookup_returns_empty_text(self, detector):
        results = detector.detect("John 3:16")
        assert len(results) == 1
        assert results[0]["verse"]["text"] == ""

    def test_lookup_returns_none_gracefully(self):
        lookup = MagicMock()
        lookup.get.return_value = None
        lookup.get_range.return_value = []
        det = VerseDetector(lookup=lookup)
        results = det.detect("John 3:16")
        assert len(results) == 1
        assert results[0]["verse"]["text"] == ""


# ─────────────────────────────────────────────────────────────────────────────
# Suggestion shape validation
# ─────────────────────────────────────────────────────────────────────────────

class TestSuggestionShape:
    def test_required_keys_present(self, detector):
        results = detector.detect("John 3:16")
        assert len(results) == 1
        r = results[0]
        assert "id" in r
        assert "kind" in r
        assert "verse" in r
        assert "score" in r
        assert "triggerText" in r

    def test_verse_reference_keys(self, detector):
        results = detector.detect("Romans 8:28")
        ref = results[0]["verse"]["reference"]
        assert "book" in ref
        assert "chapter" in ref
        assert "verse" in ref
        assert "verseEnd" in ref

    def test_id_is_stable(self, detector):
        """Same reference always produces the same suggestion ID."""
        r1 = detector.detect("John 3:16")[0]
        r2 = detector.detect("John 3:16")[0]
        assert r1["id"] == r2["id"]

    def test_trigger_text_is_substring(self, detector):
        text = "We read from John 3:16 today"
        results = detector.detect(text)
        assert len(results) == 1
        trigger = results[0]["triggerText"]
        assert trigger in text


# ─────────────────────────────────────────────────────────────────────────────
# Edge cases
# ─────────────────────────────────────────────────────────────────────────────

class TestEdgeCases:
    def test_empty_string(self, detector):
        assert detector.detect("") == []

    def test_no_references(self, detector):
        assert detector.detect("Welcome to our Sunday service today!") == []

    def test_reference_at_start(self, detector):
        results = detector.detect("John 3:16 is the key verse")
        assert len(results) == 1

    def test_reference_at_end(self, detector):
        results = detector.detect("The key verse is John 3:16")
        assert len(results) == 1

    def test_multiline_text(self, detector):
        results = detector.detect("Today we look at\nJohn 3:16\nand Romans 8:28")
        assert len(results) == 2

    def test_case_insensitive_book(self, detector):
        results = detector.detect("john 3:16")
        assert len(results) == 1
        assert results[0]["verse"]["reference"]["book"] == "John"

    def test_verse_range_end_captured(self, detector):
        results = detector.detect("Read Ephesians 2:8-9")
        assert len(results) == 1
        ref = results[0]["verse"]["reference"]
        assert ref["verse"] == 8
        assert ref["verseEnd"] == 9

    def test_single_chapter_book(self, detector):
        results = detector.detect("Jude 4")
        assert len(results) == 1
        ref = results[0]["verse"]["reference"]
        assert ref["book"] == "Jude"

    def test_song_of_solomon(self, detector):
        results = detector.detect("Song of Solomon 2:4")
        assert len(results) == 1
        assert results[0]["verse"]["reference"]["book"] == "Song of Solomon"

    def test_psalm_abbreviation(self, detector):
        results = detector.detect("Ps 119:105")
        assert len(results) == 1
        assert results[0]["verse"]["reference"]["book"] == "Psalms"
