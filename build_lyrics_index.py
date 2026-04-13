"""
scripts/build_lyrics_index.py
───────────────────────────────────────────────────────────────────────────────
Ingests worship song lyrics from a user-supplied folder, generates embeddings
per lyric block (verse/chorus/bridge), and writes a FAISS index + metadata.

─── Copyright compliance ────────────────────────────────────────────────────
  Most modern worship song lyrics are copyrighted (CCLI, Hillsong, Bethel,
  Elevation, etc.).  VerseFlow does NOT bundle any copyrighted lyrics.

  HOW TO LEGALLY SOURCE LYRICS FOR THIS INDEX:
    1. CCLI SongSelect (https://songselect.ccli.com)
       Your church almost certainly has a CCLI licence.  Log in, search for a
       song, and export/copy the lyrics.  CCLI licences typically permit local
       use in church software.

    2. OpenLP song database (https://openlp.org)
       OpenLP ships with a public-domain hymn pack and allows importing from
       CCLI SongSelect.  Export songs as plain text.

    3. Public-domain hymns
       Pre-1928 hymns (Amazing Grace, How Great Thou Art, etc.) are in the
       public domain.  Many are available at hymnary.org.

  WHAT THIS SCRIPT STORES:
    ✓  Song title
    ✓  Artist / copyright holder (for display only)
    ✓  Line groups (2-4 lines per block) that matched the query
    ✗  No full lyric text is stored in plain form — the data directory should
       NOT be committed to a public git repository.

─── Input format ────────────────────────────────────────────────────────────
  Place one .txt file per song in:  data/lyrics/source/

  File format (simple, human-editable):

      Title: Amazing Grace
      Artist: John Newton (Public Domain)

      Amazing grace! How sweet the sound
      That saved a wretch like me!
      I once was lost, but now am found
      Was blind, but now I see.

      'Twas grace that taught my heart to fear
      And grace my fears relieved
      ...

  Rules:
    - First two lines must be "Title:" and "Artist:" headers.
    - Blank lines separate lyric blocks (verse / chorus / bridge).
    - The script splits each block into overlapping windows of 4 lines,
      each window becomes one searchable entry in the FAISS index.

─── Output ──────────────────────────────────────────────────────────────────
    data/lyrics/index.faiss
    data/lyrics/meta.json    — [{title, artist, lines: [str, ...]}, ...]

Usage:
    python scripts/build_lyrics_index.py
    python scripts/build_lyrics_index.py --source-dir /path/to/lyrics
    python scripts/build_lyrics_index.py --window 3 --stride 2
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from dataclasses import dataclass

# Ensure UTF-8 output on Windows (cp1252 terminals can't print ✓ etc.)
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
from pathlib import Path

import numpy as np

# ── Paths ─────────────────────────────────────────────────────────────────────

REPO_ROOT = Path(__file__).parent.parent
SOURCE_DIR = REPO_ROOT / "data" / "lyrics" / "source"
OUT_DIR = REPO_ROOT / "data" / "lyrics"
OUT_DIR.mkdir(parents=True, exist_ok=True)

META_PATH = OUT_DIR / "meta.json"
INDEX_PATH = OUT_DIR / "index.faiss"

EMBED_MODEL = "multi-qa-MiniLM-L6-cos-v1"
BATCH_SIZE = 256


# ── Lyric parsing ─────────────────────────────────────────────────────────────

@dataclass
class LyricBlock:
    title: str
    artist: str
    lines: list[str]   # The 2–4 lines in this sliding window
    embed_text: str    # Joined text passed to the encoder


def parse_song_file(path: Path) -> tuple[list[str], str, str] | None:
    """
    Parse a single song .txt file.
    Returns (lyric_lines, title, artist) or None if the file has no content.
    """
    text = path.read_text(encoding="utf-8")
    lines = [l.rstrip() for l in text.splitlines()]

    title = artist = ""
    content_start = 0
    for i, line in enumerate(lines):
        if line.lower().startswith("title:"):
            title = line.split(":", 1)[1].strip()
        elif line.lower().startswith("artist:"):
            artist = line.split(":", 1)[1].strip()
        else:
            if title and artist and line.strip():
                content_start = i
                break

    if not title:
        title = path.stem.replace("_", " ").title()

    lyric_lines = [l for l in lines[content_start:] if l.strip()]
    if not lyric_lines:
        return None

    return lyric_lines, title, artist


def make_blocks(
    lyric_lines: list[str],
    title: str,
    artist: str,
    window: int = 4,
    stride: int = 2,
) -> list[LyricBlock]:
    """Slide a window over lyric_lines to create overlapping LyricBlocks."""
    blocks = []
    total = len(lyric_lines)
    for start in range(0, max(1, total - window + 1), stride):
        chunk = lyric_lines[start: start + window]
        blocks.append(LyricBlock(
            title=title,
            artist=artist,
            lines=chunk,
            embed_text=" ".join(chunk),
        ))
    return blocks


def load_all_songs(
    source_dir: Path,
    window: int = 4,
    stride: int = 2,
) -> list[LyricBlock]:
    """Walk source_dir and parse every .txt file."""
    txt_files = sorted(source_dir.glob("*.txt"))
    if not txt_files:
        return []

    all_blocks: list[LyricBlock] = []
    print(f"  Found {len(txt_files)} song file(s) in {source_dir}")

    for path in txt_files:
        try:
            result = parse_song_file(path)
            if result is None:
                continue
            lyric_lines, title, artist = result
            blocks = make_blocks(lyric_lines, title, artist, window, stride)
            all_blocks.extend(blocks)
            print(f"    ✓ {path.name:40s}  →  {len(blocks)} blocks")
        except Exception as e:
            print(f"    ✗ {path.name}: {e}")

    return all_blocks


# ── Embedding ──────────────────────────────────────────────────────────────────

def embed_blocks(blocks: list[LyricBlock]) -> np.ndarray:
    try:
        from sentence_transformers import SentenceTransformer  # type: ignore[import]
    except ImportError:
        print("ERROR: sentence-transformers not installed.")
        sys.exit(1)

    model = SentenceTransformer(EMBED_MODEL)
    texts = [b.embed_text for b in blocks]
    total = len(texts)

    print(f"  Embedding {total:,} lyric blocks …")
    t0 = time.time()
    all_emb: list[np.ndarray] = []

    for i in range(0, total, BATCH_SIZE):
        batch = texts[i: i + BATCH_SIZE]
        emb = model.encode(batch, normalize_embeddings=True, show_progress_bar=False)
        all_emb.append(emb.astype("float32"))
        done = min(i + BATCH_SIZE, total)
        print(f"    {done:>5,} / {total}", end="\r")

    print(f"\n  ✓ Embedded in {time.time() - t0:.1f}s")
    return np.vstack(all_emb)


# ── FAISS index ───────────────────────────────────────────────────────────────

def build_and_save(blocks: list[LyricBlock], embeddings: np.ndarray) -> None:
    try:
        import faiss  # type: ignore[import]
    except ImportError:
        print("ERROR: faiss-cpu not installed.")
        sys.exit(1)

    dim = embeddings.shape[1]
    index = faiss.IndexFlatIP(dim)
    index.add(embeddings)
    faiss.write_index(index, str(INDEX_PATH))

    # Build metadata — store only title + artist + lines (no full song text).
    meta = [
        {"title": b.title, "artist": b.artist, "lines": b.lines}
        for b in blocks
    ]
    with open(META_PATH, "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, separators=(",", ":"))

    print(f"  ✓ index.faiss  {INDEX_PATH.stat().st_size / 1_048_576:.2f} MB")
    print(f"  ✓ meta.json    {META_PATH.stat().st_size / 1_024:.1f} KB")


# ── Verification ──────────────────────────────────────────────────────────────

def verify(query: str = "amazing grace how sweet the sound") -> None:
    import faiss  # type: ignore[import]
    from sentence_transformers import SentenceTransformer  # type: ignore[import]

    if not INDEX_PATH.exists():
        return

    model = SentenceTransformer(EMBED_MODEL)
    index = faiss.read_index(str(INDEX_PATH))
    with open(META_PATH, encoding="utf-8") as f:
        meta = json.load(f)

    q = model.encode([query], normalize_embeddings=True).astype("float32")
    scores, indices = index.search(q, 3)

    print(f'\n  Smoke test — "{query}":')
    for score, idx in zip(scores[0], indices[0]):
        if idx < 0:
            continue
        m = meta[idx]
        print(f"    [{score:.3f}]  {m['title']} — {' / '.join(m['lines'][:2])}")


# ── Entry point ───────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(description="Build VerseFlow lyrics FAISS index")
    parser.add_argument("--source-dir", type=Path, default=SOURCE_DIR,
                        help="Directory containing .txt lyric files")
    parser.add_argument("--window", type=int, default=4,
                        help="Lines per lyric block (default: 4)")
    parser.add_argument("--stride", type=int, default=2,
                        help="Sliding window stride (default: 2)")
    parser.add_argument("--skip-verify", action="store_true")
    args = parser.parse_args()

    print("VerseFlow — Lyrics Index Builder")
    print("=" * 40)

    source_dir: Path = args.source_dir
    if not source_dir.exists():
        print(f"\n  Source directory not found: {source_dir}")
        print("  Creating it and adding a sample song for demonstration …")
        source_dir.mkdir(parents=True, exist_ok=True)
        _write_sample_song(source_dir)

    print(f"\n[1/3] Loading songs from {source_dir} …")
    blocks = load_all_songs(source_dir, window=args.window, stride=args.stride)

    if not blocks:
        print("\n  No lyrics found. Add .txt files to the source directory and re-run.")
        print(f"  Directory: {source_dir}")
        print("  See the script docstring for the expected file format.")
        sys.exit(0)

    print(f"  Total lyric blocks: {len(blocks):,}")

    print("\n[2/3] Generating embeddings …")
    embeddings = embed_blocks(blocks)

    print("\n[3/3] Building FAISS index …")
    build_and_save(blocks, embeddings)

    print(f"\n✓ Lyrics index built — {len(blocks):,} blocks from {source_dir}")

    if not args.skip_verify:
        verify()

    print("\nDone. Lyric search is now active.")


def _write_sample_song(dest: Path) -> None:
    """Write a public-domain sample so the pipeline can be tested immediately."""
    sample = """\
Title: Amazing Grace
Artist: John Newton (Public Domain, 1779)

Amazing grace! How sweet the sound
That saved a wretch like me!
I once was lost, but now am found
Was blind, but now I see.

'Twas grace that taught my heart to fear
And grace my fears relieved
How precious did that grace appear
The hour I first believed.

Through many dangers, toils and snares
I have already come
'Tis grace hath brought me safe thus far
And grace will lead me home.

The Lord has promised good to me
His word my hope secures
He will my shield and portion be
As long as life endures.

When we've been there ten thousand years
Bright shining as the sun
We've no less days to sing God's praise
Than when we'd first begun.
"""
    out = dest / "amazing_grace.txt"
    out.write_text(sample, encoding="utf-8")
    print(f"  Wrote sample: {out.name}")


if __name__ == "__main__":
    main()
