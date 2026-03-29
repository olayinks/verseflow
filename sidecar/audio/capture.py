"""
sidecar/audio/capture.py
───────────────────────────────────────────────────────────────────────────────
Captures audio from a microphone (or system loopback) using sounddevice and
yields fixed-length numpy chunks for the STT engine.

Key design choices:
  - We use sounddevice's InputStream in callback mode, feeding an asyncio queue.
  - The generator is an async generator so the event loop is never blocked.
  - sample_rate = 16 kHz matches Whisper's expected input format.
  - chunk_seconds controls latency vs accuracy: 0.5s gives responsive streaming,
    larger values (2-3s) improve accuracy on slow hardware.
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import AsyncGenerator
from typing import Any

import numpy as np
import sounddevice as sd

log = logging.getLogger("verseflow.audio")


class AudioCapture:
    def __init__(
        self,
        device: int | str | None = None,
        sample_rate: int = 16_000,
        chunk_seconds: float = 0.5,
    ) -> None:
        self.device = device
        self.sample_rate = sample_rate
        self.chunk_frames = int(sample_rate * chunk_seconds)
        self._queue: asyncio.Queue[np.ndarray | None] = asyncio.Queue()
        self._stream: sd.InputStream | None = None
        self._loop: asyncio.AbstractEventLoop | None = None

    # ── Public ────────────────────────────────────────────────────────────────

    async def stream(self) -> AsyncGenerator[np.ndarray, None]:
        """
        Open the microphone and yield audio chunks (shape: [N], dtype: float32).
        Yields None sentinel on stop — the caller should break on that.
        """
        self._loop = asyncio.get_running_loop()
        self._stream = sd.InputStream(
            samplerate=self.sample_rate,
            channels=1,
            dtype="float32",
            blocksize=self.chunk_frames,
            device=self.device,
            callback=self._callback,
        )

        log.info(
            "Opening audio stream: device=%s  rate=%d Hz  chunk=%.2fs",
            self.device or "default",
            self.sample_rate,
            self.chunk_frames / self.sample_rate,
        )

        with self._stream:
            while True:
                chunk = await self._queue.get()
                if chunk is None:
                    break
                yield chunk

    def stop(self) -> None:
        """Signal the stream to stop by pushing a None sentinel."""
        if self._loop and not self._loop.is_closed():
            # Thread-safe call from any thread.
            self._loop.call_soon_threadsafe(self._queue.put_nowait, None)
        if self._stream and self._stream.active:
            self._stream.stop()

    # ── Internal ──────────────────────────────────────────────────────────────

    def _callback(
        self,
        indata: np.ndarray,
        frames: int,  # noqa: ARG002
        time: Any,    # noqa: ARG002
        status: sd.CallbackFlags,
    ) -> None:
        """Called by sounddevice on the audio thread — must be non-blocking."""
        if status:
            log.debug("Audio callback status: %s", status)
        if self._loop and not self._loop.is_closed():
            # Flatten to 1-D and copy (indata is a view that gets reused).
            chunk = indata[:, 0].copy()
            self._loop.call_soon_threadsafe(self._queue.put_nowait, chunk)

    # ── Device listing (utility) ──────────────────────────────────────────────

    @staticmethod
    def list_devices() -> list[dict]:
        """Return a list of available audio devices with their indices."""
        devices = []
        for idx, info in enumerate(sd.query_devices()):
            if info["max_input_channels"] > 0:  # type: ignore[index]
                devices.append({
                    "index": idx,
                    "name": info["name"],  # type: ignore[index]
                    "channels": info["max_input_channels"],  # type: ignore[index]
                    "sample_rate": int(info["default_samplerate"]),  # type: ignore[index]
                })
        return devices
