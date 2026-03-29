"""
sidecar/analysis/verse_detector.py
───────────────────────────────────────────────────────────────────────────────
Explicit Bible verse reference detector.

Handles all common spoken and written reference styles:

  Style A — colon/dot notation (written):
      "John 3:16"   "Rev. 22:20-21"   "1 Cor. 13:4"

  Style B — chapter-only (common for Psalms and single-chapter books):
      "Psalm 23"    "Obadiah 3"

  Style C — space-separated (spoken transcript artefact):
      "Romans 8 28"   "Genesis 1 1"

  Style D — chapter/verse keywords (dictated or spoken naturally):
      "John chapter 3 verse 16"   "First John chapter two verse fifteen"

  Style E — compound spoken numbers (all of the above with word numbers):
      "Revelation chapter twenty-two verse twenty"
      "Psalms thirty-one"

For each match the detector:
  1. Extracts raw book name + chapter + verse (+ optional end verse for ranges).
  2. Normalises the book name via exact lookup → fuzzy fallback.
  3. Looks up the verse text from BibleLookup (loaded from meta.json).
  4. Returns a VerseSuggestion-shaped dict ready to broadcast over WebSocket.
"""

from __future__ import annotations

import hashlib
import logging
import re
from dataclasses import dataclass
from typing import Any

from rapidfuzz import process as fuzz_process

from .bible_lookup import BibleLookup

log = logging.getLogger("verseflow.verse_detector")


# ─────────────────────────────────────────────────────────────────────────────
# Book normalisation table
# Maps every common alias/abbreviation → (abbreviation, canonical full name)
# ─────────────────────────────────────────────────────────────────────────────

_BOOK_TABLE: dict[str, tuple[str, str]] = {
    # ── Old Testament ──────────────────────────────────────────────────────
    "genesis": ("Gen", "Genesis"), "gen": ("Gen", "Genesis"),
    "exodus": ("Exod", "Exodus"), "exod": ("Exod", "Exodus"), "ex": ("Exod", "Exodus"),
    "leviticus": ("Lev", "Leviticus"), "lev": ("Lev", "Leviticus"),
    "numbers": ("Num", "Numbers"), "num": ("Num", "Numbers"),
    "deuteronomy": ("Deut", "Deuteronomy"), "deut": ("Deut", "Deuteronomy"), "dt": ("Deut", "Deuteronomy"),
    "joshua": ("Josh", "Joshua"), "josh": ("Josh", "Joshua"),
    "judges": ("Judg", "Judges"), "judg": ("Judg", "Judges"),
    "ruth": ("Ruth", "Ruth"),
    "1 samuel": ("1Sam", "1 Samuel"), "1samuel": ("1Sam", "1 Samuel"), "1sam": ("1Sam", "1 Samuel"),
    "2 samuel": ("2Sam", "2 Samuel"), "2samuel": ("2Sam", "2 Samuel"), "2sam": ("2Sam", "2 Samuel"),
    "1 kings": ("1Kgs", "1 Kings"), "1kings": ("1Kgs", "1 Kings"), "1kgs": ("1Kgs", "1 Kings"),
    "2 kings": ("2Kgs", "2 Kings"), "2kings": ("2Kgs", "2 Kings"), "2kgs": ("2Kgs", "2 Kings"),
    "1 chronicles": ("1Chr", "1 Chronicles"), "1chronicles": ("1Chr", "1 Chronicles"), "1chr": ("1Chr", "1 Chronicles"),
    "2 chronicles": ("2Chr", "2 Chronicles"), "2chronicles": ("2Chr", "2 Chronicles"), "2chr": ("2Chr", "2 Chronicles"),
    "ezra": ("Ezra", "Ezra"),
    "nehemiah": ("Neh", "Nehemiah"), "neh": ("Neh", "Nehemiah"),
    "esther": ("Esth", "Esther"), "esth": ("Esth", "Esther"),
    "job": ("Job", "Job"),
    "psalms": ("Ps", "Psalms"), "psalm": ("Ps", "Psalms"), "ps": ("Ps", "Psalms"),
    "proverbs": ("Prov", "Proverbs"), "prov": ("Prov", "Proverbs"),
    "ecclesiastes": ("Eccl", "Ecclesiastes"), "eccl": ("Eccl", "Ecclesiastes"),
    "song of solomon": ("Song", "Song of Solomon"), "song": ("Song", "Song of Solomon"),
    "song of songs": ("Song", "Song of Solomon"), "sos": ("Song", "Song of Solomon"),
    "isaiah": ("Isa", "Isaiah"), "isa": ("Isa", "Isaiah"),
    "jeremiah": ("Jer", "Jeremiah"), "jer": ("Jer", "Jeremiah"),
    "lamentations": ("Lam", "Lamentations"), "lam": ("Lam", "Lamentations"),
    "ezekiel": ("Ezek", "Ezekiel"), "ezek": ("Ezek", "Ezekiel"),
    "daniel": ("Dan", "Daniel"), "dan": ("Dan", "Daniel"),
    "hosea": ("Hos", "Hosea"), "hos": ("Hos", "Hosea"),
    "joel": ("Joel", "Joel"),
    "amos": ("Amos", "Amos"),
    "obadiah": ("Obad", "Obadiah"), "obad": ("Obad", "Obadiah"),
    "jonah": ("Jonah", "Jonah"),
    "micah": ("Mic", "Micah"), "mic": ("Mic", "Micah"),
    "nahum": ("Nah", "Nahum"), "nah": ("Nah", "Nahum"),
    "habakkuk": ("Hab", "Habakkuk"), "hab": ("Hab", "Habakkuk"),
    "zephaniah": ("Zeph", "Zephaniah"), "zeph": ("Zeph", "Zephaniah"),
    "haggai": ("Hag", "Haggai"), "hag": ("Hag", "Haggai"),
    "zechariah": ("Zech", "Zechariah"), "zech": ("Zech", "Zechariah"),
    "malachi": ("Mal", "Malachi"), "mal": ("Mal", "Malachi"),
    # ── New Testament ──────────────────────────────────────────────────────
    "matthew": ("Matt", "Matthew"), "matt": ("Matt", "Matthew"), "mt": ("Matt", "Matthew"),
    "mark": ("Mark", "Mark"), "mk": ("Mark", "Mark"),
    "luke": ("Luke", "Luke"), "lk": ("Luke", "Luke"),
    "john": ("John", "John"), "jn": ("John", "John"),
    "acts": ("Acts", "Acts"),
    "romans": ("Rom", "Romans"), "rom": ("Rom", "Romans"),
    "1 corinthians": ("1Cor", "1 Corinthians"), "1corinthians": ("1Cor", "1 Corinthians"), "1cor": ("1Cor", "1 Corinthians"),
    "2 corinthians": ("2Cor", "2 Corinthians"), "2corinthians": ("2Cor", "2 Corinthians"), "2cor": ("2Cor", "2 Corinthians"),
    "galatians": ("Gal", "Galatians"), "gal": ("Gal", "Galatians"),
    "ephesians": ("Eph", "Ephesians"), "eph": ("Eph", "Ephesians"),
    "philippians": ("Phil", "Philippians"), "phil": ("Phil", "Philippians"),
    "colossians": ("Col", "Colossians"), "col": ("Col", "Colossians"),
    "1 thessalonians": ("1Thess", "1 Thessalonians"), "1thess": ("1Thess", "1 Thessalonians"),
    "2 thessalonians": ("2Thess", "2 Thessalonians"), "2thess": ("2Thess", "2 Thessalonians"),
    "1 timothy": ("1Tim", "1 Timothy"), "1timothy": ("1Tim", "1 Timothy"), "1tim": ("1Tim", "1 Timothy"),
    "2 timothy": ("2Tim", "2 Timothy"), "2timothy": ("2Tim", "2 Timothy"), "2tim": ("2Tim", "2 Timothy"),
    "titus": ("Titus", "Titus"),
    "philemon": ("Phlm", "Philemon"), "phlm": ("Phlm", "Philemon"),
    "hebrews": ("Heb", "Hebrews"), "heb": ("Heb", "Hebrews"),
    "james": ("Jas", "James"), "jas": ("Jas", "James"),
    "1 peter": ("1Pet", "1 Peter"), "1peter": ("1Pet", "1 Peter"), "1pet": ("1Pet", "1 Peter"),
    "2 peter": ("2Pet", "2 Peter"), "2peter": ("2Pet", "2 Peter"), "2pet": ("2Pet", "2 Peter"),
    "1 john": ("1John", "1 John"), "1john": ("1John", "1 John"),
    "2 john": ("2John", "2 John"), "2john": ("2John", "2 John"),
    "3 john": ("3John", "3 John"), "3john": ("3John", "3 John"),
    "jude": ("Jude", "Jude"),
    "revelation": ("Rev", "Revelation"), "rev": ("Rev", "Revelation"),
    "revelations": ("Rev", "Revelation"),
    # ── Spoken ordinal forms ───────────────────────────────────────────────
    "first samuel": ("1Sam", "1 Samuel"),   "second samuel": ("2Sam", "2 Samuel"),
    "first kings": ("1Kgs", "1 Kings"),     "second kings": ("2Kgs", "2 Kings"),
    "first chronicles": ("1Chr", "1 Chronicles"), "second chronicles": ("2Chr", "2 Chronicles"),
    "first corinthians": ("1Cor", "1 Corinthians"), "second corinthians": ("2Cor", "2 Corinthians"),
    "first thessalonians": ("1Thess", "1 Thessalonians"), "second thessalonians": ("2Thess", "2 Thessalonians"),
    "first timothy": ("1Tim", "1 Timothy"), "second timothy": ("2Tim", "2 Timothy"),
    "first peter": ("1Pet", "1 Peter"),     "second peter": ("2Pet", "2 Peter"),
    "first john": ("1John", "1 John"),      "second john": ("2John", "2 John"),
    "third john": ("3John", "3 John"),
}

# Precomputed set of all lookup keys (used by fuzzy match).
_BOOK_KEYS = list(_BOOK_TABLE.keys())


# ─────────────────────────────────────────────────────────────────────────────
# Number word parsing
# ─────────────────────────────────────────────────────────────────────────────

_ONES = {
    "one": 1, "two": 2, "three": 3, "four": 4, "five": 5,
    "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10,
    "eleven": 11, "twelve": 12, "thirteen": 13, "fourteen": 14, "fifteen": 15,
    "sixteen": 16, "seventeen": 17, "eighteen": 18, "nineteen": 19,
}
_TENS = {
    "twenty": 20, "thirty": 30, "forty": 40, "fifty": 50,
    "sixty": 60, "seventy": 70, "eighty": 80, "ninety": 90,
}

def _word_to_int(word: str) -> int | None:
    """
    Convert a spoken number word to an integer.
    Handles: "three", "twenty", "twenty-two", "twenty two", digits.
    Returns None if the word cannot be parsed as a number.
    """
    w = word.strip().lower().replace("-", " ")
    if w.isdigit():
        return int(w)
    if w in _ONES:
        return _ONES[w]
    if w in _TENS:
        return _TENS[w]
    # Compound: "twenty two" / "thirty three"
    parts = w.split()
    if len(parts) == 2 and parts[0] in _TENS and parts[1] in _ONES:
        return _TENS[parts[0]] + _ONES[parts[1]]
    return None


# ─────────────────────────────────────────────────────────────────────────────
# Regex patterns
# ─────────────────────────────────────────────────────────────────────────────

# Book segment: optional leading digit, one or more word groups, optional dot.
_BOOK_SEG = r"(?:\d\s?)?[A-Za-z]+(?:\s[A-Za-z]+)*\.?"

# Digit chapter:verse with optional range  →  groups: (ch, vs, vs_end?)
_CV_COLON = r"(\d{1,3})\s*[:\.]\s*(\d{1,3})(?:\s*[-–]\s*(\d{1,3}))?"

# Digit chapter SPACE digit verse (no colon) — e.g. "Romans 8 28"
# Requires verse ≤ 176 (longest chapter) to avoid false positives on years etc.
_CV_SPACE = r"(\d{1,3})\s+(\d{1,3})"

# "chapter N verse M" keyword form — N and M can be digits or word numbers.
_NUM_WORD = r"(\d+|(?:twenty|thirty|forty|fifty|sixty|seventy|eighty|ninety)?[-\s]?(?:eleven|twelve|thirteen|fourteen|fifteen|sixteen|seventeen|eighteen|nineteen|one|two|three|four|five|six|seven|eight|nine|ten|twenty|thirty|forty|fifty|sixty|seventy|eighty|ninety)?)"
_CV_KEYWORD = rf"chapter\s+{_NUM_WORD}\s+verse\s+{_NUM_WORD}"

# ── Compiled patterns (order matters — most specific first) ──────────────────

# Style A: "John 3:16"  "Rev. 22:20-21"
_RE_COLON = re.compile(
    rf"({_BOOK_SEG})\s+{_CV_COLON}",
    re.IGNORECASE,
)

# Style D: "John chapter 3 verse 16"  "First John chapter two verse fifteen"
_RE_KEYWORD = re.compile(
    rf"({_BOOK_SEG})\s+{_CV_KEYWORD}",
    re.IGNORECASE,
)

# Style C: "Romans 8 28"  (space-separated digits, no colon)
# Anchored to avoid matching inside longer numeric strings.
_RE_SPACE = re.compile(
    rf"({_BOOK_SEG})\s+{_CV_SPACE}(?!\s*\d)",
    re.IGNORECASE,
)

# Style B: "Psalm 23"  (chapter only — we default to verse 1)
_RE_CHAPTER_ONLY = re.compile(
    rf"({_BOOK_SEG})\s+(\d{{1,3}})(?!\s*[:.\d])",
    re.IGNORECASE,
)


# ─────────────────────────────────────────────────────────────────────────────
# Internal match container
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class _RawMatch:
    book_raw: str
    chapter: int
    verse: int
    verse_end: int | None
    span: tuple[int, int]
    chapter_only: bool = False   # True → verse 1 assumed


# ─────────────────────────────────────────────────────────────────────────────
# VerseDetector
# ─────────────────────────────────────────────────────────────────────────────

class VerseDetector:
    """
    Stateless (after construction) explicit verse reference detector.

    Pass a BibleLookup instance so verse text is populated in results.
    If no lookup is provided, text field will be empty (useful for tests).
    """

    def __init__(self, lookup: BibleLookup | None = None) -> None:
        self._lookup = lookup

    def detect(self, text: str) -> list[dict[str, Any]]:
        """
        Detect all explicit Bible references in `text`.
        Returns VerseSuggestion-shaped dicts, deduped, in match order.
        """
        raw_matches = self._find_matches(text)
        results: list[dict[str, Any]] = []
        seen: set[str] = set()

        for m in raw_matches:
            canonical = _normalise_book(m.book_raw)
            if canonical is None:
                continue

            abbrev, full_name = canonical
            dedup_key = f"{abbrev}.{m.chapter}.{m.verse}"
            if dedup_key in seen:
                continue
            seen.add(dedup_key)

            # Look up verse text (populated if BibleLookup is loaded).
            verse_text = ""
            translation = "KJV"
            if self._lookup:
                if m.verse_end:
                    entries = self._lookup.get_range(full_name, m.chapter, m.verse, m.verse_end)
                    if entries:
                        verse_text = " ".join(e["text"] for e in entries)
                        translation = entries[0]["translation"]
                else:
                    entry = self._lookup.get(full_name, m.chapter, m.verse)
                    if entry:
                        verse_text = entry["text"]
                        translation = entry["translation"]

            ref_str = (
                f"{full_name} {m.chapter}:{m.verse}-{m.verse_end}"
                if m.verse_end
                else f"{full_name} {m.chapter}:{m.verse}"
            )
            suggestion_id = hashlib.md5(ref_str.encode()).hexdigest()[:12]

            results.append({
                "id": suggestion_id,
                "kind": "explicit",
                "verse": {
                    "reference": {
                        "book": full_name,
                        "chapter": m.chapter,
                        "verse": m.verse,
                        "verseEnd": m.verse_end,
                    },
                    "translation": translation,
                    "text": verse_text,
                },
                "score": 1.0,
                "triggerText": text[m.span[0]: m.span[1]],
            })

        return results

    # ── Private ───────────────────────────────────────────────────────────────

    def _find_matches(self, text: str) -> list[_RawMatch]:
        """
        Run all regex patterns and return raw matches sorted by position.
        Overlapping spans are filtered so the most specific match wins.
        """
        matches: list[_RawMatch] = []

        # Style A (colon) — highest confidence.
        for m in _RE_COLON.finditer(text):
            ch = int(m.group(2))
            vs = int(m.group(3))
            vs_end = int(m.group(4)) if m.group(4) else None
            matches.append(_RawMatch(m.group(1).strip().rstrip("."), ch, vs, vs_end, m.span()))

        # Style D (keyword) — high confidence.
        for m in _RE_KEYWORD.finditer(text):
            ch = _word_to_int(m.group(2))
            vs = _word_to_int(m.group(3))
            if ch and vs:
                matches.append(_RawMatch(m.group(1).strip(), ch, vs, None, m.span()))

        # Style C (space-separated) — medium confidence; skip if same span covered.
        existing_spans = {m.span for m in matches}
        for m in _RE_SPACE.finditer(text):
            span = m.span()
            if any(_spans_overlap(span, e) for e in existing_spans):
                continue
            ch = int(m.group(2))
            vs = int(m.group(3))
            # Sanity-check: verse numbers > 200 are almost certainly not Bible refs.
            if ch > 150 or vs > 200:
                continue
            matches.append(_RawMatch(m.group(1).strip().rstrip("."), ch, vs, None, span))
            existing_spans.add(span)

        # Style B (chapter-only) — lowest confidence; only accept known book names.
        for m in _RE_CHAPTER_ONLY.finditer(text):
            span = m.span()
            if any(_spans_overlap(span, e) for e in existing_spans):
                continue
            book_raw = m.group(1).strip().rstrip(".")
            # Pre-validate the book name before adding — avoids noise.
            if _normalise_book(book_raw) is None:
                continue
            ch = int(m.group(2))
            matches.append(_RawMatch(book_raw, ch, 1, None, span, chapter_only=True))

        # Sort by position in text.
        matches.sort(key=lambda x: x.span[0])
        return matches


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _normalise_book(raw: str) -> tuple[str, str] | None:
    """Resolve a raw book name string to (abbreviation, full canonical name)."""
    key = raw.lower().strip().rstrip(".")
    if key in _BOOK_TABLE:
        return _BOOK_TABLE[key]

    # Fuzzy fallback for STT transcription errors (e.g. "Jon" → "John").
    result = fuzz_process.extractOne(key, _BOOK_KEYS, score_cutoff=82)
    if result:
        return _BOOK_TABLE[result[0]]

    log.debug("Could not normalise book name: %r", raw)
    return None


def _spans_overlap(a: tuple[int, int], b: tuple[int, int]) -> bool:
    return a[0] < b[1] and b[0] < a[1]
