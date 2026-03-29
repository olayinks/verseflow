# verseflow_sidecar.spec
# ─────────────────────────────────────────────────────────────────────────────
# PyInstaller spec for the VerseFlow Python sidecar.
#
# Build from the project root:
#   pip install pyinstaller
#   pyinstaller sidecar/verseflow_sidecar.spec
#
# Output:  dist/verseflow-sidecar[.exe]
# The electron-builder then copies this binary into the app bundle via
# extraResources so Electron can spawn it in production.
# ─────────────────────────────────────────────────────────────────────────────

import sys
from pathlib import Path

ROOT = Path(SPECPATH).parent          # project root (verseflow/)
SIDECAR = ROOT / "sidecar"
DATA_DIR = ROOT / "data"

block_cipher = None

a = Analysis(
    [str(SIDECAR / "main.py")],
    pathex=[str(SIDECAR)],
    binaries=[],
    datas=[
        # Bible + lyrics indices are runtime data — bundled so the sidecar
        # finds them at a predictable relative path in the packaged app.
        (str(DATA_DIR / "bibles"),  "data/bibles"),
        (str(DATA_DIR / "lyrics"),  "data/lyrics"),
        (str(DATA_DIR / "models"),  "data/models"),
    ],
    hiddenimports=[
        # faster-whisper / CTranslate2
        "faster_whisper",
        "faster_whisper.transcribe",
        "ctranslate2",
        # sentence-transformers
        "sentence_transformers",
        "sentence_transformers.models",
        "sentence_transformers.losses",
        "transformers",
        "tokenizers",
        # FAISS
        "faiss",
        # Audio
        "sounddevice",
        "soundfile",
        "cffi",
        "_cffi_backend",
        # Utilities
        "numpy",
        "scipy",
        "scipy.special",
        "scipy.special._ufuncs",
        "sklearn",
        "sklearn.utils._cython_blas",
        "rapidfuzz",
        "regex",
        # WebSocket server
        "websockets",
        "websockets.legacy",
        "websockets.legacy.server",
        # Standard library extras commonly missed by the hook
        "asyncio",
        "logging",
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        # Exclude GUI toolkits — not needed in a headless sidecar.
        "tkinter",
        "matplotlib",
        "PIL",
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name="verseflow-sidecar",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,       # keep console so logs are visible (Electron captures stdout)
    disable_windowed_traceback=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
