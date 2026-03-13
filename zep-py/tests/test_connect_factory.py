"""ZEP connect() factory tests."""

import os
import sys
import tempfile
import threading
import time
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from zep import connect
from zep.peer import Peer, RemoteError
from zep.transport.tcp import TcpTransport


class TestConnectFactory(unittest.TestCase):
    """Test that connect() returns the right transport backend."""

    def test_int_returns_tcp(self):
        transport = connect(0, is_server=True)
        self.assertIsInstance(transport, TcpTransport)
        transport.close()

    def test_str_returns_native(self):
        if sys.platform == "win32":
            from zep.transport.winpipe import WinPipeTransport
            transport = connect("zep_test", is_server=True)
            self.assertIsInstance(transport, WinPipeTransport)
            transport.close()
        else:
            from zep.transport.uds import UdsTransport
            with tempfile.TemporaryDirectory() as tmp_dir:
                sock_path = os.path.join(tmp_dir, "zep.sock")
                transport = connect(sock_path, is_server=True)
                self.assertIsInstance(transport, UdsTransport)
                transport.close()

    def test_tcp_roundtrip_via_connect(self):
        """Full call-response via connect() factory."""
        server = connect(0, is_server=True)
        port = server.port
        time.sleep(0.05)

        client = connect(port, is_server=False)

        engine = Peer(server, "engine", session="s1")
        agent = Peer(client, "agent", session="s1")

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
            client.close()
            server.close()


if __name__ == "__main__":
    unittest.main()
