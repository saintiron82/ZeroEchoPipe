"""ZEP — lightweight inter-program communication protocol."""

from .message import parse, validate, serialize, make_timestamp, ValidationError, SCHEMA
from .peer import Peer, CallTimeout, PeerNotFound, RemoteError
from .agent import BaseAgent, method, on_event
from .transport import TcpTransport, FileTransport, connect

__version__ = "0.2.0"
__all__ = [
    "parse", "validate", "serialize", "make_timestamp", "ValidationError", "SCHEMA",
    "Peer", "CallTimeout", "PeerNotFound", "RemoteError",
    "BaseAgent", "method", "on_event",
    "FileTransport", "TcpTransport", "connect",
]
