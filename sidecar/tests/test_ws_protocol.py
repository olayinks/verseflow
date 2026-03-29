"""
sidecar/tests/test_ws_protocol.py
───────────────────────────────────────────────────────────────────────────────
Integration tests for the WebSocket IPC server (ipc/server.py).

Tests the full message-exchange protocol between the server and a real
websockets client — no mocking of the network layer.

Run from the project root:
    py -3.13 -m pytest sidecar/tests/test_ws_protocol.py -v
"""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

import pytest
import websockets

sys.path.insert(0, str(Path(__file__).parent.parent))

from ipc.server import WebSocketServer

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

# Use a high ephemeral port to avoid conflicts with the real sidecar.
TEST_PORT = 18765


async def _start_server(port: int = TEST_PORT, on_command=None) -> WebSocketServer:
    srv = WebSocketServer(port=port)
    await srv.start(on_command=on_command or (lambda _: asyncio.sleep(0)))
    return srv


async def _connect(port: int = TEST_PORT):
    return await websockets.connect(f"ws://127.0.0.1:{port}")


# ---------------------------------------------------------------------------
# Connection tests
# ---------------------------------------------------------------------------

class TestConnection:
    @pytest.mark.asyncio
    async def test_client_can_connect(self):
        srv = await _start_server()
        try:
            ws = await _connect()
            # Ping round-trips if and only if the connection is alive.
            pong = await asyncio.wait_for(ws.ping(), timeout=2)
            assert pong is not None
            await ws.close()
        finally:
            await srv.stop()

    @pytest.mark.asyncio
    async def test_second_client_replaces_first(self):
        """Connecting a second client should close the first connection."""
        srv = await _start_server()
        try:
            ws1 = await _connect()
            ws2 = await _connect()
            # Give server time to process the new connection.
            await asyncio.sleep(0.2)
            # ws2 should be alive.
            await asyncio.wait_for(ws2.ping(), timeout=2)
            # ws1 should be closed — recv() raises ConnectionClosed.
            with pytest.raises(websockets.exceptions.ConnectionClosed):
                await asyncio.wait_for(ws1.recv(), timeout=1)
            await ws2.close()
        finally:
            await srv.stop()


# ---------------------------------------------------------------------------
# broadcast() tests
# ---------------------------------------------------------------------------

class TestBroadcast:
    @pytest.mark.asyncio
    async def test_broadcast_reaches_client(self):
        srv = await _start_server()
        try:
            ws = await _connect()
            msg = {"type": "status", "payload": {"connected": True}}
            await srv.broadcast(msg)
            raw = await asyncio.wait_for(ws.recv(), timeout=2)
            received = json.loads(raw)
            assert received["type"] == "status"
            assert received["payload"]["connected"] is True
            await ws.close()
        finally:
            await srv.stop()

    @pytest.mark.asyncio
    async def test_broadcast_without_client_does_not_raise(self):
        srv = await _start_server()
        try:
            # No client connected — broadcast should be silent no-op.
            await srv.broadcast({"type": "status", "payload": {}})
        finally:
            await srv.stop()

    @pytest.mark.asyncio
    async def test_broadcast_verse_suggestion_shape(self):
        srv = await _start_server()
        try:
            ws = await _connect()
            suggestion = {
                "id": "abc123",
                "kind": "explicit",
                "verse": {"reference": {"book": "John", "chapter": 3, "verse": 16}, "translation": "KJV", "text": "For God so loved…"},
                "score": 1.0,
                "triggerText": "John 3 16",
            }
            await srv.broadcast({"type": "verse_suggestion", "payload": suggestion})
            raw = await asyncio.wait_for(ws.recv(), timeout=2)
            received = json.loads(raw)
            assert received["type"] == "verse_suggestion"
            assert received["payload"]["id"] == "abc123"
            assert received["payload"]["verse"]["reference"]["book"] == "John"
            await ws.close()
        finally:
            await srv.stop()


# ---------------------------------------------------------------------------
# Command handling tests
# ---------------------------------------------------------------------------

class TestCommands:
    @pytest.mark.asyncio
    async def test_start_command_is_dispatched(self):
        received_commands: list[str] = []

        async def handler(cmd: str) -> None:
            received_commands.append(cmd)

        srv = await _start_server(on_command=handler)
        try:
            ws = await _connect()
            await ws.send(json.dumps({"type": "status", "payload": {"command": "start"}}))
            await asyncio.sleep(0.1)
            assert "start" in received_commands
            await ws.close()
        finally:
            await srv.stop()

    @pytest.mark.asyncio
    async def test_stop_command_is_dispatched(self):
        received_commands: list[str] = []

        async def handler(cmd: str) -> None:
            received_commands.append(cmd)

        srv = await _start_server(on_command=handler)
        try:
            ws = await _connect()
            await ws.send(json.dumps({"type": "status", "payload": {"command": "stop"}}))
            await asyncio.sleep(0.1)
            assert "stop" in received_commands
            await ws.close()
        finally:
            await srv.stop()

    @pytest.mark.asyncio
    async def test_invalid_json_does_not_crash_server(self):
        srv = await _start_server()
        try:
            ws = await _connect()
            await ws.send("not valid json {{{{")
            await asyncio.sleep(0.1)
            # Server should still be alive — a valid command should still work.
            received_commands: list[str] = []
            srv._on_command = lambda cmd: received_commands.append(cmd) or asyncio.sleep(0)
            await ws.send(json.dumps({"type": "status", "payload": {"command": "stop"}}))
            await asyncio.sleep(0.1)
            await ws.close()
        finally:
            await srv.stop()

    @pytest.mark.asyncio
    async def test_unknown_message_type_is_ignored(self):
        received_commands: list[str] = []

        async def handler(cmd: str) -> None:
            received_commands.append(cmd)

        srv = await _start_server(on_command=handler)
        try:
            ws = await _connect()
            await ws.send(json.dumps({"type": "unknown_type", "payload": {}}))
            await asyncio.sleep(0.1)
            assert received_commands == []
            await ws.close()
        finally:
            await srv.stop()
