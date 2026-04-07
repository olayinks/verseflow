"""
sidecar/training/trainer.py
───────────────────────────────────────────────────────────────────────────────
Fine-tunes openai/whisper-small.en on speaker-recorded samples and converts
the result to CTranslate2 format so faster-whisper can load it.

Usage (called by Electron main process):
    python trainer.py <manifest_path> <output_dir>

    manifest_path  – path to training/manifest.json
    output_dir     – where to write the CTranslate2 model

Progress is reported on stdout as:
    PROGRESS:<0-100>

Requires (install from requirements-training.txt):
    torch, transformers, datasets, soundfile, librosa, ctranslate2
"""

from __future__ import annotations

import json
import logging
import os
import sys
import tempfile
from pathlib import Path

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("verseflow.trainer")

BASE_MODEL = "openai/whisper-small.en"
SAMPLE_RATE = 16_000
MIN_SAMPLES = 5          # Hard minimum; more = better
MAX_STEPS = 200          # Enough for quick personalisation; raise for more data


def progress(pct: int) -> None:
    print(f"PROGRESS:{pct}", flush=True)


def load_manifest(manifest_path: str) -> list[dict]:
    with open(manifest_path, encoding="utf-8") as f:
        samples = json.load(f)
    valid = [s for s in samples if Path(s["audioFile"]).exists() and s.get("transcript")]
    log.info("Loaded %d valid samples from manifest", len(valid))
    return valid


def build_dataset(samples: list[dict]):
    """Convert manifest entries into a HuggingFace Dataset."""
    import soundfile as sf
    import numpy as np
    from datasets import Dataset, Audio  # type: ignore[import]

    rows: list[dict] = []
    for s in samples:
        try:
            audio_array, sr = sf.read(s["audioFile"], dtype="float32")
            # Resample to 16 kHz if needed.
            if sr != SAMPLE_RATE:
                import librosa  # type: ignore[import]
                audio_array = librosa.resample(audio_array, orig_sr=sr, target_sr=SAMPLE_RATE)
            # Ensure mono.
            if audio_array.ndim > 1:
                audio_array = audio_array.mean(axis=1)
            rows.append({
                "audio": {"array": audio_array.astype(np.float32), "sampling_rate": SAMPLE_RATE},
                "sentence": s["transcript"],
            })
        except Exception as e:
            log.warning("Skipping sample %s: %s", s["id"], e)

    if not rows:
        raise RuntimeError("No valid audio samples could be loaded.")

    ds = Dataset.from_list(rows)
    ds = ds.cast_column("audio", Audio(sampling_rate=SAMPLE_RATE))
    return ds


def train(manifest_path: str, output_dir: str) -> None:
    samples = load_manifest(manifest_path)
    if len(samples) < MIN_SAMPLES:
        raise RuntimeError(
            f"Need at least {MIN_SAMPLES} samples to train (have {len(samples)})."
        )

    progress(5)
    log.info("Loading base model: %s", BASE_MODEL)

    from transformers import (  # type: ignore[import]
        WhisperForConditionalGeneration,
        WhisperProcessor,
        Seq2SeqTrainer,
        Seq2SeqTrainingArguments,
    )
    import torch

    processor = WhisperProcessor.from_pretrained(BASE_MODEL)
    model = WhisperForConditionalGeneration.from_pretrained(BASE_MODEL)
    model.config.forced_decoder_ids = None
    model.config.suppress_tokens = []

    progress(15)
    log.info("Building dataset from %d samples", len(samples))
    dataset = build_dataset(samples)

    def preprocess(batch):
        audio = batch["audio"]
        inputs = processor(
            audio["array"],
            sampling_rate=audio["sampling_rate"],
            return_tensors="pt",
        )
        batch["input_features"] = inputs.input_features[0]
        labels = processor.tokenizer(batch["sentence"]).input_ids
        batch["labels"] = labels
        return batch

    dataset = dataset.map(preprocess, remove_columns=dataset.column_names)
    progress(25)

    # Use a small collator that pads labels to the same length.
    import dataclasses
    from typing import Any

    @dataclasses.dataclass
    class DataCollator:
        processor: Any

        def __call__(self, features):
            import torch
            input_features = torch.stack([
                torch.tensor(f["input_features"]) for f in features
            ])
            label_features = [{"input_ids": f["labels"]} for f in features]
            batch = self.processor.tokenizer.pad(
                label_features, return_tensors="pt"
            )
            labels = batch["input_ids"].masked_fill(
                batch["attention_mask"].ne(1), -100
            )
            return {"input_features": input_features, "labels": labels}

    collator = DataCollator(processor=processor)

    with tempfile.TemporaryDirectory() as tmpdir:
        training_args = Seq2SeqTrainingArguments(
            output_dir=tmpdir,
            per_device_train_batch_size=2,
            gradient_accumulation_steps=2,
            learning_rate=1e-5,
            max_steps=MAX_STEPS,
            warmup_steps=10,
            predict_with_generate=False,
            fp16=torch.cuda.is_available(),
            logging_steps=10,
            save_steps=MAX_STEPS,
            report_to="none",
        )

        class ProgressCallback:
            """Push PROGRESS lines at training milestones."""
            def on_log(self, args, state, control, logs=None, **kwargs):
                pct = 25 + int((state.global_step / MAX_STEPS) * 65)
                progress(min(pct, 89))

        from transformers import TrainerCallback  # type: ignore[import]

        class _Cb(TrainerCallback):
            def on_log(self, args, state, control, logs=None, **kwargs):
                pct = 25 + int((state.global_step / MAX_STEPS) * 65)
                progress(min(pct, 89))

        trainer = Seq2SeqTrainer(
            model=model,
            args=training_args,
            train_dataset=dataset,
            data_collator=collator,
            callbacks=[_Cb()],
        )

        log.info("Starting fine-tuning (%d steps)", MAX_STEPS)
        trainer.train()
        progress(90)

        # Save the HuggingFace model to a temp location for conversion.
        hf_model_path = Path(tmpdir) / "hf_model"
        model.save_pretrained(str(hf_model_path))
        processor.save_pretrained(str(hf_model_path))

    # Convert to CTranslate2 format for faster-whisper.
    # ct2-transformers-converter is the official CLI tool bundled with ctranslate2.
    progress(92)
    log.info("Converting to CTranslate2 format → %s", output_dir)
    Path(output_dir).mkdir(parents=True, exist_ok=True)

    import subprocess
    result = subprocess.run(
        [
            sys.executable, "-m", "ctranslate2.tools.ct2_transformers_converter",
            "--model", str(hf_model_path),
            "--output_dir", output_dir,
            "--quantization", "int8",
            "--force",
        ],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise RuntimeError(
            f"CTranslate2 conversion failed:\n{result.stderr}"
        )

    progress(100)
    log.info("Training complete. Custom model saved to %s", output_dir)


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: trainer.py <manifest_path> <output_dir>", file=sys.stderr)
        sys.exit(1)

    try:
        train(sys.argv[1], sys.argv[2])
    except Exception as e:
        log.error("Training failed: %s", e)
        sys.exit(1)
