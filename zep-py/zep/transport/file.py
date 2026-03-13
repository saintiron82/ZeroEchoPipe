"""ZEP file transport — sender-split inbox, JSONL profile."""

import os
import fcntl
from pathlib import Path
from .base import BaseTransport


class FileTransport(BaseTransport):
    def __init__(self, base_dir):
        self.base_dir = Path(base_dir)
        self._cursors = {}  # (peer, sender) -> byte offset

    def send(self, to_peer, from_peer, data):
        """Append serialized JSONL message to target peer's inbox file."""
        peer_dir = self.base_dir / "peers" / to_peer
        peer_dir.mkdir(parents=True, exist_ok=True)
        inbox_file = peer_dir / f"from_{from_peer}.jsonl"

        if isinstance(data, str):
            data = data.encode("utf-8")

        with open(inbox_file, "ab") as f:
            fcntl.flock(f, fcntl.LOCK_EX)
            f.write(data)
            f.flush()
            os.fsync(f.fileno())
            fcntl.flock(f, fcntl.LOCK_UN)

    def recv(self, peer_name, limit=100):
        """Read new messages from all inbox files for peer."""
        peer_dir = self.base_dir / "peers" / peer_name
        if not peer_dir.exists():
            return []

        messages = []
        for inbox_file in sorted(peer_dir.glob("from_*.jsonl")):
            sender = inbox_file.stem[5:]  # strip "from_"
            key = (peer_name, sender)
            cursor = self._cursors.get(key, 0)

            try:
                with open(inbox_file, "rb") as f:
                    f.seek(cursor)
                    remaining = f.read()
                    if not remaining:
                        continue

                    new_cursor = cursor + len(remaining)
                    lines = remaining.decode("utf-8").split("\n")

                    for line in lines:
                        line = line.strip()
                        if line:
                            messages.append(line)
                            if len(messages) >= limit:
                                break

                    self._cursors[key] = new_cursor

            except FileNotFoundError:
                continue

            if len(messages) >= limit:
                break

        return messages

    def peer_exists(self, peer_name):
        """Check if peer inbox directory exists."""
        return (self.base_dir / "peers" / peer_name).is_dir()

    def close(self):
        self._cursors.clear()
