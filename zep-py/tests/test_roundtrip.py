"""ZEP Roundtrip Test — two peers communicate via file transport."""

import os
import sys
import tempfile
import threading
import time
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from zep.peer import Peer, CallTimeout, RemoteError
from zep.transport.file import FileTransport


class TestRoundtrip(unittest.TestCase):

    def _make_peers(self):
        """Create a pair of peers connected via file transport."""
        tmp_dir = tempfile.TemporaryDirectory()
        self._tmp_dir = tmp_dir

        transport_a = FileTransport(tmp_dir.name)
        transport_b = FileTransport(tmp_dir.name)

        engine = Peer(transport_a, "engine", session="test_session")
        agent = Peer(transport_b, "agent", session="test_session")

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

    def test_basic_call(self):
        """Program peer registers method, agent peer calls it."""
        engine, agent = self._make_peers()
        engine.bind("get_status", lambda p: {"health": 100, "fps": 60})

        result = agent.call("engine", "get_status", {}, timeout_ms=5000)
        self.assertEqual(result, {"health": 100, "fps": 60})

    def test_echo(self):
        """Echo handler returns params as-is."""
        engine, agent = self._make_peers()
        engine.bind("echo", lambda p: p)

        result = agent.call("engine", "echo", {"msg": "hello"}, timeout_ms=5000)
        self.assertEqual(result, {"msg": "hello"})

    def test_unknown_method(self):
        """Calling an unregistered method raises METHOD_NOT_FOUND."""
        engine, agent = self._make_peers()

        with self.assertRaises(RemoteError) as ctx:
            agent.call("engine", "nonexistent", {}, timeout_ms=5000)
        self.assertEqual(ctx.exception.code, "METHOD_NOT_FOUND")

    def test_event(self):
        """Fire-and-forget event is received by the engine."""
        engine, agent = self._make_peers()
        received = []
        engine.bind("on_ping", lambda p: received.append(p))

        agent.emit("engine", "on_ping", {"ts": "2026-03-13T12:00:00.000Z"})

        time.sleep(0.1)
        engine.poll_once()

        self.assertEqual(len(received), 1)

    def test_timeout(self):
        """Extremely short timeout raises CallTimeout."""
        engine, agent = self._make_peers()

        with self.assertRaises(CallTimeout):
            agent.call("engine", "get_status", {}, timeout_ms=1)

    def test_internal_error(self):
        """Handler that raises an exception produces INTERNAL_ERROR."""
        engine, agent = self._make_peers()
        engine.bind("crash", lambda p: 1 / 0)

        with self.assertRaises(RemoteError) as ctx:
            agent.call("engine", "crash", {}, timeout_ms=5000)
        self.assertEqual(ctx.exception.code, "INTERNAL_ERROR")
        self.assertTrue(ctx.exception.retryable)


if __name__ == "__main__":
    unittest.main()
