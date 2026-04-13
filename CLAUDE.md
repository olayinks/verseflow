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
        ├─ stt/            RealtimeSTT (tiny.en partials + base.en finals, Silero VAD)
        ├─ analysis/       Verse + lyric detection engines
        ├─ ipc/            WebSocket server (port 8765)
        └─ training/       Speaker fine-tuning (optional)
        │
        │  Keyboard simulation
        │
  Presentation software (ProPresenter, PowerPoint, etc.)
```

**Communication:** Electron spawns the Python process via `SidecarManager`, then connects to it over WebSocket. All real-time events (transcripts, suggestions, status) flow over that socket.

**Startup order:** The WebSocket server starts first so Electron can connect immediately. AI engines (`stt`, `semantic_bible`, `semantic_lyrics`) load in the background via `asyncio.create_task(_load_engines())` and broadcast step-by-step status updates. The renderer queries the last-known status on mount via `IPC.GET_STATUS` to avoid missing messages that arrived before React's `useEffect` registered listeners.

---

## Tech stack

| Layer | Technology |
|---|---|
| Desktop shell | Electron 41 |
| UI | React 18, TypeScript, Tailwind CSS 4, Zustand |
| Build | electron-vite, Vite |
| IPC bridge | Electron contextBridge (`src/preload/`) |
| STT | RealtimeSTT — `tiny.en` for partials (~150 ms), `base.en` for finals; Silero VAD utterance detection |
| Semantic search | `multi-qa-MiniLM-L6-cos-v1` (retrieval-optimised) + FAISS IndexFlatIP |
| Audio | RealtimeSTT built-in capture (PyAudio / sounddevice underneath) |
| WebSocket | `ws` (Node) + `websockets` (Python asyncio) |
| Packaging | electron-builder (JS) + PyInstaller (Python sidecar) |

---

## Key files

| File | Purpose |
|---|---|
| `src/shared/types.ts` | All shared types: `WsMessage`, `Suggestion`, `AppSettings`, IPC channel names |
| `src/main/sidecar-manager.ts` | Spawns Python subprocess, manages WS client, reconnection; caches last status payload via `getLastStatus()` |
| `src/main/ipc/handlers.ts` | IPC handlers wired to renderer channels, including `GET_STATUS` |
| `src/main/python-resolver.ts` | Finds system Python installation |
| `src/preload/index.ts` | Context-isolated IPC bridge exposed to renderer; exposes `getStatus()` |
| `src/renderer/src/App.tsx` | Root React component, layout, keyboard wiring |
| `src/renderer/src/store/index.ts` | Zustand store — `engineState: EngineState` tracks `disconnected / loading / ready / error` |
| `src/renderer/src/hooks/useSidecar.ts` | Subscribes to IPC events; queries `getStatus()` on mount to sync engine state |
| `src/renderer/src/components/StatusBar.tsx` | Listen button (disabled until `engineState === 'ready'`), amber pulse while loading |
| `src/renderer/src/components/SuggestionCard.tsx` | Hover-to-reveal Send button; single click sends to presentation |
| `sidecar/main.py` | Sidecar entry point; WS server first, then background engine load with per-step status broadcasts |
| `sidecar/stt/engine.py` | RealtimeSTT wrapper — partial queue + final queue via asyncio |
| `sidecar/analysis/verse_detector.py` | Regex + keyword Bible verse detection |
| `sidecar/analysis/semantic_base.py` | FAISS-backed semantic search base class; uses `multi-qa-MiniLM-L6-cos-v1` |
| `sidecar/analysis/semantic_bible.py` | Embedding-based fuzzy verse matching |
| `sidecar/analysis/semantic_lyrics.py` | Embedding-based lyric matching |
| `sidecar/ipc/server.py` | asyncio WebSocket server; fires `on_connect` callback so current engine state is re-broadcast on every new connection |

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
npm run scripts:build-bible       # builds FAISS index with multi-qa-MiniLM-L6-cos-v1
npm run scripts:build-lyrics
```

> If you change the embedding model in `semantic_base.py`, you must re-run both build scripts — the runtime model and index model must match exactly.

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
| `transcript` | `{ text, isFinal, fullText }` | Partial / final speech text |
| `verse_suggestion` | `VerseSuggestion` | Detected Bible verse + confidence score |
| `lyric_suggestion` | `LyricSuggestion` | Matched worship song lyric |
| `status` | `{ state, connected, message }` | Engine state — `state` is `"loading" \| "ready" \| "error"` |
| `error` | `{ message }` | Error notifications |

Electron can send:
| `type` | Description |
|---|---|
| `start` | Begin listening |
| `stop` | Stop listening |
| `config` | Push updated settings |
| `train` | Trigger speaker training |

---

## Engine state lifecycle

```
disconnected → loading → ready
                       ↘ error
```

- `SidecarManager` stores `_lastStatus` every time a status payload is sent or received.
- On every new WS connection, `_handle_connect` in `sidecar/main.py` re-broadcasts the current state (race-condition guard).
- The renderer calls `api.getStatus()` (IPC `sidecar:get-status`) on mount and applies the result immediately after subscribing to `onStatus` — this handles the case where all status messages arrived before React's `useEffect` ran.
- `StatusBar.tsx` uses `engineState === 'ready'` as the sole gate for the Listen button. Never derive this from the `status.message` string.

---

## Semantic search

- **Model:** `multi-qa-MiniLM-L6-cos-v1` — asymmetric retrieval (short speech query vs longer verse document). Better than `all-MiniLM-L6-v2` for the modern-speech-to-KJV style gap.
- **Index:** FAISS `IndexFlatIP` over L2-normalised embeddings (cosine similarity = inner product).
- **Query:** The current utterance chunk (`chunk_text`), not the concatenated recent window. Focused signal outperforms noisy multi-sentence context for per-verse retrieval.
- **Triggered mode:** When a `_TRIGGER_PHRASE` is detected, threshold drops by 25% (`threshold * 0.75`) and text after the trigger phrase is used as the query.
- **Threshold tuning:** Default `semantic_threshold` is `0.45`. The dev-config can override this. Values above `0.55` will suppress valid paraphrases; values below `0.35` produce false positives.

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

Drivers live in `src/main/drivers/`. Each driver implements `IPresentationDriver` and sends a verse/lyric text to the target app via clipboard + keyboard simulation. Supported targets: ProPresenter, PowerPoint, EasyWorship, Keynote, OpenLP. The active driver is selected via `AppSettings.presentationDriver`.

**Sending flow:** Hovering a `SuggestionCard` reveals a Send button. Clicking it calls `onSend(text)` → `window.verseflow.sendToPresentation(text)` → `IPC.SEND_TO_PRESENTATION` → `getDriver(driver).send(text)`.

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
- Node 20+, Python 3.11+ (use `py -3.13` explicitly on Windows if multiple Python versions are installed — do not use bare `python`)
- Python sidecar runs as a child process; if it crashes, `SidecarManager` retries up to 10 times with a 2 s delay
- WebSocket port default: **8765**
- RealtimeSTT downloads Silero VAD and Whisper models on first run — this can take several minutes; the UI shows a loading state throughout
- `torch.hub.load("snakers4/silero-vad", ..., trust_repo=True)` must be called before `AudioToTextRecorder` init to avoid an interactive y/N prompt that hangs the sidecar on Windows
