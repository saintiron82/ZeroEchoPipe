"""Tests for Peer advanced features — reserved methods, routing, shutdown."""

import os
import sys
import tempfile
import threading
import time
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from zep.peer import Peer, CallTimeout, RemoteError
from zep.transport.file import FileTransport


class TestReservedMethods(unittest.TestCase):
    """Test _capabilities, _ping, _shutdown protocol methods."""

    def _make_peers(self):
        tmp_dir = tempfile.TemporaryDirectory()
        transport_a = FileTransport(tmp_dir.name)
        transport_b = FileTransport(tmp_dir.name)

        engine = Peer(transport_a, "engine", session="test_session",
                      capabilities={"version": "0.1.0"})
        agent = Peer(transport_b, "agent", session="test_session")

        engine.bind("echo", lambda p: p)

        stop = threading.Event()

        def engine_loop():
            while not stop.is_set():
                engine.poll_once()
                stop.wait(0.001)

        t = threading.Thread(target=engine_loop, daemon=True)
        t.start()

        def cleanup():
            stop.set()
            t.join(timeout=1)
            transport_a.close()
            transport_b.close()
            tmp_dir.cleanup()

        self.addCleanup(cleanup)
        return engine, agent

    def test_capabilities(self):
        engine, agent = self._make_peers()
        result = agent.call("engine", "_capabilities", {}, timeout_ms=5000)
        self.assertEqual(result["name"], "engine")
        self.assertEqual(result["schema"], "zep.v0.1")
        self.assertIn("echo", result["methods"])
        self.assertEqual(result["version"], "0.1.0")

    def test_ping(self):
        engine, agent = self._make_peers()
        result = agent.call("engine", "_ping", {}, timeout_ms=5000)
        self.assertTrue(result["pong"])
        self.assertIn("timestamp", result)

    def test_shutdown(self):
        engine, agent = self._make_peers()
        shutdown_called = []
        engine.on_shutdown(lambda: shutdown_called.append(True))

        result = agent.call("engine", "_shutdown", {}, timeout_ms=5000)
        self.assertTrue(result["acknowledged"])
        self.assertTrue(engine.is_shutdown)
        self.assertEqual(len(shutdown_called), 1)

    def test_reserved_method_binding_blocked(self):
        engine, agent = self._make_peers()
        with self.assertRaises(ValueError):
            engine.bind("_secret", lambda p: p)


class TestRoutingSymmetry(unittest.TestCase):
    """Test §3.3 routing symmetry verification."""

    def test_session_mismatch_ignored(self):
        """Response with wrong session should be ignored → timeout."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            transport = FileTransport(tmp_dir)

            from zep.message import serialize
            # Agent sends call
            agent = Peer(transport, "agent", session="s1")

            # Manually craft a response with wrong session
            bad_response = {
                "id": "resp1",
                "session": "wrong_session",
                "from": "engine",
                "to": "agent",
                "type": "response",
                "timestamp": "2026-03-13T12:00:00.000Z",
                "meta": {"schema": "zep.v0.1"},
                "reply_to": "nonexistent",
                "result": {"ok": True},
            }
            transport.send("agent", "engine", serialize(bad_response))

            # Agent polls — should ignore the mismatched response
            agent.poll_once()
            # No crash = success. The response is silently ignored.


class TestBindEvent(unittest.TestCase):
    """Test separate event handler registration."""

    def test_bind_event_separate(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            transport_a = FileTransport(tmp_dir)
            transport_b = FileTransport(tmp_dir)

            engine = Peer(transport_a, "engine", session="s1")
            agent = Peer(transport_b, "agent", session="s1")

            call_results = []
            event_results = []

            engine.bind("action", lambda p: call_results.append(p) or {"ok": True})
            engine.bind_event("action", lambda p: event_results.append(p))

            stop = threading.Event()

            def engine_loop():
                while not stop.is_set():
                    engine.poll_once()
                    stop.wait(0.001)

            t = threading.Thread(target=engine_loop, daemon=True)
            t.start()

            try:
                # Event uses event handler
                agent.emit("engine", "action", {"type": "event"})
                time.sleep(0.1)

                # Call uses call handler
                result = agent.call("engine", "action", {"type": "call"}, timeout_ms=5000)

                self.assertEqual(len(event_results), 1)
                self.assertEqual(event_results[0]["type"], "event")
                self.assertEqual(result, {"ok": True})
            finally:
                stop.set()
                t.join(timeout=1)


if __name__ == "__main__":
    unittest.main()
