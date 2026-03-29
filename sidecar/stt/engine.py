"""
sidecar/stt/engine.py
───────────────────────────────────────────────────────────────────────────────
Speech-to-text engine built on faster-whisper.

Why faster-whisper?
  - 4× faster than openai/whisper on CPU (uses CTranslate2 under the hood).
  - Supports int8 quantisation — runs well even on a modest laptop.
  - Streaming-friendly: we can transcribe short chunks and accumulate context.

Model sizes (base.en is the recommended dev default):
  tiny.en  ~ 75 MB  — very fast, lower accuracy
  base.en  ~ 140 MB — good balance for real-time use
  small.en ~ 460 MB — better accuracy, still real-time on modern CPUs
  medium.en~ 1.5 GB — best quality, may lag on CPU-only machines

Streaming strategy:
  We use a "rolling window" approach — each chunk is transcribed independently
  (faster-whisper has no streaming mode for partial transcripts). A VAD (Voice
  Activity Detection) pre-pass is used to skip silent frames so we don't waste
  compute. The full-text accumulation happens in main.py.
"""

from __future__ import annotations

import logging
from typing import TypedDict

import numpy as np

log = logging.getLogger("verseflow.stt")


class TranscriptResult(TypedDict):
    text: str
    is_final: bool
    language: str
    confidence: float


class STTEngine:
    def __init__(
        self,
        model_name: str = "base.en",
        device: str = "cpu",
        compute_type: str = "int8",
    ) -> None:
        self.model_name = model_name
        self.device = device
        self.compute_type = compute_type
        self._model = None  # Lazy-loaded in load()

    def load(self) -> None:
        """
        Download (if necessary) and load the Whisper model.
        Called once at startup in a background thread.
        Models are cached in ~/.cache/huggingface/hub/ by default.
        """
        from faster_whisper import WhisperModel  # type: ignore[import]

        log.info(
            "Loading Whisper model '%s' on %s (%s)",
            self.model_name,
            self.device,
            self.compute_type,
        )
        self._model = WhisperModel(
            self.model_name,
            device=self.device,
            compute_type=self.compute_type,
        )
        log.info("Whisper model loaded")

    def transcribe_chunk(self, audio: np.ndarray) -> TranscriptResult | None:
        """
        Transcribe a single audio chunk (float32, 16 kHz, mono).

        Returns None if the audio is silent or the model is not loaded.
        Returns a TranscriptResult dict with the recognised text.

        Note: faster-whisper always returns "final" segments — there are no
        partial hypotheses. We mark every result as final=True. Partial
        transcript UX is achieved by displaying results as they arrive.
        """
        if self._model is None:
            log.error("STTEngine.load() must be called before transcribe_chunk()")
            return None

        # Simple energy gate to avoid transcribing silence (saves CPU).
        rms = float(np.sqrt(np.mean(audio ** 2)))
        if rms < 0.002:
            return None

        segments, info = self._model.transcribe(
            audio,
            language="en",
            beam_size=5,
            vad_filter=True,         # Skip silent regions automatically.
            vad_parameters={
                "min_silence_duration_ms": 300,
            },
            condition_on_previous_text=False,  # Each chunk is independent.
        )

        # Collect all segment texts.
        texts = [seg.text.strip() for seg in segments if seg.text.strip()]
        if not texts:
            return None

        return TranscriptResult(
            text=" ".join(texts),
            is_final=True,
            language=info.language,
            confidence=getattr(info, "language_probability", 1.0),
        )
