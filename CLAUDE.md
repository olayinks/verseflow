# VerseFlow — Claude Code Project Guide

## What this project is

VerseFlow is a real-time Bible verse and worship lyric suggestion tool for church services. It listens to a pastor or worship leader via microphone, transcribes speech with OpenAI Whisper, and automatically surfaces relevant Bible verses and song lyrics in a floating overlay so operators can send them to presentation software (ProPresenter, PowerPoint, EasyWorship, Keynote, OpenLP).

---

## Architecture

```
Electron (TypeScript/React)
  └─ Main process          src/main/
  └─ Preload bridge        src/preload/
  └─ Renderer (React UI)   src/renderer/src/
        │
        │  WebSocket  ws://localhost:8765
        │
  Python Sidecar           sidecar/
        ├─ audio/          PyAudio mic capture
        ├─ stt/            Whisper STT (small.en, CT2)
        ├─ analysis/       Verse + lyric detection engines
        ├─ inference/      Model loading
        ├─ ipc/            WebSocket server (port 8765)
        └─ training/       Speaker fine-tuning (optional)
        │
        │  Keyboard simulation
        │
  Presentation software (ProPresenter, PowerPoint, etc.)
```

**Communication:** Electron spawns the Python process via `SidecarManager`, then connects to it over WebSocket. All real-time events (transcripts, suggestions, status) flow over that socket.

---

## Tech stack

| Layer | Technology |
|---|---|
| Desktop shell | Electron 41 |
| UI | React 18, TypeScript, Tailwind CSS 4, Zustand |
| Build | electron-vite, Vite |
| IPC bridge | Electron contextBridge (`src/preload/`) |
| STT | OpenAI Whisper `small.en` via `faster-whisper` (CTranslate2) |
| Semantic search | Sentence Transformers embeddings |
| Audio | PyAudio / sounddevice |
| WebSocket | `ws` (Node) + `websockets` (Python asyncio) |
| Packaging | electron-builder (JS) + PyInstaller (Python sidecar) |

---

## Key files

| File | Purpose |
|---|---|
| `src/shared/types.ts` | All shared types: `WsMessage`, `Suggestion`, `AppSettings`, IPC channel names |
| `src/main/sidecar-manager.ts` | Spawns Python subprocess, manages WS client, reconnection logic |
| `src/main/ipc/handlers.ts` | IPC handlers wired to renderer channels |
| `src/main/python-resolver.ts` | Finds system Python installation |
| `src/preload/index.ts` | Context-isolated IPC bridge exposed to renderer |
| `src/renderer/src/App.tsx` | Root React component, layout, keyboard wiring |
| `src/renderer/src/store/index.ts` | Zustand store (app state) |
| `sidecar/main.py` | Sidecar entry point; initialises all engines, starts WS server |
| `sidecar/stt/engine.py` | Whisper STT engine |
| `sidecar/analysis/verse_detector.py` | Regex + keyword Bible verse detection |
| `sidecar/analysis/semantic_bible.py` | Embedding-based fuzzy verse matching |
| `sidecar/analysis/semantic_lyrics.py` | Embedding-based lyric matching |
| `sidecar/ipc/server.py` | asyncio WebSocket server (port 8765) |

---

## Development workflow

```bash
# Two terminals needed
npm run dev           # Electron app (auto-spawns sidecar in dev)
npm run sidecar:dev   # Python sidecar standalone (alternative)

# Or use a mock sidecar for UI work without Python
npm run sidecar:mock
```

**First-time setup:**
```bash
npm install
pip install -r sidecar/requirements.txt
npm run scripts:download-models   # ~1.5 GB (Whisper + embeddings)
npm run scripts:build-bible
npm run scripts:build-lyrics
```

---

## Common tasks

```bash
# Tests
npm test              # JS tests (Vitest)
npm run test:py       # Python tests (pytest)

# Type / lint
npm run typecheck
npm run lint
npm run format

# Build & package
npm run build         # Compile TS + React
npm run sidecar:build # PyInstaller → dist/
npm run dist:win      # Full Windows installer
npm run dist:mac      # Full macOS build
```

---

## WebSocket message types

Defined in `src/shared/types.ts`. The sidecar emits:

| `type` | Payload | Description |
|---|---|---|
| `transcript` | `{ text, isFinal }` | Partial / final speech text |
| `verse_suggestion` | `VerseSuggestion` | Detected Bible verse + confidence score |
| `lyric_suggestion` | `LyricSuggestion` | Matched worship song lyric |
| `status` | `{ state, message }` | Engine state changes |
| `error` | `{ message }` | Error notifications |

Electron can send:
| `type` | Description |
|---|---|
| `start` | Begin listening |
| `stop` | Stop listening |
| `config` | Push updated settings |
| `train` | Trigger speaker training |

---

## Modes

- **Sermon** — Optimises for spoken word; Bible verse matching prioritised; lyrics suppressed
- **Worship** — Optimises for singing; lyric matching prioritised

Mode is stored in `AppSettings.mode` and forwarded to the sidecar as part of the config message.

---

## Trigger phrase detection

`sidecar/main.py` maintains `_TRIGGER_PHRASES` — a list of phrases like `"the bible says"`, `"it is written"`, `"turn with me to"`. When detected in the transcript, Bible search threshold is lowered and lyrics are suppressed for that chunk. To add a new trigger phrase, append to `_TRIGGER_PHRASES`.

---

## Presentation software integration

Drivers live in `src/main/drivers/`. Each driver implements a common interface and sends a verse/lyric search query to the target app via keyboard simulation. Supported targets: ProPresenter, PowerPoint, EasyWorship, Keynote, OpenLP. The active driver is selected via `AppSettings.driver`.

---

## Data directories

```
data/
  bibles/     Bible translation JSON indices (built by scripts:build-bible)
  lyrics/     Worship song lyric indices (built by scripts:build-lyrics)
  models/     AI model weights (Whisper CT2, Sentence Transformers)
```

---

## Speaker training (optional)

Records voice samples → fine-tunes Whisper → saves custom model to `data/models/custom-whisper-ct2/`. Requires `sidecar/requirements-training.txt` (PyTorch, transformers). Training is initiated from the SettingsPanel UI or via `npm run sidecar:train`.

---

## Environment notes

- Platform: Windows 11 (primary), macOS 12+ (supported)
- Node 20+, Python 3.11+
- Python sidecar runs as a child process; if it crashes, `SidecarManager` retries up to 10 times with a 2 s delay
- WebSocket port default: **8765**
