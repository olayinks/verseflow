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
from audio.capture import AudioCapture          # noqa: E402
from stt.engine import STTEngine                # noqa: E402
from analysis.bible_lookup import BibleLookup          # noqa: E402
from analysis.verse_detector import VerseDetector      # noqa: E402
from analysis.semantic_bible import SemanticBibleEngine  # noqa: E402
from analysis.semantic_lyrics import SemanticLyricsEngine  # noqa: E402


# ── Paths ─────────────────────────────────────────────────────────────────────

# Project root is always one level above this file (verseflow/).
# All relative paths in the config are resolved against this, so the sidecar
# works correctly regardless of the working directory it was launched from.
REPO_ROOT = Path(__file__).parent.parent

# ── Default config ────────────────────────────────────────────────────────────

DEFAULT_CONFIG: dict = {
    "port": int(os.environ.get("VERSEFLOW_PORT", 8765)),
    "whisper_model": "base.en",      # tiny.en | base.en | small.en | medium.en
    "whisper_device": "cpu",         # cpu | cuda
    "audio_device": os.environ.get("VERSEFLOW_AUDIO_DEVICE") or None,
    "sample_rate": 16000,
    "chunk_seconds": 0.5,
    "bible_index_path": "data/bibles/index.faiss",
    "bible_meta_path": "data/bibles/meta.json",
    "lyrics_index_path": "data/lyrics/index.faiss",
    "lyrics_meta_path": "data/lyrics/meta.json",
    "semantic_threshold": 0.60,
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
        AudioCapture  →  STTEngine  →  [VerseDetector, SemanticBibleEngine,
                                         SemanticLyricsEngine]
                      →  WebSocketServer (pushes events to Electron)
    """

    def __init__(self, config: dict) -> None:
        self.config = config
        self.server = WebSocketServer(port=config["port"])
        self.stt = STTEngine(
            model_name=config["whisper_model"],
            device=config["whisper_device"],
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
        self.audio = AudioCapture(
            device=config["audio_device"],
            sample_rate=config["sample_rate"],
            chunk_seconds=config["chunk_seconds"],
        )
        self._listening = False

    async def start(self) -> None:
        log.info("VerseFlow sidecar starting on port %d", self.config["port"])

        # Load engines (may download models on first run).
        await asyncio.gather(
            asyncio.to_thread(self.stt.load),
            asyncio.to_thread(self._bible_lookup.load),
            asyncio.to_thread(self.semantic_bible.load),
            asyncio.to_thread(self.semantic_lyrics.load),
        )

        # Start the WebSocket server.
        await self.server.start(on_command=self._handle_command)

        log.info("Sidecar ready — waiting for Electron to connect")

        # Notify Electron we are up.
        await self.server.broadcast({
            "type": "status",
            "payload": {"connected": True, "message": "Audio engine ready"},
        })

    async def _handle_command(self, command: str) -> None:
        """Handle commands sent from Electron (start / stop listening)."""
        if command == "start" and not self._listening:
            self._listening = True
            asyncio.create_task(self._run_audio_pipeline())
        elif command == "stop":
            self._listening = False
            self.audio.stop()

    async def _run_audio_pipeline(self) -> None:
        """Open the mic, feed audio chunks to STT, push results to Electron."""
        log.info("Starting audio pipeline")
        full_transcript = ""

        async for chunk in self.audio.stream():
            if not self._listening:
                break

            # Run STT in a thread (CPU-bound).
            result = await asyncio.to_thread(self.stt.transcribe_chunk, chunk)
            if not result:
                continue

            is_final = result["is_final"]
            text = result["text"]
            if is_final:
                full_transcript += " " + text

            # Push transcript to renderer.
            await self.server.broadcast({
                "type": "transcript",
                "payload": {
                    "text": text,
                    "isFinal": is_final,
                    "fullText": full_transcript.strip(),
                },
            })

            # Only run detection on stable (final) chunks to avoid noise.
            if is_final and text.strip():
                await self._run_detection(text, full_transcript)

        log.info("Audio pipeline stopped")

    async def _run_detection(self, chunk_text: str, full_text: str) -> None:
        """Run all detection engines on a finalised transcript chunk."""
        max_s = self.config["max_suggestions"]
        threshold = self.config["semantic_threshold"]

        # Explicit verse references (fast — regex, no ML). Run first so we can
        # skip semantic search when the preacher already cited a reference.
        explicit = await asyncio.to_thread(self.verse_detector.detect, chunk_text)
        for suggestion in explicit[:max_s]:
            await self.server.broadcast({"type": "verse_suggestion", "payload": suggestion})

        # Semantic engines are independent — run them in parallel.
        if len(explicit) < 2:
            tasks = [asyncio.to_thread(self.semantic_bible.query, full_text, max_s, threshold)]
            if self.config["lyrics_enabled"]:
                tasks.append(asyncio.to_thread(self.semantic_lyrics.query, full_text, max_s, threshold))

            results = await asyncio.gather(*tasks)
            sem_verses = results[0]
            sem_lyrics = results[1] if len(results) > 1 else []

            for suggestion in sem_verses:
                await self.server.broadcast({"type": "verse_suggestion", "payload": suggestion})
            for suggestion in sem_lyrics:
                await self.server.broadcast({"type": "lyric_suggestion", "payload": suggestion})

    async def shutdown(self) -> None:
        self._listening = False
        self.audio.stop()
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
