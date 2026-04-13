"""
sidecar/tests/mock_sidecar.py
───────────────────────────────────────────────────────────────────────────────
Lightweight fake sidecar for testing the full IPC chain without loading any
ML models or opening a real microphone.

Run it instead of main.py:
    py -3.13 sidecar/tests/mock_sidecar.py

Then start Electron:
    npm run dev

Click "Listen" in the overlay — you will see fabricated transcript chunks,
verse suggestions, and lyric suggestions flowing through in real time,
proving the WebSocket → IPC → React pipeline is wired correctly end-to-end.

The mock replays a fixed script of events on a 1-second cadence.
"""

from __future__ import annotations

import asyncio
import json
import logging
import sys
from pathlib import Path

# Ensure UTF-8 output on Windows terminals.
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

sys.path.insert(0, str(Path(__file__).parent.parent))

import websockets

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("verseflow.mock")

PORT = int(__import__("os").environ.get("VERSEFLOW_PORT", 8765))

# ── Scripted event replay ─────────────────────────────────────────────────────

SCRIPT: list[dict] = [
    # (delay_s, message)
    {"delay": 1.0, "msg": {"type": "transcript", "payload": {
        "text": "For God so loved the world",
        "isFinal": False,
        "fullText": "",
    }}},
    {"delay": 1.0, "msg": {"type": "transcript", "payload": {
        "text": "For God so loved the world that he gave his only Son",
        "isFinal": True,
        "fullText": "For God so loved the world that he gave his only Son",
    }}},
    {"delay": 0.5, "msg": {"type": "verse_suggestion", "payload": {
        "id": "mock001",
        "kind": "explicit",
        "verse": {
            "reference": {"book": "John", "chapter": 3, "verse": 16},
            "translation": "KJV",
            "text": "For God so loved the world, that he gave his only begotten Son, that whosoever believeth in him should not perish, but have everlasting life.",
        },
        "score": 1.0,
        "triggerText": "For God so loved the world",
    }}},
    {"delay": 0.5, "msg": {"type": "verse_suggestion", "payload": {
        "id": "mock002",
        "kind": "semantic",
        "verse": {
            "reference": {"book": "Romans", "chapter": 5, "verse": 8},
            "translation": "KJV",
            "text": "But God commendeth his love toward us, in that, while we were yet sinners, Christ died for us.",
        },
        "score": 0.74,
        "triggerText": "For God so loved the world that he gave his only Son",
    }}},
    {"delay": 1.5, "msg": {"type": "transcript", "payload": {
        "text": "Amazing grace how sweet the sound",
        "isFinal": True,
        "fullText": "For God so loved the world that he gave his only Son. Amazing grace how sweet the sound",
    }}},
    {"delay": 0.5, "msg": {"type": "lyric_suggestion", "payload": {
        "id": "mock003",
        "kind": "lyric",
        "songTitle": "Amazing Grace",
        "artist": "John Newton (Public Domain)",
        "lines": [
            "Amazing grace! How sweet the sound",
            "That saved a wretch like me!",
        ],
        "score": 0.91,
        "triggerText": "Amazing grace how sweet the sound",
    }}},
    {"delay": 2.0, "msg": {"type": "transcript", "payload": {
        "text": "The Lord is my shepherd I shall not want",
        "isFinal": True,
        "fullText": "For God so loved the world ... The Lord is my shepherd I shall not want",
    }}},
    {"delay": 0.5, "msg": {"type": "verse_suggestion", "payload": {
        "id": "mock004",
        "kind": "explicit",
        "verse": {
            "reference": {"book": "Psalms", "chapter": 23, "verse": 1},
            "translation": "KJV",
            "text": "The LORD is my shepherd; I shall not want.",
        },
        "score": 1.0,
        "triggerText": "The Lord is my shepherd I shall not want",
    }}},
]


# ── WebSocket server ──────────────────────────────────────────────────────────

async def handler(ws: websockets.ServerConnection) -> None:
    log.info("Electron connected")
    listening = False

    async def replay() -> None:
        for entry in SCRIPT:
            await asyncio.sleep(entry["delay"])
            if not listening:
                break
            await ws.send(json.dumps(entry["msg"]))
            log.info("Sent: %s", entry["msg"]["type"])

    replay_task: asyncio.Task | None = None

    try:
        async for raw in ws:
            try:
                msg = json.loads(raw)
            except json.JSONDecodeError:
                continue

            if msg.get("type") == "status":
                command = msg.get("payload", {}).get("command")
                if command == "start" and not listening:
                    listening = True
                    log.info("Mock: start listening — replaying script")
                    replay_task = asyncio.create_task(replay())
                elif command == "stop":
                    listening = False
                    if replay_task:
                        replay_task.cancel()
                    log.info("Mock: stopped")
    except websockets.ConnectionClosedOK:
        log.info("Electron disconnected")
    finally:
        if replay_task:
            replay_task.cancel()


async def main() -> None:
    log.info("Mock sidecar starting on ws://127.0.0.1:%d", PORT)

    # Send ready status as soon as Electron connects.
    async def on_connect(ws: websockets.ServerConnection) -> None:
        await ws.send(json.dumps({
            "type": "status",
            "payload": {"connected": True, "message": "Mock audio engine ready"},
        }))
        await handler(ws)

    async with websockets.serve(on_connect, "127.0.0.1", PORT):
        log.info("Mock sidecar ready — start Electron and click Listen")
        await asyncio.Future()  # run forever


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        log.info("Mock sidecar stopped")
