#!/usr/bin/env bash
set -euo pipefail

echo ""
echo " =================================================="
echo "  VerseFlow Setup"
echo " =================================================="
echo ""

# ── Check Node.js ──────────────────────────────────────────────────────────────
echo "[1/6] Checking Node.js..."
if ! command -v node &>/dev/null; then
  echo ""
  echo " ERROR: Node.js was not found."
  echo " Please install it from https://nodejs.org and re-run this script."
  echo ""
  exit 1
fi
echo "      Found $(node --version)"

# ── Check Python ───────────────────────────────────────────────────────────────
echo "[2/6] Checking Python..."
PYTHON=""
for cmd in python3 python; do
  if command -v "$cmd" &>/dev/null; then
    ver=$("$cmd" --version 2>&1)
    if [[ "$ver" == Python\ 3* ]]; then
      PYTHON="$cmd"
      break
    fi
  fi
done
if [[ -z "$PYTHON" ]]; then
  echo ""
  echo " ERROR: Python 3 was not found."
  echo " Please install it from https://python.org"
  echo ""
  exit 1
fi
echo "      Found $($PYTHON --version)"

# ── Install Node packages ──────────────────────────────────────────────────────
echo ""
echo "[3/6] Installing Node.js packages..."
npm install --legacy-peer-deps

# ── Install Python packages ────────────────────────────────────────────────────
echo ""
echo "[4/6] Installing Python packages (this may take several minutes)..."
$PYTHON -m pip install -r sidecar/requirements.txt

# ── Build Bible search index ───────────────────────────────────────────────────
echo ""
echo "[5/6] Building Bible search index..."
echo "      Downloads KJV (~10 MB) and builds the AI search index."
echo "      This may take 5-10 minutes on first run."
$PYTHON scripts/build_bible_index.py

# ── Build lyrics search index ──────────────────────────────────────────────────
echo ""
echo "[5/6] Building worship lyrics index..."
$PYTHON scripts/build_lyrics_index.py

# ── Download AI models ─────────────────────────────────────────────────────────
echo ""
echo "[6/6] Downloading AI speech recognition model (~150 MB)..."
echo "      This only happens once. Please wait..."
$PYTHON scripts/download_models.py

# ── Done ───────────────────────────────────────────────────────────────────────
echo ""
echo " =================================================="
echo "  Setup complete!"
echo " =================================================="
echo ""
echo " To start VerseFlow, open TWO terminals and run:"
echo ""
echo "   Terminal 1:  npm run sidecar:dev"
echo "   Terminal 2:  npm run dev"
echo ""
echo " Or in VS Code: Terminal menu → Run Task → Start VerseFlow"
echo ""
