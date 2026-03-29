"""
scripts/download_models.py
───────────────────────────────────────────────────────────────────────────────
Pre-download all ML models used by the sidecar so the first real run is
instant.  Run once after `pip install -r sidecar/requirements.txt`.

    python scripts/download_models.py

Models downloaded:
  1. faster-whisper  "base.en"    (~140 MB)  — speech-to-text
  2. sentence-transformers  "all-MiniLM-L6-v2"  (~90 MB)  — embeddings

Both are cached in the HuggingFace Hub cache directory:
  Windows:  %USERPROFILE%\.cache\huggingface\hub
  macOS/Linux: ~/.cache/huggingface/hub
"""

from __future__ import annotations

import sys

# Ensure UTF-8 output on Windows (cp1252 terminals can't print ✓ etc.)
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
import time
from pathlib import Path

# Make sure the sidecar package is importable.
sys.path.insert(0, str(Path(__file__).parent.parent / "sidecar"))


def download_whisper(model_name: str = "base.en") -> None:
    print(f"\n[1/2] Downloading Whisper model '{model_name}' …")
    t0 = time.time()
    try:
        from faster_whisper import WhisperModel
        # Instantiating the model triggers the download.
        WhisperModel(model_name, device="cpu", compute_type="int8")
        print(f"      ✓ Done in {time.time() - t0:.1f}s")
    except ImportError:
        print("      ✗ faster-whisper not installed — run: pip install faster-whisper")
        sys.exit(1)
    except Exception as e:
        print(f"      ✗ Failed: {e}")
        sys.exit(1)


def download_embedding_model(model_name: str = "all-MiniLM-L6-v2") -> None:
    print(f"\n[2/2] Downloading embedding model '{model_name}' …")
    t0 = time.time()
    try:
        from sentence_transformers import SentenceTransformer
        SentenceTransformer(model_name)
        print(f"      ✓ Done in {time.time() - t0:.1f}s")
    except ImportError:
        print("      ✗ sentence-transformers not installed — run: pip install sentence-transformers")
        sys.exit(1)
    except Exception as e:
        print(f"      ✗ Failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Pre-download VerseFlow ML models")
    parser.add_argument("--whisper-model", default="base.en",
                        choices=["tiny.en", "base.en", "small.en", "medium.en", "large-v3"],
                        help="Whisper model size (default: base.en)")
    parser.add_argument("--embed-model", default="all-MiniLM-L6-v2",
                        help="Sentence-transformers model (default: all-MiniLM-L6-v2)")
    args = parser.parse_args()

    print("VerseFlow — Model Downloader")
    print("=" * 40)

    download_whisper(args.whisper_model)
    download_embedding_model(args.embed_model)

    print("\n✓ All models ready. You can now run the sidecar.")
