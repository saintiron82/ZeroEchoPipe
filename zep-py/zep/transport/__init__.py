"""ZEP transport backends.

PipeTransport is the primary transport — Named Pipe (FIFO), no server,
no client, no ports. Just a path.

FileTransport is the cross-platform fallback (disk-based).
TcpTransport/UdsTransport are available for special cases.
"""

import sys
from .base import BaseTransport
from .file import FileTransport
from .tcp import TcpTransport, frame_encode, frame_decode

__all__ = [
    "BaseTransport", "FileTransport", "TcpTransport",
    "frame_encode", "frame_decode",
    "connect",
]

if sys.platform != "win32":
    from .pipe import PipeTransport
    __all__.append("PipeTransport")

if sys.platform == "win32":
    # Windows: FileTransport as default (Named Pipe via ctypes planned)
    pass
else:
    from .uds import UdsTransport
    __all__.append("UdsTransport")


def connect(base_dir):
    """Create the best available transport for the current platform.

    Args:
        base_dir: Directory path for pipe/file communication.
            All peers sharing this path can communicate.

    Returns:
        A BaseTransport instance. No server, no client, no ports.
    """
    if sys.platform == "win32":
        return FileTransport(base_dir)
    else:
        return PipeTransport(base_dir)
