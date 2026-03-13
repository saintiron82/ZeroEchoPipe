"""ZEP Agent — decorator-based agent framework on top of Peer.

Usage:
    class MyAgent(BaseAgent):
        @method("get_status")
        def handle_status(self, params):
            return {"health": 100}

        @on_event("log")
        def handle_log(self, params):
            print(params["message"])

    agent = MyAgent("myagent", transport)
    agent.run()  # blocking
"""

import logging
import time
import threading
from .peer import Peer

logger = logging.getLogger("zep.agent")

# Decorators for method registration
_METHOD_ATTR = "_zep_method"
_EVENT_ATTR = "_zep_event"


def method(name):
    """Decorator to register a call handler method."""
    def decorator(func):
        setattr(func, _METHOD_ATTR, name)
        return func
    return decorator


def on_event(name):
    """Decorator to register an event handler method."""
    def decorator(func):
        setattr(func, _EVENT_ATTR, name)
        return func
    return decorator


class BaseAgent:
    """Base class for ZEP agents with decorator-based method routing.

    Subclass and use @method / @on_event decorators to register handlers.
    """

    def __init__(self, name, transport, session=None, capabilities=None):
        caps = capabilities or {}
        caps.setdefault("agent_type", self.__class__.__name__)
        self.peer = Peer(transport, name, session=session, capabilities=caps)
        self.name = name
        self._poll_interval = 0.001  # 1ms
        self._running = False
        self._thread = None

        self._auto_bind()

    def _auto_bind(self):
        """Scan class for @method and @on_event decorated methods."""
        for attr_name in dir(self):
            if attr_name.startswith("__"):
                continue
            attr = getattr(self, attr_name, None)
            if attr is None:
                continue

            zep_method = getattr(attr, _METHOD_ATTR, None)
            if zep_method:
                self.peer.bind(zep_method, attr)
                logger.debug("Bound method %s -> %s", zep_method, attr_name)

            zep_event = getattr(attr, _EVENT_ATTR, None)
            if zep_event:
                self.peer.bind_event(zep_event, attr)
                logger.debug("Bound event %s -> %s", zep_event, attr_name)

    def call(self, peer, method_name, params, timeout_ms=10000):
        """Call a remote peer method."""
        return self.peer.call(peer, method_name, params, timeout_ms=timeout_ms)

    def emit(self, peer, method_name, params):
        """Emit an event to a remote peer."""
        self.peer.emit(peer, method_name, params)

    def run(self, blocking=True):
        """Start the agent polling loop.

        If blocking=True, runs in current thread (blocks).
        If blocking=False, runs in background thread.
        """
        self._running = True
        logger.info("Agent %s starting (blocking=%s)", self.name, blocking)

        if blocking:
            self._poll_loop()
        else:
            self._thread = threading.Thread(target=self._poll_loop, daemon=True)
            self._thread.start()
            return self

    def stop(self):
        """Stop the agent."""
        logger.info("Agent %s stopping", self.name)
        self._running = False
        self.peer.shutdown()
        if self._thread:
            self._thread.join(timeout=2)

    def _poll_loop(self):
        while self._running and not self.peer.is_shutdown:
            self.peer.poll_once()
            time.sleep(self._poll_interval)

    def on_start(self):
        """Override for startup logic."""
        pass

    def on_stop(self):
        """Override for cleanup logic."""
        pass
