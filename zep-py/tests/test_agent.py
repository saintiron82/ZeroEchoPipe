"""Tests for BaseAgent framework — decorator binding, agent-to-agent communication."""

import os
import sys
import tempfile
import time
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from zep.agent import BaseAgent, method, on_event
from zep.peer import RemoteError
from zep.transport.file import FileTransport


class EchoAgent(BaseAgent):
    """Simple agent that echoes params and tracks events."""

    def __init__(self, *args, **kwargs):
        self.received_events = []
        super().__init__(*args, **kwargs)

    @method("echo")
    def handle_echo(self, params):
        return params

    @method("add")
    def handle_add(self, params):
        return {"sum": params["a"] + params["b"]}

    @on_event("notify")
    def handle_notify(self, params):
        self.received_events.append(params)


class TestAgentBasic(unittest.TestCase):
    """Test BaseAgent decorator binding and method routing."""

    def _setup_agents(self):
        tmp_dir = tempfile.TemporaryDirectory()
        transport_a = FileTransport(tmp_dir.name)
        transport_b = FileTransport(tmp_dir.name)

        server = EchoAgent("server", transport_a, session="test")
        client = BaseAgent("client", transport_b, session="test")

        server.run(blocking=False)

        def cleanup():
            server.stop()
            transport_a.close()
            transport_b.close()
            tmp_dir.cleanup()

        self.addCleanup(cleanup)
        return server, client

    def test_echo(self):
        server, client = self._setup_agents()
        result = client.call("server", "echo", {"msg": "hello"}, timeout_ms=5000)
        self.assertEqual(result, {"msg": "hello"})

    def test_add(self):
        server, client = self._setup_agents()
        result = client.call("server", "add", {"a": 3, "b": 4}, timeout_ms=5000)
        self.assertEqual(result, {"sum": 7})

    def test_event(self):
        server, client = self._setup_agents()
        client.emit("server", "notify", {"level": "info", "msg": "test"})
        time.sleep(0.1)
        self.assertEqual(len(server.received_events), 1)
        self.assertEqual(server.received_events[0]["msg"], "test")

    def test_capabilities(self):
        server, client = self._setup_agents()
        caps = client.call("server", "_capabilities", {}, timeout_ms=5000)
        self.assertEqual(caps["name"], "server")
        self.assertEqual(caps["agent_type"], "EchoAgent")
        self.assertIn("echo", caps["methods"])
        self.assertIn("add", caps["methods"])

    def test_unknown_method(self):
        server, client = self._setup_agents()
        with self.assertRaises(RemoteError) as ctx:
            client.call("server", "nonexistent", {}, timeout_ms=5000)
        self.assertEqual(ctx.exception.code, "METHOD_NOT_FOUND")


class TestAgentToAgent(unittest.TestCase):
    """Two agents communicating with each other."""

    def test_bidirectional(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            transport_a = FileTransport(tmp_dir)
            transport_b = FileTransport(tmp_dir)

            class AgentA(BaseAgent):
                @method("greet")
                def handle_greet(self, params):
                    return {"reply": f"Hello, {params['name']}!"}

            class AgentB(BaseAgent):
                @method("status")
                def handle_status(self, params):
                    return {"online": True}

            a = AgentA("alice", transport_a, session="s1")
            b = AgentB("bob", transport_b, session="s1")

            a.run(blocking=False)
            b.run(blocking=False)

            try:
                # B calls A
                result = b.call("alice", "greet", {"name": "Bob"}, timeout_ms=5000)
                self.assertEqual(result, {"reply": "Hello, Bob!"})

                # A calls B
                result = a.call("bob", "status", {}, timeout_ms=5000)
                self.assertEqual(result, {"online": True})
            finally:
                a.stop()
                b.stop()


if __name__ == "__main__":
    unittest.main()
