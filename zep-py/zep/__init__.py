"""ZEP — lightweight inter-program communication protocol."""

from .message import parse, validate, serialize, make_timestamp, ValidationError, SCHEMA
from .peer import Peer, CallTimeout, PeerNotFound, RemoteError
from .agent import BaseAgent, method, on_event
from .transport import FileTransport, connect
import sys
if sys.platform != "win32":
    from .transport import PipeTransport

__version__ = "0.3.1"
__all__ = [
    "parse", "validate", "serialize", "make_timestamp", "ValidationError", "SCHEMA",
    "Peer", "CallTimeout", "PeerNotFound", "RemoteError",
    "BaseAgent", "method", "on_event",
    "FileTransport", "connect",
]
