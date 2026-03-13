"""Scenario-based conformance test runner for ZEP.

Interprets scenario JSON files that define step-by-step message exchanges
between peers, verifying state transitions per spec section 3.
"""

import glob
import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from zep.message import serialize, parse
from zep.transport.file import FileTransport

SCENARIO_DIR = os.path.join(
    os.path.dirname(__file__), "..", "..", "conformance", "scenarios"
)


class TestScenario(unittest.TestCase):

    def test_scenarios(self):
        pattern = os.path.join(SCENARIO_DIR, "*.scenario.json")
        scenario_files = sorted(glob.glob(pattern))
        self.assertTrue(scenario_files, f"No scenario files found in {SCENARIO_DIR}")

        for path in scenario_files:
            name = os.path.basename(path)
            with self.subTest(scenario=name):
                with open(path, "r") as f:
                    scenario = json.load(f)
                self._run_scenario(scenario)

    def _run_scenario(self, scenario):
        pending_calls = {}   # msg_id -> "pending" | "completed" | "failed" | "timeout"
        call_sessions = {}   # msg_id -> session (for symmetry check)

        with tempfile.TemporaryDirectory() as base_dir:
            transport = FileTransport(base_dir)

            for step in scenario["steps"]:
                if "action" in step:
                    self._exec_action(step, transport, pending_calls, call_sessions)
                elif "assert_state" in step:
                    self._exec_assert(step, pending_calls)

            transport.close()

    def _exec_action(self, step, transport, pending_calls, call_sessions):
        action = step["action"]

        if action == "send":
            message = step["message"]
            serialized = serialize(message, profile="jsonl")
            transport.send(
                to_peer=message["to"],
                from_peer=message["from"],
                data=serialized,
            )
            if message["type"] == "call":
                pending_calls[message["id"]] = "pending"
                call_sessions[message["id"]] = message["session"]

        elif action == "receive":
            raw_messages = transport.recv(step["actor"])
            expected_id = step["expect_message_id"]
            parsed_msg = None

            for raw in raw_messages:
                candidate = parse(raw)
                if candidate["id"] == expected_id:
                    parsed_msg = candidate
                    break

            self.assertIsNotNone(
                parsed_msg,
                f"Expected message {expected_id} not found "
                f"for actor {step['actor']}",
            )

            if (
                parsed_msg["type"] in ("response", "error")
                and "reply_to" in parsed_msg
            ):
                reply_to = parsed_msg["reply_to"]
                if reply_to in pending_calls:
                    original_session = call_sessions.get(reply_to)
                    if original_session and parsed_msg["session"] != original_session:
                        pass  # session mismatch: ignore per spec 3.4
                    elif parsed_msg["type"] == "response":
                        pending_calls[reply_to] = "completed"
                    elif parsed_msg["type"] == "error":
                        pending_calls[reply_to] = "failed"

    def _exec_assert(self, step, pending_calls):
        expected = step["assert_state"].get("pending_calls", {})
        for msg_id, expected_status in expected.items():
            if expected_status == "timeout":
                actual = pending_calls.get(msg_id)
                if actual == "pending":
                    pending_calls[msg_id] = "timeout"
                self.assertEqual(
                    pending_calls.get(msg_id),
                    "timeout",
                    f"pending_calls[{msg_id}]: expected timeout, "
                    f"got {pending_calls.get(msg_id)}",
                )
            else:
                self.assertEqual(
                    pending_calls.get(msg_id),
                    expected_status,
                    f"pending_calls[{msg_id}]: expected {expected_status}, "
                    f"got {pending_calls.get(msg_id)}",
                )


if __name__ == "__main__":
    unittest.main()
