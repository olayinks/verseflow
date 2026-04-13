"""
sidecar/main.py
───────────────────────────────────────────────────────────────────────────────
Entry point for the VerseFlow Python sidecar.

Usage:
    python main.py [config_path]

    config_path  – optional path to a JSON config file.
                   Defaults to ../data/dev-config.json relative to this file.

The sidecar:
  1. Reads configuration from a JSON file.
  2. Loads all detection engines (STT, verse detector, semantic engines).
  3. Starts an asyncio WebSocket server for Electron to connect to.
  4. Opens the audio capture stream.
  5. Runs until SIGINT / SIGTERM or the Electron parent process dies.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import signal
import sys
from pathlib import Path

import numpy as np

# ── Logging ───────────────────────────────────────────────────────────────────

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("verseflow.main")

# ── Local imports (resolved after sys.path is set) ───────────────────────────
# We add the sidecar directory to sys.path so imports work whether the sidecar
# is launched from its own directory or the project root.
sys.path.insert(0, str(Path(__file__).parent))

from ipc.server import WebSocketServer          # noqa: E402
from stt.engine import STTEngine                # noqa: E402
from analysis.bible_lookup import BibleLookup          # noqa: E402
from analysis.verse_detector import VerseDetector      # noqa: E402
from analysis.semantic_bible import SemanticBibleEngine  # noqa: E402
from analysis.semantic_lyrics import SemanticLyricsEngine  # noqa: E402

# ── Trigger phrases ───────────────────────────────────────────────────────────
# When the transcript contains one of these phrases, Bible search is given
# priority: threshold is lowered and lyrics are suppressed for that chunk.
# Patterns are lowercase; matching is case-insensitive substring search.

_TRIGGER_PHRASES: list[str] = [
    # Direct attribution to the Bible / God's word
    "the bible says",
    "the bible tells us",
    "the bible teaches",
    "the word says",
    "the word tells us",
    "the word of god says",
    "god's word says",
    "scripture says",
    "scripture tells us",
    "the scripture says",
    "according to scripture",
    "according to the bible",
    # Quotation framing
    "it is written",
    "as it is written",
    "as the bible says",
    "as scripture says",
    # Speaker attribution
    "jesus said",
    "jesus says",
    "god said",
    "god says",
    "the lord said",
    "the lord says",
    "paul said",
    "paul says",
    "peter said",
    "peter says",
    "isaiah said",
    "moses said",
    # Navigation cues
    "turn with me to",
    "open your bibles to",
    "open your bible to",
    "let us read from",
    "let's read from",
    "let me read from",
    "we read in",
    "we find in",
    "in the book of",
    # Generic preaching cues
    "the text says",
    "the passage says",
    "the verse says",
    "in our text",
    "this morning's text",
    "today's text",
    "today's scripture",
]


def _check_trigger(text: str) -> tuple[bool, str]:
    """
    Return (triggered, focus_text) where focus_text is the substring *after*
    the matched trigger phrase (used as the primary search query when available),
    falling back to the full text.
    """
    lower = text.lower()
    for phrase in _TRIGGER_PHRASES:
        idx = lower.find(phrase)
        if idx != -1:
            after = text[idx + len(phrase):].strip(" ,;:-")
            return True, after if len(after) > 8 else text
    return False, text


# ── Paths ─────────────────────────────────────────────────────────────────────

# Project root is always one level above this file (verseflow/).
# All relative paths in the config are resolved against this, so the sidecar
# works correctly regardless of the working directory it was launched from.
REPO_ROOT = Path(__file__).parent.parent

# ── Default config ────────────────────────────────────────────────────────────

DEFAULT_CONFIG: dict = {
    "port": int(os.environ.get("VERSEFLOW_PORT", 8765)),
    "whisper_model": "base.en",        # tiny.en | base.en | small.en | medium.en
    "whisper_device": "cpu",         # cpu | cuda
    "audio_device": os.environ.get("VERSEFLOW_AUDIO_DEVICE") or None,
    "bible_index_path": "data/bibles/index.faiss",
    "bible_meta_path": "data/bibles/meta.json",
    "lyrics_index_path": "data/lyrics/index.faiss",
    "lyrics_meta_path": "data/lyrics/meta.json",
    "semantic_threshold": 0.45,
    "max_suggestions": 5,
    "lyrics_enabled": True,
}

# Keys whose values are file paths that need to be resolved to absolute paths.
_PATH_KEYS = {
    "bible_index_path", "bible_meta_path",
    "lyrics_index_path", "lyrics_meta_path",
}


def load_config(config_path: str | None) -> dict:
    config = dict(DEFAULT_CONFIG)
    if config_path and Path(config_path).exists():
        with open(config_path, encoding="utf-8") as f:
            overrides = json.load(f)
        # Strip JSON comment keys before merging.
        overrides = {k: v for k, v in overrides.items() if not k.startswith("_")}
        config.update(overrides)
        log.info("Loaded config from %s", config_path)
    else:
        log.info("Using default config (no config file found at %s)", config_path)

    # Resolve relative paths against the project root so they work regardless
    # of which directory the sidecar process was launched from.
    for key in _PATH_KEYS:
        raw = config.get(key, "")
        if raw:
            resolved = (REPO_ROOT / raw).resolve()
            config[key] = str(resolved)
            log.debug("Resolved %s → %s", key, resolved)

    return config


# ── Pipeline wiring ───────────────────────────────────────────────────────────

class VerseFlowSidecar:
    """
    Wires all components together and manages the asyncio event loop.

    Data flow:
        RealtimeSTT (VAD-driven)  →  [VerseDetector, SemanticBibleEngine,
                                       SemanticLyricsEngine]
                                  →  WebSocketServer (pushes events to Electron)

    RealtimeSTT handles its own audio capture and uses Silero VAD to detect
    speech endpoints, so Whisper only runs on complete utterances.
    """

    def __init__(self, config: dict) -> None:
        self.config = config
        self.server = WebSocketServer(port=config["port"])
        self.stt = STTEngine(
            model_name=config["whisper_model"],
            device=config["whisper_device"],
            audio_device=config["audio_device"],
        )
        self._bible_lookup = BibleLookup(meta_path=config["bible_meta_path"])
        self.verse_detector = VerseDetector(lookup=self._bible_lookup)
        self.semantic_bible = SemanticBibleEngine(
            index_path=config["bible_index_path"],
            meta_path=config["bible_meta_path"],
            threshold=config["semantic_threshold"],
        )
        self.semantic_lyrics = SemanticLyricsEngine(
            index_path=config["lyrics_index_path"],
            meta_path=config["lyrics_meta_path"],
            threshold=config["semantic_threshold"],
            enabled=config["lyrics_enabled"],
        )
        self._listening = False
        self._engines_ready = False
        self._mode = "sermon"
        self._recent_window = 3

    async def start(self) -> None:
        log.info("VerseFlow sidecar starting on port %d", self.config["port"])

        # Start the WebSocket server FIRST so Electron can connect immediately
        # and receive status updates while the heavier engines are loading.
        # Previously engines loaded before the server started — this worked with
        # WhisperModel (fast) but breaks with RealtimeSTT which downloads Silero
        # VAD and tiny.en on first run, exhausting Electron's reconnect window.
        await self.server.start(on_command=self._handle_command, on_connect=self._handle_connect)
        log.info("WebSocket ready — waiting for Electron, loading engines in background")

        # Load engines in the background; broadcast status so the UI can show
        # a loading indicator while the user waits.
        asyncio.create_task(self._load_engines())

    async def _load_engines(self) -> None:
        """
        Load all AI engines sequentially in the background after the WS server
        is up.  Each step broadcasts a status message so the UI and console both
        show exactly what is happening — important because RealtimeSTT downloads
        Silero VAD and two Whisper models on first run which can take minutes.
        """
        async def _step(message: str, fn, *args) -> None:
            """Broadcast a status update, run fn(*args) in a thread, log timing."""
            log.info("[load] %s", message)
            await self.server.broadcast({
                "type": "status",
                "payload": {"state": "loading", "message": message},
            })
            t0 = asyncio.get_event_loop().time()
            await asyncio.to_thread(fn, *args)
            elapsed = asyncio.get_event_loop().time() - t0
            log.info("[load] done in %.1f s", elapsed)

        try:
            loop = asyncio.get_running_loop()

            # STT is first and slowest: Silero VAD + tiny.en + base.en are all
            # downloaded here on first run.  Log each sub-step from inside load().
            await _step(
                "Loading speech recognition (downloading models if needed)…",
                self.stt.load, loop,
            )
            await _step("Loading Bible index…",   self._bible_lookup.load)
            await _step("Loading verse embeddings…", self.semantic_bible.load)
            await _step("Loading lyric embeddings…", self.semantic_lyrics.load)

            self._engines_ready = True
            log.info("[load] All engines ready — VerseFlow is live")
            await self.server.broadcast({
                "type": "status",
                "payload": {"state": "ready", "connected": True, "message": "Ready"},
            })

        except Exception:
            log.exception("Engine load failed")
            await self.server.broadcast({
                "type": "error",
                "payload": {"message": "Failed to load engines — check the sidecar log"},
            })

    async def _handle_connect(self) -> None:
        """
        Called every time Electron opens a new WebSocket connection.
        Re-broadcasts the current engine state so the UI is always accurate,
        even if Electron reconnected after the initial 'ready' broadcast was sent.
        """
        if self._engines_ready:
            await self.server.broadcast({
                "type": "status",
                "payload": {"state": "ready", "connected": True, "message": "Ready"},
            })
        else:
            await self.server.broadcast({
                "type": "status",
                "payload": {"state": "loading", "message": "Loading AI engines…"},
            })

    async def _handle_command(self, command: str) -> None:
        """Handle commands sent from Electron (start / stop / set_mode)."""
        if command == "start" and not self._listening:
            if not self._engines_ready:
                await self.server.broadcast({
                    "type": "status",
                    "payload": {"state": "loading", "message": "Still loading engines, please wait…"},
                })
                return
            self._listening = True
            self.stt.start()
            asyncio.create_task(self._run_audio_pipeline())
        elif command == "stop":
            self._listening = False
            self.stt.stop()
        elif command.startswith("set_mode:"):
            mode = command.split(":", 1)[1]
            self._apply_mode(mode)

    def _apply_mode(self, mode: str) -> None:
        self._mode = mode
        if mode == "worship":
            self._recent_window = 2
        else:
            self._recent_window = 3
        log.info("Mode set to '%s'", mode)

    async def _run_audio_pipeline(self) -> None:
        """
        Consume partial and final transcript streams from RealtimeSTT and
        push results to Electron and the detection engines.

        RealtimeSTT uses Silero VAD to detect speech endpoints, so:
          - Partial updates  arrive every ~150 ms from the tiny.en model
            (fast, for live display — marked isFinal=False).
          - Final transcripts arrive after a natural speech pause from the
            main Whisper model (complete phrases — used for verse/lyric detection).
        No manual buffering or chunking is needed here.
        """
        log.info("Audio pipeline started (RealtimeSTT)")
        full_transcript = ""
        recent_chunks: list[str] = []

        async def _stream_partials() -> None:
            async for text in self.stt.partial_updates():
                if not self._listening:
                    break
                await self.server.broadcast({
                    "type": "transcript",
                    "payload": {
                        "text": text,
                        "isFinal": False,
                        "fullText": full_transcript.strip(),
                    },
                })

        async def _stream_finals() -> None:
            nonlocal full_transcript, recent_chunks
            async for text in self.stt.final_transcripts():
                if not self._listening:
                    break
                full_transcript += " " + text
                recent_chunks.append(text)
                if len(recent_chunks) > self._recent_window:
                    recent_chunks.pop(0)
                await self.server.broadcast({
                    "type": "transcript",
                    "payload": {
                        "text": text,
                        "isFinal": True,
                        "fullText": full_transcript.strip(),
                    },
                })
                await self._run_detection(text, " ".join(recent_chunks))

        await asyncio.gather(_stream_partials(), _stream_finals())
        log.info("Audio pipeline stopped")

    async def _run_detection(self, chunk_text: str, recent_text: str) -> None:
        """Run detection engines based on the current capture mode."""
        max_s = self.config["max_suggestions"]
        threshold = self.config["semantic_threshold"]
        worship_mode = self._mode == "worship"

        # ── Trigger phrase check ───────────────────────────────────────────────
        # If the chunk contains a phrase like "the Bible says" or "it is written",
        # force Bible-first search with a lower threshold and skip lyric matching
        # for this chunk (the preacher is clearly about to cite scripture).
        triggered, focus_text = _check_trigger(chunk_text)
        if triggered:
            log.info("Trigger phrase detected — forcing Bible search (focus: %r)", focus_text[:60])

        # ── Explicit verse references ─────────────────────────────────────────
        # Always active in both modes; cite "John 3:16" etc. directly.
        explicit = await asyncio.to_thread(self.verse_detector.detect, chunk_text)
        for suggestion in explicit[:max_s]:
            await self.server.broadcast({"type": "verse_suggestion", "payload": suggestion})

        if len(explicit) >= 2:
            return

        # ── Semantic engines ──────────────────────────────────────────────────
        # Triggered mode: Bible only, lower threshold, use text after the phrase.
        # Worship mode:   lyrics first, Bible secondary (slightly relaxed threshold).
        # Sermon mode:    Bible first, lyrics secondary.
        if triggered:
            # Use the focused text (after the trigger phrase) for the query, and
            # fall back to recent_text if the focused portion is too short.
            query = focus_text if len(focus_text) > 8 else recent_text
            trigger_threshold = threshold * 0.75  # ~33 % lower than normal
            sem_verses = await asyncio.to_thread(
                self.semantic_bible.query, query, max_s, trigger_threshold
            )
            for suggestion in sem_verses:
                await self.server.broadcast({"type": "verse_suggestion", "payload": suggestion})
            # No lyric search on triggered chunks — the context is clearly biblical.
            return

        # Use the current utterance as the primary query: it is the most
        # focused signal.  recent_text (last N chunks) provides broader context
        # but dilutes precision when earlier chunks cover a different topic.
        tasks = []
        if worship_mode:
            if self.config["lyrics_enabled"]:
                tasks.append(asyncio.to_thread(self.semantic_lyrics.query, chunk_text, max_s, threshold))
            tasks.append(asyncio.to_thread(self.semantic_bible.query, chunk_text, max_s, threshold * 1.1))
        else:
            tasks.append(asyncio.to_thread(self.semantic_bible.query, chunk_text, max_s, threshold))
            if self.config["lyrics_enabled"]:
                tasks.append(asyncio.to_thread(self.semantic_lyrics.query, chunk_text, max_s, threshold))

        results = await asyncio.gather(*tasks)

        if worship_mode:
            sem_lyrics = results[0] if self.config["lyrics_enabled"] else []
            sem_verses = results[-1]
        else:
            sem_verses = results[0]
            sem_lyrics = results[1] if len(results) > 1 else []

        for suggestion in sem_verses:
            await self.server.broadcast({"type": "verse_suggestion", "payload": suggestion})
        for suggestion in sem_lyrics:
            await self.server.broadcast({"type": "lyric_suggestion", "payload": suggestion})

    async def shutdown(self) -> None:
        self._listening = False
        self.stt.stop()
        await self.server.stop()
        log.info("Sidecar shut down cleanly")


# ── Main ──────────────────────────────────────────────────────────────────────

async def async_main(config_path: str | None) -> None:
    config = load_config(config_path)
    sidecar = VerseFlowSidecar(config)

    loop = asyncio.get_running_loop()

    def _handle_signal() -> None:
        log.info("Shutdown signal received")
        asyncio.create_task(sidecar.shutdown())
        loop.stop()

    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, _handle_signal)
        except NotImplementedError:
            # Windows does not support add_signal_handler.
            pass

    await sidecar.start()

    # Keep the event loop alive.
    try:
        await asyncio.Event().wait()
    except asyncio.CancelledError:
        pass
    finally:
        await sidecar.shutdown()


def main() -> None:
    config_path = sys.argv[1] if len(sys.argv) > 1 else None
    try:
        asyncio.run(async_main(config_path))
    except KeyboardInterrupt:
        log.info("Interrupted — goodbye")


if __name__ == "__main__":
    main()
