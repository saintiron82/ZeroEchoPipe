"""ZEP Socket Transport tests — Frame Profile over Unix Domain Socket."""

import os
import sys
import tempfile
import threading
import time
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from zep.peer import Peer, CallTimeout, RemoteError
from zep.transport.socket import SocketTransport, frame_encode, frame_decode


class TestFrameCodec(unittest.TestCase):
    """Test Frame Profile encode/decode."""

    def test_roundtrip(self):
        msg = '{"id":"m1","type":"call"}'
        encoded = frame_encode(msg)
        decoded, remaining = frame_decode(encoded)
        self.assertEqual(decoded, msg)
        self.assertEqual(remaining, b"")

    def test_strips_lf(self):
        msg = '{"id":"m1"}\n'
        encoded = frame_encode(msg)
        decoded, _ = frame_decode(encoded)
        self.assertEqual(decoded, '{"id":"m1"}')

    def test_incomplete_header(self):
        msg, remaining = frame_decode(b"\x00\x00")
        self.assertIsNone(msg)
        self.assertEqual(remaining, b"\x00\x00")

    def test_incomplete_payload(self):
        encoded = frame_encode("hello")
        msg, remaining = frame_decode(encoded[:6])  # header + 2 bytes only
        self.assertIsNone(msg)
        self.assertEqual(len(remaining), 6)

    def test_multiple_frames(self):
        data = frame_encode("first") + frame_encode("second")
        msg1, remaining = frame_decode(data)
        msg2, remaining = frame_decode(remaining)
        self.assertEqual(msg1, "first")
        self.assertEqual(msg2, "second")
        self.assertEqual(remaining, b"")


class TestSocketRoundtrip(unittest.TestCase):
    """Two peers communicate via SocketTransport."""

    def test_basic_call(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            sock_path = os.path.join(tmp_dir, "zep.sock")

            server = SocketTransport(sock_path, is_server=True)
            time.sleep(0.05)  # let server start

            client = SocketTransport(sock_path, is_server=False)

            engine = Peer(server, "engine", session="test_session")
            agent = Peer(client, "agent", session="test_session")

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
                client.close()
                server.close()

    def test_unknown_method(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            sock_path = os.path.join(tmp_dir, "zep.sock")

            server = SocketTransport(sock_path, is_server=True)
            time.sleep(0.05)

            client = SocketTransport(sock_path, is_server=False)

            engine = Peer(server, "engine", session="test_session")
            agent = Peer(client, "agent", session="test_session")

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
                client.close()
                server.close()

    def test_event(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            sock_path = os.path.join(tmp_dir, "zep.sock")

            server = SocketTransport(sock_path, is_server=True)
            time.sleep(0.05)

            client = SocketTransport(sock_path, is_server=False)

            engine = Peer(server, "engine", session="test_session")
            agent = Peer(client, "agent", session="test_session")

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
                client.close()
                server.close()


if __name__ == "__main__":
    unittest.main()
