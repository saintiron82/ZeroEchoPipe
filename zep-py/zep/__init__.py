"""ZEP — lightweight inter-program communication protocol."""

from .message import parse, validate, serialize, make_timestamp, ValidationError, SCHEMA
from .peer import Peer, CallTimeout, PeerNotFound, RemoteError
from .agent import BaseAgent, method, on_event
from .transport.file import FileTransport
from .transport.socket import SocketTransport

__version__ = "0.1.0"
__all__ = [
    "parse", "validate", "serialize", "make_timestamp", "ValidationError", "SCHEMA",
    "Peer", "CallTimeout", "PeerNotFound", "RemoteError",
    "BaseAgent", "method", "on_event",
    "FileTransport", "SocketTransport",
]
