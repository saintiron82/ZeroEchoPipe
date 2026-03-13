"""ZEP Windows Named Pipe transport with Frame Profile.

Frame Profile: 4-byte big-endian length prefix + JSON payload.
Windows only. Native performance via Named Pipes.
"""

import json
import sys
import threading
from .base import BaseTransport
from .tcp import frame_encode, frame_decode

if sys.platform == "win32":
    import win32pipe
    import win32file
    import pywintypes


class WinPipeTransport(BaseTransport):
    r"""Windows Named Pipe transport using Frame Profile.

    One peer acts as server (creates pipe), others connect as clients.
    Messages are routed by 'to' field in the envelope.
    Pipe name format: \\.\pipe\zep_<name>
    Windows only.
    """

    def __init__(self, pipe_name, is_server=False):
        if sys.platform != "win32":
            raise OSError("WinPipeTransport is only available on Windows")
        self._pipe_name = f"\\\\.\\pipe\\{pipe_name}"
        self._is_server = is_server
        self._connections = {}       # peer_name -> pipe handle
        self._buffers = {}           # buf_key -> bytes
        self._inbox = {}             # peer_name -> [message_str, ...]
        self._lock = threading.Lock()
        self._running = False
        self._accept_thread = None
        self._server_pipe = None

        if is_server:
            self._start_server()

    def _start_server(self):
        self._running = True
        self._accept_thread = threading.Thread(target=self._accept_loop, daemon=True)
        self._accept_thread.start()

    def _accept_loop(self):
        while self._running:
            try:
                pipe = win32pipe.CreateNamedPipe(
                    self._pipe_name,
                    win32pipe.PIPE_ACCESS_DUPLEX,
                    (win32pipe.PIPE_TYPE_BYTE
                     | win32pipe.PIPE_READMODE_BYTE
                     | win32pipe.PIPE_WAIT),
                    win32pipe.PIPE_UNLIMITED_INSTANCES,
                    65536, 65536, 0, None,
                )
                win32pipe.ConnectNamedPipe(pipe, None)
                reader = threading.Thread(
                    target=self._read_from, args=(pipe,), daemon=True,
                )
                reader.start()
            except pywintypes.error:
                if not self._running:
                    break

    def _read_from(self, pipe):
        buf = b""
        while self._running:
            try:
                hr, data = win32file.ReadFile(pipe, 65536)
                if not data:
                    break
                buf += data
                with self._lock:
                    while True:
                        msg, buf = frame_decode(buf)
                        if msg is None:
                            break
                        try:
                            envelope = json.loads(msg)
                            to_peer = envelope.get("to", "")
                            from_peer = envelope.get("from", "")
                            if from_peer and from_peer not in self._connections:
                                self._connections[from_peer] = pipe
                            self._inbox.setdefault(to_peer, []).append(msg)
                        except json.JSONDecodeError:
                            pass
            except pywintypes.error:
                break
        try:
            win32file.CloseHandle(pipe)
        except pywintypes.error:
            pass

    def _ensure_connected(self):
        if self._is_server:
            return
        if not hasattr(self, "_client_pipe") or self._client_pipe is None:
            self._client_pipe = win32file.CreateFile(
                self._pipe_name,
                win32file.GENERIC_READ | win32file.GENERIC_WRITE,
                0, None,
                win32file.OPEN_EXISTING, 0, None,
            )
            self._recv_buffer = b""

    def send(self, to_peer, from_peer, data):
        """Send framed message via Named Pipe."""
        if isinstance(data, str):
            payload = data.rstrip("\n")
        else:
            payload = data.decode("utf-8").rstrip("\n") if isinstance(data, bytes) else data

        frame = frame_encode(payload)

        if self._is_server:
            with self._lock:
                pipe = self._connections.get(to_peer)
            if pipe:
                try:
                    win32file.WriteFile(pipe, frame)
                except pywintypes.error:
                    pass
        else:
            self._ensure_connected()
            win32file.WriteFile(self._client_pipe, frame)

    def recv(self, peer_name, limit=100):
        """Receive messages for peer_name."""
        if self._is_server:
            with self._lock:
                msgs = self._inbox.pop(peer_name, [])
            return msgs[:limit]
        else:
            self._ensure_connected()
            messages = []
            try:
                hr, data = win32file.ReadFile(self._client_pipe, 65536)
                if data:
                    self._recv_buffer += data
            except pywintypes.error:
                return []

            while True:
                msg, self._recv_buffer = frame_decode(self._recv_buffer)
                if msg is None:
                    break
                messages.append(msg)
                if len(messages) >= limit:
                    break

            return messages

    def close(self):
        """Shutdown transport and release resources."""
        self._running = False
        if self._accept_thread:
            self._accept_thread.join(timeout=1)
        with self._lock:
            for pipe in self._connections.values():
                try:
                    win32file.CloseHandle(pipe)
                except (pywintypes.error, OSError):
                    pass
            self._connections.clear()
        if hasattr(self, "_client_pipe") and self._client_pipe:
            try:
                win32file.CloseHandle(self._client_pipe)
            except (pywintypes.error, OSError):
                pass
            self._client_pipe = None
        self._buffers.clear()
        self._inbox.clear()
