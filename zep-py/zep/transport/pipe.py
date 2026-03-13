"""ZEP Pipe transport — Named Pipe (FIFO) with Frame Profile.

Each peer has an inbox directory with one pipe per sender.
Path: <base_dir>/peers/<peer>/from_<sender>.pipe

Data stays in kernel memory (no disk I/O).
No server, no client, no ports — just a path.

Unix/macOS: mkfifo
Windows: falls back to file-based (see file.py)
"""

import os
import sys
import stat
from pathlib import Path
from .base import BaseTransport
from .tcp import frame_encode, frame_decode


class PipeTransport(BaseTransport):
    """Named Pipe transport using Frame Profile.

    Symmetric — every peer is equal. No server, no client.
    Each peer reads from its own inbox pipes, writes to others'.

    Usage:
        transport = PipeTransport("/tmp/zep-bus")
    """

    def __init__(self, base_dir):
        self.base_dir = Path(base_dir)
        self._write_fds = {}     # (to_peer, from_peer) -> fd
        self._read_fds = {}      # (peer_name, sender) -> fd
        self._read_buffers = {}  # (peer_name, sender) -> bytes

    def _pipe_path(self, peer, sender):
        return self.base_dir / "peers" / peer / f"from_{sender}.pipe"

    def _ensure_pipe(self, path):
        """Create FIFO if it doesn't exist."""
        path.parent.mkdir(parents=True, exist_ok=True)
        if not path.exists():
            os.mkfifo(str(path))
        elif not stat.S_ISFIFO(os.stat(str(path)).st_mode):
            os.unlink(str(path))
            os.mkfifo(str(path))

    def send(self, to_peer, from_peer, data):
        """Write framed message to target peer's inbox pipe."""
        key = (to_peer, from_peer)

        if key not in self._write_fds:
            path = self._pipe_path(to_peer, from_peer)
            self._ensure_pipe(path)
            # O_RDWR avoids blocking when no reader yet
            fd = os.open(str(path), os.O_RDWR | os.O_NONBLOCK)
            self._write_fds[key] = fd

        if isinstance(data, str):
            data = data.rstrip("\n")

        frame = frame_encode(data)
        fd = self._write_fds[key]
        # Handle partial writes
        written = 0
        while written < len(frame):
            n = os.write(fd, frame[written:])
            written += n

    def recv(self, peer_name, limit=100):
        """Read framed messages from all inbox pipes for peer."""
        peer_dir = self.base_dir / "peers" / peer_name
        if not peer_dir.exists():
            return []

        # Discover new pipes
        for pipe_file in sorted(peer_dir.glob("from_*.pipe")):
            sender = pipe_file.stem[5:]  # strip "from_"
            key = (peer_name, sender)
            if key not in self._read_fds:
                try:
                    fd = os.open(str(pipe_file), os.O_RDWR | os.O_NONBLOCK)
                    self._read_fds[key] = fd
                    self._read_buffers[key] = b""
                except OSError:
                    continue

        messages = []
        for key, fd in list(self._read_fds.items()):
            try:
                chunk = os.read(fd, 65536)
                if chunk:
                    self._read_buffers[key] += chunk
            except (BlockingIOError, OSError):
                pass

            while True:
                msg, self._read_buffers[key] = frame_decode(
                    self._read_buffers[key]
                )
                if msg is None:
                    break
                messages.append(msg)
                if len(messages) >= limit:
                    return messages

        return messages

    def close(self):
        """Close all pipe file descriptors."""
        for fd in self._write_fds.values():
            try:
                os.close(fd)
            except OSError:
                pass
        for fd in self._read_fds.values():
            try:
                os.close(fd)
            except OSError:
                pass
        self._write_fds.clear()
        self._read_fds.clear()
        self._read_buffers.clear()
