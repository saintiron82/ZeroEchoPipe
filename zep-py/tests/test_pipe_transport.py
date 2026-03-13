"""ZEP Pipe Transport tests — Named Pipe (FIFO), no server/client."""

import os
import sys
import tempfile
import threading
import time
import unittest

if sys.platform == "win32":
    raise unittest.SkipTest("PipeTransport not available on Windows")

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from zep.peer import Peer, CallTimeout, RemoteError
from zep.transport.pipe import PipeTransport


class TestPipeRoundtrip(unittest.TestCase):
    """Two peers communicate via PipeTransport — no server, no client."""

    def test_basic_call(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            # Both use same path. No server, no client.
            transport_a = PipeTransport(tmp_dir)
            transport_b = PipeTransport(tmp_dir)

            engine = Peer(transport_a, "engine", session="s1")
            agent = Peer(transport_b, "agent", session="s1")

            engine.bind("get_status", lambda p: {"health": 100})

            stop = threading.Event()

            def engine_loop():
                while not stop.is_set():
                    engine.poll_once()
                    stop.wait(0.001)

            t = threading.Thread(target=engine_loop, daemon=True)
            t.start()

            try:
                result = agent.call("engine", "get_status", {}, timeout_ms=5000)
                self.assertEqual(result, {"health": 100})
            finally:
                stop.set()
                t.join(timeout=1)
                transport_a.close()
                transport_b.close()

    def test_unknown_method(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            transport_a = PipeTransport(tmp_dir)
            transport_b = PipeTransport(tmp_dir)

            engine = Peer(transport_a, "engine", session="s1")
            agent = Peer(transport_b, "agent", session="s1")

            stop = threading.Event()

            def engine_loop():
                while not stop.is_set():
                    engine.poll_once()
                    stop.wait(0.001)

            t = threading.Thread(target=engine_loop, daemon=True)
            t.start()

            try:
                with self.assertRaises(RemoteError) as ctx:
                    agent.call("engine", "nonexistent", {}, timeout_ms=5000)
                self.assertEqual(ctx.exception.code, "METHOD_NOT_FOUND")
            finally:
                stop.set()
                t.join(timeout=1)
                transport_a.close()
                transport_b.close()

    def test_event(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            transport_a = PipeTransport(tmp_dir)
            transport_b = PipeTransport(tmp_dir)

            engine = Peer(transport_a, "engine", session="s1")
            agent = Peer(transport_b, "agent", session="s1")

            received = []
            engine.bind("on_ping", lambda p: received.append(p))

            stop = threading.Event()

            def engine_loop():
                while not stop.is_set():
                    engine.poll_once()
                    stop.wait(0.001)

            t = threading.Thread(target=engine_loop, daemon=True)
            t.start()

            try:
                agent.emit("engine", "on_ping", {"ts": "now"})
                time.sleep(0.2)
                self.assertEqual(len(received), 1)
            finally:
                stop.set()
                t.join(timeout=1)
                transport_a.close()
                transport_b.close()


class TestPipeConnect(unittest.TestCase):
    """Test connect() factory returns PipeTransport."""

    def test_connect_returns_pipe(self):
        from zep import connect
        with tempfile.TemporaryDirectory() as tmp_dir:
            transport = connect(tmp_dir)
            self.assertIsInstance(transport, PipeTransport)
            transport.close()

    def test_connect_roundtrip(self):
        from zep import connect
        with tempfile.TemporaryDirectory() as tmp_dir:
            ta = connect(tmp_dir)
            tb = connect(tmp_dir)

            engine = Peer(ta, "engine", session="s1")
            agent = Peer(tb, "agent", session="s1")

            engine.bind("echo", lambda p: p)

            stop = threading.Event()

            def engine_loop():
                while not stop.is_set():
                    engine.poll_once()
                    stop.wait(0.001)

            t = threading.Thread(target=engine_loop, daemon=True)
            t.start()

            try:
                result = agent.call("engine", "echo", {"msg": "hi"}, timeout_ms=5000)
                self.assertEqual(result, {"msg": "hi"})
            finally:
                stop.set()
                t.join(timeout=1)
                ta.close()
                tb.close()


if __name__ == "__main__":
    unittest.main()
