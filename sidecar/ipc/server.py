"""
sidecar/ipc/server.py
───────────────────────────────────────────────────────────────────────────────
asyncio WebSocket server that Electron connects to as a CLIENT.

Design decisions:
  - We accept only ONE connection at a time (the Electron main process).
    If a second client connects, the first is dropped — this prevents stale
    connections from accumulating across hot-reloads in dev.
  - Messages are JSON objects with a top-level "type" discriminant.
  - Commands from Electron arrive as:
      {"type": "status", "payload": {"command": "start" | "stop"}}
"""

from __future__ import annotations

import asyncio
import json
import logging
from collections.abc import Awaitable, Callable
from typing import Any

import websockets
from websockets.server import WebSocketServerProtocol

log = logging.getLogger("verseflow.ipc")

CommandHandler = Callable[[str], Awaitable[None]]


class WebSocketServer:
    def __init__(self, port: int = 8765) -> None:
        self.port = port
        self._client: WebSocketServerProtocol | None = None
        self._server: websockets.WebSocketServer | None = None
        self._on_command: CommandHandler | None = None

    # ── Public API ────────────────────────────────────────────────────────────

    async def start(self, on_command: CommandHandler) -> None:
        self._on_command = on_command
        self._server = await websockets.serve(
            self._handler,
            host="127.0.0.1",
            port=self.port,
            ping_interval=20,
            ping_timeout=10,
        )
        log.info("WebSocket server listening on ws://127.0.0.1:%d", self.port)

    async def stop(self) -> None:
        if self._server:
            self._server.close()
            await self._server.wait_closed()
            log.info("WebSocket server stopped")

    async def broadcast(self, msg: dict[str, Any]) -> None:
        """Send a JSON message to the connected Electron client."""
        if self._client is None:
            return
        try:
            await self._client.send(json.dumps(msg))
        except websockets.ConnectionClosed:
            log.debug("Tried to send to closed connection — client disconnected")
            self._client = None

    # ── Internal ──────────────────────────────────────────────────────────────

    async def _handler(self, ws: WebSocketServerProtocol) -> None:
        """Called once per incoming connection."""
        # Drop any existing client and take the new one.
        if self._client is not None:
            log.warning("Replacing existing client connection")
            await self._client.close()

        self._client = ws
        log.info("Electron connected from %s", ws.remote_address)

        try:
            async for raw in ws:
                await self._handle_message(raw)
        except websockets.ConnectionClosedOK:
            log.info("Electron disconnected gracefully")
        except websockets.ConnectionClosedError as e:
            log.warning("Electron connection closed with error: %s", e)
        finally:
            if self._client is ws:
                self._client = None

    async def _handle_message(self, raw: str | bytes) -> None:
        try:
            msg = json.loads(raw)
        except json.JSONDecodeError:
            log.error("Received invalid JSON: %r", raw)
            return

        msg_type = msg.get("type")
        payload = msg.get("payload", {})

        if msg_type == "status":
            command = payload.get("command")
            if command and self._on_command:
                await self._on_command(command)
        else:
            log.debug("Unhandled message type: %s", msg_type)
