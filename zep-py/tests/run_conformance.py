"""ZEP Conformance Test Runner — validates Python SDK against test suite."""

import json
import sys
import os

# Add parent to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from zep.message import parse, validate, serialize, ValidationError

CONFORMANCE_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "conformance")

passed = 0
failed = 0
errors = []


def load_json(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def load_raw(path):
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


def test_parse_valid(case_path):
    global passed, failed
    input_file = case_path + ".input.json"
    expected_file = case_path + ".expected.json"

    raw = load_raw(input_file).strip()
    expected = load_json(expected_file)

    try:
        result = parse(raw)
        # Compare parsed fields
        expected_parsed = expected["parsed"]
        if result == expected_parsed:
            passed += 1
        else:
            failed += 1
            errors.append(f"PARSE_VALID MISMATCH: {os.path.basename(case_path)}\n"
                         f"  expected: {json.dumps(expected_parsed, ensure_ascii=False)}\n"
                         f"  got:      {json.dumps(result, ensure_ascii=False)}")
    except ValidationError as e:
        failed += 1
        errors.append(f"PARSE_VALID REJECTED: {os.path.basename(case_path)} — {e}")


def test_parse_invalid(case_path):
    global passed, failed
    input_file = case_path + ".input.json"
    expected_file = case_path + ".expected.json"

    raw = load_raw(input_file).strip()
    expected = load_json(expected_file)

    try:
        parse(raw)
        failed += 1
        errors.append(f"PARSE_INVALID ACCEPTED: {os.path.basename(case_path)} — should have been rejected")
    except ValidationError as e:
        # Check error_code and error_field match
        exp_code = expected.get("error_code", "")
        exp_field = expected.get("error_field", "")

        code_ok = (e.code == exp_code)
        field_ok = (e.field == exp_field)

        if code_ok and field_ok:
            passed += 1
        else:
            failed += 1
            detail = []
            if not code_ok:
                detail.append(f"code: expected={exp_code}, got={e.code}")
            if not field_ok:
                detail.append(f"field: expected={exp_field}, got={e.field}")
            errors.append(f"PARSE_INVALID MISMATCH: {os.path.basename(case_path)} — {', '.join(detail)}")


def test_serialize(case_path):
    global passed, failed
    fields_file = case_path + ".fields.json"
    expected_file = case_path + ".expected.jsonl"

    fields = load_json(fields_file)
    expected_raw = load_raw(expected_file)

    result = serialize(fields, profile="jsonl")

    if result == expected_raw:
        passed += 1
    else:
        failed += 1
        errors.append(f"SERIALIZE MISMATCH: {os.path.basename(case_path)}\n"
                     f"  expected: {expected_raw.rstrip()}\n"
                     f"  got:      {result.rstrip()}")


def main():
    global passed, failed

    manifest_path = os.path.join(CONFORMANCE_DIR, "manifest.json")
    if not os.path.exists(manifest_path):
        print(f"ERROR: manifest not found at {manifest_path}")
        sys.exit(1)

    manifest = load_json(manifest_path)
    suites = manifest["suites"]

    print(f"ZEP Conformance Runner — schema {manifest['version']}")
    print("=" * 60)

    # Parse valid
    print("\n[parse/valid]")
    for case in suites.get("parse_valid", []):
        case_path = os.path.join(CONFORMANCE_DIR, case)
        name = os.path.basename(case)
        try:
            test_parse_valid(case_path)
            if not errors or not errors[-1].startswith(f"PARSE_VALID"):
                print(f"  ✓ {name}")
            else:
                print(f"  ✗ {name}")
        except Exception as e:
            failed += 1
            errors.append(f"PARSE_VALID CRASH: {name} — {e}")
            print(f"  ✗ {name} (CRASH)")

    # Parse invalid
    print("\n[parse/invalid]")
    for case in suites.get("parse_invalid", []):
        case_path = os.path.join(CONFORMANCE_DIR, case)
        name = os.path.basename(case)
        try:
            test_parse_invalid(case_path)
            if not errors or not errors[-1].startswith(f"PARSE_INVALID"):
                print(f"  ✓ {name}")
            else:
                print(f"  ✗ {name}")
        except Exception as e:
            failed += 1
            errors.append(f"PARSE_INVALID CRASH: {name} — {e}")
            print(f"  ✗ {name} (CRASH)")

    # Serialize
    print("\n[serialize]")
    for case in suites.get("serialize", []):
        case_path = os.path.join(CONFORMANCE_DIR, case)
        name = os.path.basename(case)
        try:
            test_serialize(case_path)
            if not errors or not errors[-1].startswith(f"SERIALIZE"):
                print(f"  ✓ {name}")
            else:
                print(f"  ✗ {name}")
        except Exception as e:
            failed += 1
            errors.append(f"SERIALIZE CRASH: {name} — {e}")
            print(f"  ✗ {name} (CRASH)")

    # Summary
    total = passed + failed
    print("\n" + "=" * 60)
    print(f"Total: {total}  Passed: {passed}  Failed: {failed}")

    if errors:
        print("\n--- Failures ---")
        for e in errors:
            print(f"\n{e}")

    sys.exit(0 if failed == 0 else 1)


if __name__ == "__main__":
    main()
