"""ZEP Peer — bind methods, call peers, emit events, poll inbox.

Supports reserved protocol methods (_capabilities, _ping, _shutdown)
and routing symmetry verification per spec sections 3.3 and 3.4.
"""

import logging
import uuid
import time
import threading
from . import message as msg

logger = logging.getLogger("zep.peer")


class CallTimeout(Exception):
    pass


class PeerNotFound(Exception):
    pass


class RemoteError(Exception):
    def __init__(self, code, detail, retryable=False):
        self.code = code
        self.detail = detail
        self.retryable = retryable
        super().__init__(f"{code}: {detail}")


class Peer:
    def __init__(self, transport, name, session=None, capabilities=None):
        self.transport = transport
        self.name = name
        self.session = session or f"sess_{uuid.uuid4().hex[:12]}"
        self._handlers = {}
        self._event_handlers = {}
        self._pending = {}     # id -> (threading.Event, holder, call_info)
        self._pending_lock = threading.Lock()
        self._shutdown_event = threading.Event()
        self._capabilities = capabilities or {}
        self._on_shutdown = None

        # Register reserved protocol methods
        self._register_reserved_methods()

    def _register_reserved_methods(self):
        self._reserved = {
            "_capabilities": self._handle_capabilities,
            "_ping": self._handle_ping,
            "_shutdown": self._handle_shutdown,
        }

    def _handle_capabilities(self, params):
        return {
            "name": self.name,
            "schema": msg.SCHEMA,
            "methods": list(self._handlers.keys()),
            **self._capabilities,
        }

    def _handle_ping(self, params):
        return {"pong": True, "timestamp": msg.make_timestamp()}

    def _handle_shutdown(self, params):
        logger.info("Received _shutdown request from peer")
        self._shutdown_event.set()
        if self._on_shutdown:
            self._on_shutdown()
        return {"acknowledged": True}

    def on_shutdown(self, callback):
        """Register a callback to be called on _shutdown."""
        self._on_shutdown = callback
        return self

    @property
    def is_shutdown(self):
        return self._shutdown_event.is_set()

    def bind(self, method, handler):
        """Register a method handler. handler(params) -> result."""
        if method.startswith("_"):
            raise ValueError(f"Methods starting with '_' are protocol-reserved: {method}")
        self._handlers[method] = handler
        return self

    def bind_event(self, method, handler):
        """Register an event handler. handler(params) -> None."""
        self._event_handlers[method] = handler
        return self

    def unbind(self, method):
        """Remove a method handler."""
        self._handlers.pop(method, None)
        self._event_handlers.pop(method, None)

    def call(self, peer, method, params, timeout_ms=10000):
        """Send call and wait for response. Returns result or raises."""
        call_id = self._gen_id()
        call_msg = {
            "id": call_id,
            "session": self.session,
            "from": self.name,
            "to": peer,
            "type": "call",
            "timestamp": msg.make_timestamp(),
            "meta": {"schema": msg.SCHEMA},
            "method": method,
            "params": params,
        }
        if timeout_ms:
            call_msg["timeout_ms"] = timeout_ms

        # Track call info for routing symmetry check
        call_info = {"to": peer, "from": self.name, "session": self.session}

        event = threading.Event()
        holder = {"result": None, "error": None}
        with self._pending_lock:
            self._pending[call_id] = (event, holder, call_info)

        data = msg.serialize(call_msg)
        self.transport.send(peer, self.name, data)
        logger.debug("Sent call %s.%s to %s (id=%s)", self.name, method, peer, call_id)

        deadline = timeout_ms / 1000.0 if timeout_ms else 30.0
        start = time.monotonic()

        while not event.is_set():
            if self._shutdown_event.is_set():
                with self._pending_lock:
                    self._pending.pop(call_id, None)
                raise CallTimeout(f"Peer shutting down, call {method} aborted")
            elapsed = time.monotonic() - start
            if elapsed >= deadline:
                with self._pending_lock:
                    self._pending.pop(call_id, None)
                raise CallTimeout(f"No response within {timeout_ms}ms for {method}")
            self.poll_once()
            if not event.is_set():
                time.sleep(0.001)

        with self._pending_lock:
            self._pending.pop(call_id, None)

        if holder["error"]:
            e = holder["error"]
            raise RemoteError(e["code"], e["message"], e.get("retryable", False))
        return holder["result"]

    def emit(self, peer, method, params):
        """Send event (no response expected)."""
        event_msg = {
            "id": self._gen_id(),
            "session": self.session,
            "from": self.name,
            "to": peer,
            "type": "event",
            "timestamp": msg.make_timestamp(),
            "meta": {"schema": msg.SCHEMA},
            "method": method,
            "params": params,
        }
        data = msg.serialize(event_msg)
        self.transport.send(peer, self.name, data)

    def poll_once(self):
        """Read inbox, dispatch handlers, match responses."""
        raw_messages = self.transport.recv(self.name)

        for raw in raw_messages:
            try:
                parsed = msg.parse(raw)
            except msg.ValidationError as e:
                logger.debug("Discarded malformed message: %s", e)
                continue

            self._dispatch(parsed)

    def shutdown(self):
        """Graceful shutdown — signal shutdown and close transport."""
        logger.info("Peer %s shutting down", self.name)
        self._shutdown_event.set()
        self.transport.close()

    def _dispatch(self, parsed):
        t = parsed["type"]

        if t == "call":
            self._handle_call(parsed)
        elif t in ("response", "error"):
            self._handle_reply(parsed)
        elif t == "event":
            self._handle_event(parsed)

    def _handle_call(self, parsed):
        method = parsed["method"]

        # Check reserved methods first
        reserved_handler = self._reserved.get(method)
        if reserved_handler:
            try:
                result = reserved_handler(parsed["params"])
                self._send_response(parsed, result)
            except Exception as e:
                logger.error("Reserved method %s failed: %s", method, e)
                self._send_error(parsed, "INTERNAL_ERROR", str(e), retryable=True)
            return

        handler = self._handlers.get(method)

        if handler is None:
            self._send_error(parsed, "METHOD_NOT_FOUND",
                             f"Unknown method: {method}", retryable=False)
            return

        try:
            result = handler(parsed["params"])
            self._send_response(parsed, result)
        except Exception as e:
            logger.error("Handler %s raised: %s", method, e)
            self._send_error(parsed, "INTERNAL_ERROR",
                             str(e), retryable=True)

    def _handle_reply(self, parsed):
        reply_to = parsed.get("reply_to")
        if not reply_to:
            return

        with self._pending_lock:
            pending = self._pending.get(reply_to)

        if not pending:
            logger.debug("Ignoring reply to unknown call: %s", reply_to)
            return

        event, holder, call_info = pending

        # Routing symmetry check per spec §3.3 and §3.4
        if not self._verify_routing(parsed, call_info):
            logger.debug("Ignoring reply with routing mismatch: %s", reply_to)
            return

        if parsed["type"] == "response":
            holder["result"] = parsed.get("result")
        elif parsed["type"] == "error":
            holder["error"] = parsed.get("error", {})

        event.set()

    def _verify_routing(self, reply, call_info):
        """Verify routing symmetry per spec §3.3.

        response/error must have: to=call.from, from=call.to, session=call.session.
        On mismatch: ignore per §3.4.
        """
        if reply.get("from") != call_info["to"]:
            return False
        if reply.get("to") != call_info["from"]:
            return False
        if reply.get("session") != call_info["session"]:
            return False
        return True

    def _handle_event(self, parsed):
        method = parsed.get("method", "")

        # Check dedicated event handlers first, then regular handlers
        handler = self._event_handlers.get(method) or self._handlers.get(method)
        if handler:
            try:
                handler(parsed["params"])
            except Exception as e:
                logger.debug("Event handler %s raised: %s", method, e)

    def _send_response(self, original, result):
        resp = {
            "id": self._gen_id(),
            "session": original["session"],
            "from": self.name,
            "to": original["from"],
            "type": "response",
            "timestamp": msg.make_timestamp(),
            "meta": {"schema": msg.SCHEMA},
            "reply_to": original["id"],
            "result": result,
        }
        data = msg.serialize(resp)
        self.transport.send(original["from"], self.name, data)

    def _send_error(self, original, code, message, retryable=False):
        err = {
            "id": self._gen_id(),
            "session": original["session"],
            "from": self.name,
            "to": original["from"],
            "type": "error",
            "timestamp": msg.make_timestamp(),
            "meta": {"schema": msg.SCHEMA},
            "reply_to": original["id"],
            "error": {"code": code, "message": message, "retryable": retryable},
        }
        data = msg.serialize(err)
        self.transport.send(original["from"], self.name, data)

    def _gen_id(self):
        return f"msg_{uuid.uuid4().hex[:16]}"
