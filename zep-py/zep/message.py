"""ZEP message parsing, validation, and serialization."""

import json
import re
from datetime import datetime, timezone

SCHEMA = "zep.v0.1"
VALID_TYPES = {"call", "response", "error", "event"}
PEER_NAME_RE = re.compile(r"^[a-z][a-z0-9_-]{0,63}$")
METHOD_NAME_RE = re.compile(r"^[a-z_][a-z0-9_.]{0,127}$")
TIMESTAMP_RE = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{3}Z$")

# Canonical key order per spec §7
_ENVELOPE_KEYS = ["id", "session", "from", "to", "type", "timestamp", "meta"]
_TYPE_KEYS = {
    "call": ["method", "params", "timeout_ms"],
    "response": ["reply_to", "result"],
    "error": ["reply_to", "error"],
    "event": ["method", "params"],
}
_ERROR_KEYS = ["code", "message", "retryable", "data"]
_META_KEYS_FIRST = ["schema"]


class ValidationError(Exception):
    def __init__(self, code, field, detail):
        self.code = code
        self.field = field
        self.detail = detail
        super().__init__(f"{code}: {field}: {detail}")


def validate(msg):
    """Validate a parsed dict against ZEP Core v0.1 spec.
    
    Returns the dict if valid.
    Raises ValidationError if invalid.
    """
    # Required envelope fields
    for f in ("id", "session", "from", "to", "type", "timestamp", "meta"):
        if f not in msg:
            raise ValidationError("MALFORMED_MESSAGE", f, f"required field {f} is missing")

    # Type
    if msg["type"] not in VALID_TYPES:
        raise ValidationError("MALFORMED_MESSAGE", "type",
                              "type must be one of: call, response, error, event")

    # Peer names
    for f in ("from", "to"):
        if not PEER_NAME_RE.match(msg[f]):
            raise ValidationError("MALFORMED_MESSAGE", f,
                                  f"peer name must match [a-z][a-z0-9_-]{{0,63}}")

    # Timestamp
    if not TIMESTAMP_RE.match(msg["timestamp"]):
        raise ValidationError("MALFORMED_MESSAGE", "timestamp",
                              "timestamp must match YYYY-MM-DDTHH:MM:SS.sssZ")

    # Meta
    if not isinstance(msg["meta"], dict):
        raise ValidationError("MALFORMED_MESSAGE", "meta", "meta must be an object")
    if "schema" not in msg["meta"]:
        raise ValidationError("MALFORMED_MESSAGE", "meta.schema",
                              "required field meta.schema is missing")

    # Type-specific validation
    t = msg["type"]
    if t in ("call", "event"):
        if "method" not in msg:
            raise ValidationError("MALFORMED_MESSAGE", "method",
                                  f"method is required when type is {t}")
        if not METHOD_NAME_RE.match(msg["method"]):
            raise ValidationError("MALFORMED_MESSAGE", "method",
                                  "method name must match [a-z_][a-z0-9_.]{0,127}")
        if "params" not in msg:
            raise ValidationError("MALFORMED_MESSAGE", "params",
                                  f"params is required when type is {t}")
        if not isinstance(msg["params"], dict):
            if isinstance(msg["params"], list):
                raise ValidationError("MALFORMED_MESSAGE", "params",
                                      "params must be a JSON object, not an array")
            raise ValidationError("MALFORMED_MESSAGE", "params",
                                  "params must be a JSON object")

    elif t == "response":
        if "reply_to" not in msg:
            raise ValidationError("MALFORMED_MESSAGE", "reply_to",
                                  "reply_to is required when type is response")
        if "result" not in msg:
            raise ValidationError("MALFORMED_MESSAGE", "result",
                                  "result is required when type is response")

    elif t == "error":
        if "reply_to" not in msg:
            raise ValidationError("MALFORMED_MESSAGE", "reply_to",
                                  "reply_to is required when type is error")
        if "error" not in msg:
            raise ValidationError("MALFORMED_MESSAGE", "error",
                                  "error is required when type is error")
        err = msg["error"]
        if not isinstance(err, dict):
            raise ValidationError("MALFORMED_MESSAGE", "error",
                                  "error must be an object")
        if "code" not in err:
            raise ValidationError("MALFORMED_MESSAGE", "error.code",
                                  "error.code is required when type is error")
        if "message" not in err:
            raise ValidationError("MALFORMED_MESSAGE", "error.message",
                                  "error.message is required when type is error")
        if "retryable" not in err:
            raise ValidationError("MALFORMED_MESSAGE", "error.retryable",
                                  "error.retryable is required when type is error")

    return msg


def parse(raw):
    """Parse raw JSON string into validated message dict.
    
    Returns dict with only spec-defined fields (unknown fields stripped).
    Raises ValidationError on invalid input.
    """
    if isinstance(raw, bytes):
        raw = raw.decode("utf-8")

    raw = raw.rstrip("\n")

    if "\r" in raw:
        raise ValidationError("MALFORMED_MESSAGE", "_raw", "message contains CR")

    try:
        msg = json.loads(raw)
    except json.JSONDecodeError as e:
        raise ValidationError("MALFORMED_MESSAGE", "_raw", f"invalid JSON: {e}")

    if not isinstance(msg, dict):
        raise ValidationError("MALFORMED_MESSAGE", "_raw", "message must be a JSON object")

    validate(msg)

    # Strip unknown top-level fields (permissive mode)
    return _extract_known_fields(msg)


def _extract_known_fields(msg):
    """Extract only spec-defined fields from a message dict."""
    t = msg.get("type", "call")
    known = set(_ENVELOPE_KEYS)
    known.update(k for k in _TYPE_KEYS.get(t, []))
    
    result = {}
    for k in list(_ENVELOPE_KEYS) + _TYPE_KEYS.get(t, []):
        if k in msg:
            result[k] = msg[k]
    return result


def serialize(msg, profile="jsonl"):
    """Serialize message dict to canonical wire format.
    
    profile: 'jsonl' (LF terminated) or 'frame' (length-prefixed bytes)
    Returns str for jsonl, bytes for frame.
    """
    ordered = _canonical_order(msg)
    compact = json.dumps(ordered, ensure_ascii=False, separators=(",", ":"))
    
    if profile == "jsonl":
        return compact + "\n"
    elif profile == "frame":
        data = compact.encode("utf-8")
        length = len(data).to_bytes(4, byteorder="big")
        return length + data
    else:
        raise ValueError(f"Unknown profile: {profile}")


def _canonical_order(msg):
    """Order message keys per spec §7 canonical key order."""
    result = {}
    t = msg.get("type", "call")

    # Envelope keys
    for k in _ENVELOPE_KEYS:
        if k in msg:
            if k == "meta":
                result[k] = _order_meta(msg[k])
            else:
                result[k] = msg[k]

    # Type-specific keys
    for k in _TYPE_KEYS.get(t, []):
        if k in msg:
            if k == "error" and isinstance(msg[k], dict):
                result[k] = _order_error(msg[k])
            else:
                result[k] = msg[k]

    return result


def _order_meta(meta):
    result = {}
    if "schema" in meta:
        result["schema"] = meta["schema"]
    for k in sorted(meta.keys()):
        if k != "schema":
            result[k] = meta[k]
    return result


def _order_error(err):
    result = {}
    for k in _ERROR_KEYS:
        if k in err:
            result[k] = err[k]
    return result


def make_timestamp():
    """Generate current UTC timestamp in spec format."""
    now = datetime.now(timezone.utc)
    return now.strftime("%Y-%m-%dT%H:%M:%S.") + f"{now.microsecond // 1000:03d}Z"
