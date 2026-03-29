"""
scripts/build_bible_index.py
───────────────────────────────────────────────────────────────────────────────
Downloads the public-domain KJV Bible (or any translation you provide),
generates per-verse sentence embeddings, and writes a FAISS index + metadata
file that the SemanticBibleEngine loads at runtime.

Usage:
    # Standard — download KJV automatically:
    python scripts/build_bible_index.py

    # Use your own Bible JSON file:
    python scripts/build_bible_index.py --bible-json path/to/bible.json

    # Build for a specific translation with a custom label:
    python scripts/build_bible_index.py --translation NIV --bible-json niv.json

Bible JSON format expected (two layouts both supported):
    Layout A — nested (most common on GitHub):
        [{"name": "Genesis", "chapters": [["verse text", ...], ...]}, ...]

    Layout B — flat (e.g. eBible corpus):
        [{"book": "Genesis", "chapter": 1, "verse": 1, "text": "..."}, ...]

Output:
    data/bibles/kjv.json        — raw source  (cached for re-use)
    data/bibles/meta.json       — [{book, chapter, verse, translation, text}, ...]
    data/bibles/index.faiss     — FAISS IndexFlatIP (L2-normalised embeddings)

Run time on CPU (base.en embed model, full KJV ~31k verses):
    ~3–5 minutes on a modern laptop.  Run once and never again unless you add
    a new translation.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.request
from pathlib import Path

# Ensure UTF-8 output on Windows (cp1252 terminals can't print ✓ etc.)
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

import numpy as np

# ── Paths ─────────────────────────────────────────────────────────────────────

REPO_ROOT = Path(__file__).parent.parent
DATA_DIR = REPO_ROOT / "data" / "bibles"
DATA_DIR.mkdir(parents=True, exist_ok=True)

RAW_KJV_PATH = DATA_DIR / "kjv.json"
META_PATH = DATA_DIR / "meta.json"
INDEX_PATH = DATA_DIR / "index.faiss"

# Public-domain KJV Bible JSON (nested layout A).
# Source: https://github.com/thiagobodruk/bible  (public domain)
KJV_URL = (
    "https://raw.githubusercontent.com/thiagobodruk/bible/master/json/en_kjv.json"
)

# Embedding model — same one the sidecar uses so vectors are compatible.
EMBED_MODEL = "all-MiniLM-L6-v2"

# How many verses to embed in one batch (tune down if you run out of RAM).
BATCH_SIZE = 256


# ── Bible loading ─────────────────────────────────────────────────────────────

def download_kjv() -> Path:
    """Download KJV JSON if not already cached."""
    if RAW_KJV_PATH.exists():
        print(f"  Using cached KJV at {RAW_KJV_PATH}")
        return RAW_KJV_PATH

    print(f"  Downloading KJV from {KJV_URL} …")
    t0 = time.time()
    urllib.request.urlretrieve(KJV_URL, RAW_KJV_PATH)
    size_mb = RAW_KJV_PATH.stat().st_size / 1_048_576
    print(f"  ✓ Downloaded {size_mb:.1f} MB in {time.time() - t0:.1f}s")
    return RAW_KJV_PATH


def load_verses_nested(data: list, translation: str) -> list[dict]:
    """
    Parse Layout A:
        [{name, chapters: [[verse_text, ...], ...]}, ...]
    Chapters and verses are 1-indexed in the output.
    """
    verses = []
    for book_obj in data:
        book = book_obj["name"]
        for ch_idx, chapter in enumerate(book_obj["chapters"], start=1):
            for vs_idx, text in enumerate(chapter, start=1):
                text = text.strip()
                if text:
                    verses.append({
                        "book": book,
                        "chapter": ch_idx,
                        "verse": vs_idx,
                        "translation": translation,
                        "text": text,
                    })
    return verses


def load_verses_flat(data: list, translation: str) -> list[dict]:
    """
    Parse Layout B:
        [{book, chapter, verse, text}, ...]
    """
    verses = []
    for entry in data:
        text = entry.get("text", "").strip()
        if text:
            verses.append({
                "book": entry["book"],
                "chapter": int(entry["chapter"]),
                "verse": int(entry["verse"]),
                "translation": translation,
                "text": text,
            })
    return verses


def load_verses(path: Path, translation: str) -> list[dict]:
    print(f"  Loading Bible JSON from {path} …")
    # Use utf-8-sig to transparently strip the BOM present in some KJV files.
    with open(path, encoding="utf-8-sig") as f:
        data = json.load(f)

    if not data:
        raise ValueError("Bible JSON is empty")

    # Auto-detect layout.
    first = data[0]
    if "chapters" in first:
        verses = load_verses_nested(data, translation)
        print(f"  Detected nested layout — {len(verses):,} verses loaded")
    elif "text" in first:
        verses = load_verses_flat(data, translation)
        print(f"  Detected flat layout — {len(verses):,} verses loaded")
    else:
        raise ValueError(
            f"Unrecognised Bible JSON layout. First entry keys: {list(first.keys())}"
        )

    return verses


# ── Embedding ──────────────────────────────────────────────────────────────────

def embed_verses(verses: list[dict]) -> np.ndarray:
    """
    Embed every verse text with sentence-transformers.
    Returns a float32 array of shape (N, embedding_dim) — L2-normalised
    so cosine similarity == inner product (required for IndexFlatIP).
    """
    try:
        from sentence_transformers import SentenceTransformer
    except ImportError:
        print("ERROR: sentence-transformers not installed.")
        print("  Run: pip install sentence-transformers")
        sys.exit(1)

    print(f"\n  Loading embedding model '{EMBED_MODEL}' …")
    model = SentenceTransformer(EMBED_MODEL)

    texts = [v["text"] for v in verses]
    total = len(texts)
    print(f"  Embedding {total:,} verses in batches of {BATCH_SIZE} …")

    all_embeddings: list[np.ndarray] = []
    t0 = time.time()

    for i in range(0, total, BATCH_SIZE):
        batch = texts[i: i + BATCH_SIZE]
        embeddings = model.encode(
            batch,
            normalize_embeddings=True,  # IMPORTANT: required for IndexFlatIP cosine search
            show_progress_bar=False,
            batch_size=BATCH_SIZE,
        )
        all_embeddings.append(embeddings.astype("float32"))

        done = min(i + BATCH_SIZE, total)
        pct = done / total * 100
        elapsed = time.time() - t0
        eta = (elapsed / done) * (total - done) if done else 0
        print(f"    {done:>6,} / {total:,}  ({pct:.1f}%)  ETA {eta:.0f}s", end="\r")

    print(f"\n  ✓ Embedded {total:,} verses in {time.time() - t0:.1f}s")
    return np.vstack(all_embeddings)


# ── FAISS index ───────────────────────────────────────────────────────────────

def build_index(embeddings: np.ndarray) -> "faiss.IndexFlatIP":  # type: ignore[name-defined]
    try:
        import faiss  # type: ignore[import]
    except ImportError:
        print("ERROR: faiss-cpu not installed.")
        print("  Run: pip install faiss-cpu")
        sys.exit(1)

    dim = embeddings.shape[1]
    print(f"\n  Building FAISS IndexFlatIP (dim={dim}) …")
    index = faiss.IndexFlatIP(dim)
    index.add(embeddings)
    print(f"  ✓ Index built — {index.ntotal:,} vectors")
    return index


def save_index(index: "faiss.IndexFlatIP", meta: list[dict]) -> None:  # type: ignore[name-defined]
    import faiss  # type: ignore[import]

    print(f"\n  Saving index to {INDEX_PATH} …")
    faiss.write_index(index, str(INDEX_PATH))

    print(f"  Saving metadata to {META_PATH} …")
    with open(META_PATH, "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, separators=(",", ":"))

    index_mb = INDEX_PATH.stat().st_size / 1_048_576
    meta_mb = META_PATH.stat().st_size / 1_048_576
    print(f"  ✓ index.faiss  {index_mb:.1f} MB")
    print(f"  ✓ meta.json    {meta_mb:.1f} MB")


# ── Verification ──────────────────────────────────────────────────────────────

def verify_index(
    verses: list[dict],
    index: "faiss.IndexFlatIP",  # type: ignore[name-defined]
    query: str = "For God so loved the world",
) -> None:
    """Quick smoke test using the already-built index and metadata — no disk re-read."""
    from sentence_transformers import SentenceTransformer  # type: ignore[import]

    print(f'\n  Smoke test — searching for: "{query}"')
    model = SentenceTransformer(EMBED_MODEL)
    q = model.encode([query], normalize_embeddings=True).astype("float32")
    scores, indices = index.search(q, 5)

    print("  Top 5 results:")
    for score, idx in zip(scores[0], indices[0]):
        if idx < 0:
            continue
        m = verses[idx]
        print(f"    [{score:.3f}]  {m['book']} {m['chapter']}:{m['verse']}  —  {m['text'][:80]}")


# ── Entry point ───────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(description="Build VerseFlow Bible FAISS index")
    parser.add_argument(
        "--bible-json", type=Path, default=None,
        help="Path to an existing Bible JSON file. If omitted, KJV is downloaded automatically.",
    )
    parser.add_argument(
        "--translation", default="KJV",
        help="Translation label stored in metadata (default: KJV)",
    )
    parser.add_argument(
        "--skip-verify", action="store_true",
        help="Skip the smoke-test query after building",
    )
    args = parser.parse_args()

    print("VerseFlow — Bible Index Builder")
    print("=" * 40)

    total_t0 = time.time()

    # 1. Source the Bible JSON.
    if args.bible_json:
        source = Path(args.bible_json)
        if not source.exists():
            print(f"ERROR: File not found: {source}")
            sys.exit(1)
    else:
        print("\n[1/4] Sourcing KJV Bible …")
        source = download_kjv()

    # 2. Parse verses.
    print("\n[2/4] Parsing verses …")
    verses = load_verses(source, args.translation)

    # 3. Embed.
    print("\n[3/4] Generating embeddings …")
    embeddings = embed_verses(verses)

    # 4. Build & save index.
    print("\n[4/4] Building FAISS index …")
    index = build_index(embeddings)
    save_index(index, verses)

    print(f"\n✓ Bible index built in {time.time() - total_t0:.1f}s")
    print(f"  Verses indexed : {len(verses):,}")
    print(f"  Output dir     : {DATA_DIR}")

    if not args.skip_verify:
        verify_index(verses, index)

    print("\nDone. You can now start the sidecar — semantic Bible search is active.")


if __name__ == "__main__":
    main()
