"""ZEP protocol conformance test suite.

Loads test cases from the shared conformance manifest and validates
parse, parse-invalid, and serialize behaviour against expected outputs.
"""

import json
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from zep.message import ValidationError, parse, serialize

CONFORMANCE_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "conformance")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _load_json(path: str):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def _load_raw(path: str) -> str:
    with open(path, encoding="utf-8") as f:
        return f.read()


# ---------------------------------------------------------------------------
# Manifest (loaded once at module level)
# ---------------------------------------------------------------------------

_MANIFEST = _load_json(os.path.join(CONFORMANCE_DIR, "manifest.json"))


# ---------------------------------------------------------------------------
# Test cases
# ---------------------------------------------------------------------------

class TestParseValid(unittest.TestCase):
    """Input messages that must parse successfully."""

    def test_parse_valid_cases(self):
        for case in _MANIFEST["suites"]["parse_valid"]:
            case_name = case.rsplit("/", 1)[-1]
            with self.subTest(case=case_name):
                raw = _load_raw(
                    os.path.join(CONFORMANCE_DIR, f"{case}.input.json")
                ).rstrip("\n")
                expected_parsed = _load_json(
                    os.path.join(CONFORMANCE_DIR, f"{case}.expected.json")
                )["parsed"]
                result = parse(raw)
                self.assertEqual(result, expected_parsed)


class TestParseInvalid(unittest.TestCase):
    """Input messages that must be rejected with the correct error."""

    def test_parse_invalid_cases(self):
        for case in _MANIFEST["suites"]["parse_invalid"]:
            case_name = case.rsplit("/", 1)[-1]
            with self.subTest(case=case_name):
                raw = _load_raw(
                    os.path.join(CONFORMANCE_DIR, f"{case}.input.json")
                ).rstrip("\n")
                expected = _load_json(
                    os.path.join(CONFORMANCE_DIR, f"{case}.expected.json")
                )
                with self.assertRaises(ValidationError) as ctx:
                    parse(raw)
                self.assertEqual(ctx.exception.code, expected["error_code"])
                self.assertEqual(ctx.exception.field, expected["error_field"])


class TestSerialize(unittest.TestCase):
    """Field dicts that must serialize to byte-exact JSONL strings."""

    def test_serialize_cases(self):
        for case in _MANIFEST["suites"]["serialize"]:
            case_name = case.rsplit("/", 1)[-1]
            with self.subTest(case=case_name):
                fields = _load_json(
                    os.path.join(CONFORMANCE_DIR, f"{case}.fields.json")
                )
                expected_raw = _load_raw(
                    os.path.join(CONFORMANCE_DIR, f"{case}.expected.jsonl")
                )
                result = serialize(fields, profile="jsonl")
                self.assertEqual(result, expected_raw)


if __name__ == "__main__":
    unittest.main()
