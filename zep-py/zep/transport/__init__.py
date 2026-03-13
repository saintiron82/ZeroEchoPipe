"""ZEP transport backends.

All backends share the same BaseTransport interface (send, recv, close)
and use the same Frame Profile wire format.
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

# Platform-specific imports
if sys.platform == "win32":
    from .winpipe import WinPipeTransport
    __all__.append("WinPipeTransport")
else:
    from .uds import UdsTransport
    __all__.append("UdsTransport")


def connect(address, is_server=False):
    """Create the best available transport for the current platform.

    Args:
        address: Transport-specific address.
            - int: TCP port (0 = auto-assign)
            - str ending with '.sock': Unix Domain Socket path (Unix/macOS)
            - str: Named Pipe name (Windows)
        is_server: Whether this side acts as server.

    Returns:
        A BaseTransport instance.
    """
    if isinstance(address, int):
        return TcpTransport(address, is_server=is_server)

    if sys.platform == "win32":
        return WinPipeTransport(address, is_server=is_server)
    else:
        return UdsTransport(address, is_server=is_server)
