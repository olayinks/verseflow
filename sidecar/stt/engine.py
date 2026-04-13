"""
sidecar/stt/engine.py
───────────────────────────────────────────────────────────────────────────────
Real-time speech-to-text engine built on RealtimeSTT (which uses faster-whisper
internally but adds proper VAD-driven utterance detection).

Why RealtimeSTT over raw faster-whisper chunking?
  The core problem with fixed-time chunking is that Whisper was trained on 30 s
  clips — it hallucates on short clips and cuts sentences mid-phrase when the
  chunk boundary doesn't align with a pause.  RealtimeSTT solves this with:

    1. Silero VAD + WebRTC VAD — detects actual speech endpoints, so Whisper
       only runs on complete utterances, never mid-word.
    2. Dual-model architecture — a tiny.en model emits partial updates every
       ~150 ms for display; the main model transcribes the full utterance once
       the speaker pauses for >= post_speech_silence_duration seconds.
    3. No manual buffer math — the library handles accumulation internally.

Architecture inside this class:
  - load()  — creates the AudioToTextRecorder; must receive the running event
               loop so callbacks can safely enqueue to asyncio from threads.
  - start() — spins up a daemon thread that calls recorder.text() in a loop.
               recorder.text() blocks until a complete utterance is ready, then
               returns the accurate final transcript.
  - The realtime callback fires on the tiny.en model every 150 ms and pushes
    partial strings into _partial_queue for live display.
  - partial_updates() / final_transcripts() are async generators that drain the
    two queues and yield strings to the asyncio pipeline in main.py.
"""

from __future__ import annotations

import asyncio
import logging
import threading
from collections.abc import AsyncGenerator

log = logging.getLogger("verseflow.stt")

# ── Domain vocabulary ─────────────────────────────────────────────────────────
# Passed as initial_prompt to bias Whisper toward correct spellings of Bible
# book names and sermon vocabulary regardless of speaker accent.
_BIBLE_PROMPT = (
    "Genesis Exodus Leviticus Numbers Deuteronomy Joshua Judges Ruth Samuel "
    "Kings Chronicles Ezra Nehemiah Esther Job Psalms Proverbs Ecclesiastes "
    "Isaiah Jeremiah Lamentations Ezekiel Daniel Hosea Joel Amos Obadiah "
    "Jonah Micah Nahum Habakkuk Zephaniah Haggai Zechariah Malachi "
    "Matthew Mark Luke John Acts Romans Corinthians Galatians Ephesians "
    "Philippians Colossians Thessalonians Timothy Titus Philemon Hebrews "
    "James Peter Jude Revelation "
    "chapter verse the Lord God Jesus Christ Holy Spirit scripture "
    "salvation grace mercy faith righteousness covenant"
)


class STTEngine:
    """
    Wraps RealtimeSTT's AudioToTextRecorder to provide async generators for
    partial and final transcripts.

    Usage (in main.py):
        engine = STTEngine(model_name="base.en", device="cpu")
        engine.load(asyncio.get_running_loop())
        engine.start()

        async for text in engine.partial_updates():
            ...   # live display

        async for text in engine.final_transcripts():
            ...   # detection pipeline
    """

    def __init__(
        self,
        model_name: str = "base.en",
        device: str = "cpu",
        compute_type: str = "int8",
        audio_device: int | str | None = None,
    ) -> None:
        self.model_name = model_name
        self.device = device
        self.compute_type = compute_type
        # RealtimeSTT expects an integer device index; ignore string names.
        self._input_device: int | None = (
            audio_device if isinstance(audio_device, int) else None
        )
        self._recorder = None
        self._loop: asyncio.AbstractEventLoop | None = None
        self._partial_queue: asyncio.Queue[str] = asyncio.Queue()
        self._final_queue: asyncio.Queue[str] = asyncio.Queue()
        self._running = False
        self._thread: threading.Thread | None = None

    # ── Lifecycle ─────────────────────────────────────────────────────────────

    def load(self, loop: asyncio.AbstractEventLoop) -> None:
        """
        Instantiate the AudioToTextRecorder.  Must be called from a thread
        with access to the running event loop (use asyncio.to_thread or pass
        the loop explicitly from the async context).

        First-run download sizes (cached in ~/.cache/huggingface/hub/):
          Silero VAD model  ~  2 MB
          tiny.en           ~ 75 MB   (real-time partial transcription)
          base.en           ~140 MB   (accurate final transcription)
        Subsequent runs load from cache and are much faster.
        """
        import time
        from RealtimeSTT import AudioToTextRecorder  # type: ignore[import]

        self._loop = loop

        def _on_partial(text: str) -> None:
            """Fires every ~150 ms from the tiny.en model — thread-safe push."""
            if text.strip() and self._loop and not self._loop.is_closed():
                self._loop.call_soon_threadsafe(
                    self._partial_queue.put_nowait, text.strip()
                )

        log.info(
            "STT init: main-model=%s  realtime-model=tiny.en  device=%s  compute=%s",
            self.model_name, self.device, self.compute_type,
        )
        log.info(
            "  First run will download: Silero VAD (~2 MB), tiny.en (~75 MB), %s (~%s)",
            self.model_name,
            "140 MB" if self.model_name == "base.en" else
            "460 MB" if self.model_name == "small.en" else "75 MB",
        )
        log.info("  Cached runs skip downloads — check %s", "~/.cache/huggingface/hub/")

        # ── Pre-trust Silero VAD ───────────────────────────────────────────────
        # RealtimeSTT loads Silero VAD via torch.hub.load(), which on first run
        # prints an interactive "do you trust this repo? (y/N)" prompt.  Since
        # the sidecar has no terminal attached, that prompt hangs forever.
        # Calling torch.hub.load(..., trust_repo=True) here first downloads and
        # caches the model with trust already given, so RealtimeSTT's call hits
        # the cache silently on all subsequent loads.
        log.info("  [1/3] Trusting and caching Silero VAD…")
        try:
            import torch
            torch.hub.load(
                "snakers4/silero-vad",
                "silero_vad",
                trust_repo=True,
            )
            log.info("  [1/3] Silero VAD ready")
        except Exception:
            log.exception("  [1/3] Silero VAD pre-load failed (RealtimeSTT may still work if cached)")

        log.info("  [2/3] Loading tiny.en (fast partial transcription)…")
        log.info("  [3/3] Loading %s (accurate final transcription)…", self.model_name)
        log.info("        (faster-whisper will download models if not cached — this is the slow step)")

        t0 = time.monotonic()
        self._recorder = AudioToTextRecorder(
            # Main model for accurate final transcription.
            model=self.model_name,
            # Tiny model for fast partial display updates.
            realtime_model_type="tiny.en",
            language="en",
            device=self.device,
            compute_type=self.compute_type,
            input_device_index=self._input_device,
            # VAD sensitivity — 0.4 balances false positives vs missed speech.
            silero_sensitivity=0.4,
            # WebRTC aggressiveness: 0 (least) – 3 (most).  2 suits a
            # close-talk mic in a moderately noisy church environment.
            webrtc_sensitivity=2,
            # How long silence must last before the utterance is considered done.
            post_speech_silence_duration=0.5,
            # Ignore clips shorter than this (coughs, mic bumps, etc.).
            min_length_of_recording=0.5,
            # Gap between recordings — prevents rapid re-triggering.
            min_gap_between_recordings=0.1,
            # Enable the real-time partial-update callback.
            enable_realtime_transcription=True,
            # How often the tiny.en model reruns on accumulating audio.
            realtime_processing_pause=0.15,
            on_realtime_transcription_update=_on_partial,
            on_realtime_transcription_stabilized=_on_partial,
            initial_prompt=_BIBLE_PROMPT,
            # Suppress RealtimeSTT's own console logging; we use our logger.
            spinner=False,
        )
        log.info("STT engine ready (%.1f s)", time.monotonic() - t0)

    def start(self) -> None:
        """Spin up the blocking recorder loop in a daemon thread."""
        if self._recorder is None:
            raise RuntimeError("STTEngine.load() must be called before start()")
        self._running = True
        self._thread = threading.Thread(
            target=self._recorder_loop, daemon=True, name="realtime-stt"
        )
        self._thread.start()
        log.info("RealtimeSTT recorder thread started")

    def stop(self) -> None:
        """Signal the recorder to stop and wait for the thread to exit."""
        self._running = False
        if self._recorder:
            try:
                self._recorder.stop()
            except Exception:
                pass
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=3.0)
        log.info("RealtimeSTT recorder stopped")

    # ── Async generators ──────────────────────────────────────────────────────

    async def partial_updates(self) -> AsyncGenerator[str, None]:
        """
        Yields partial transcript strings as they arrive from the tiny.en model.
        Use for live display in the UI.  These are NOT used for detection.
        """
        while self._running:
            try:
                text = await asyncio.wait_for(self._partial_queue.get(), timeout=0.5)
                yield text
            except asyncio.TimeoutError:
                continue

    async def final_transcripts(self) -> AsyncGenerator[str, None]:
        """
        Yields complete utterances after the speaker pauses.
        These are accurate full phrases — use for detection engines.
        """
        while self._running:
            try:
                text = await asyncio.wait_for(self._final_queue.get(), timeout=0.5)
                yield text
            except asyncio.TimeoutError:
                continue

    # ── Internal ──────────────────────────────────────────────────────────────

    def _recorder_loop(self) -> None:
        """
        Runs recorder.text() in a tight loop.  recorder.text() blocks until
        Silero VAD detects end-of-speech, then returns the accurate transcript
        from the main Whisper model.  Each result is pushed to the final queue.
        """
        try:
            while self._running:
                text: str = self._recorder.text()
                if text and text.strip() and self._running:
                    if self._loop and not self._loop.is_closed():
                        self._loop.call_soon_threadsafe(
                            self._final_queue.put_nowait, text.strip()
                        )
        except Exception:
            log.exception("RealtimeSTT recorder loop encountered an error")
