"""ZEP socket transport — Unix Domain Socket with Frame Profile.

Frame Profile: 4-byte big-endian length prefix + JSON payload.
Per spec section 4.3: same-machine only, ~20us latency.
"""

import json
import os
import socket
import selectors
import struct
import threading
from pathlib import Path
from .base import BaseTransport

_HEADER_SIZE = 4
_MAX_PAYLOAD = 1 * 1024 * 1024  # 1MB recommended max


def frame_encode(data):
    """Encode a message string into Frame Profile wire format.

    Returns bytes: [4-byte big-endian length][UTF-8 JSON payload].
    """
    if isinstance(data, str):
        payload = data.rstrip("\n").encode("utf-8")
    else:
        payload = data
    length = struct.pack(">I", len(payload))
    return length + payload


def frame_decode(data):
    """Decode one frame from bytes buffer.

    Returns (message_str, remaining_bytes) or (None, data) if incomplete.
    """
    if len(data) < _HEADER_SIZE:
        return None, data
    length = struct.unpack(">I", data[:_HEADER_SIZE])[0]
    if length > _MAX_PAYLOAD:
        raise ValueError(f"Frame too large: {length} bytes (max {_MAX_PAYLOAD})")
    total = _HEADER_SIZE + length
    if len(data) < total:
        return None, data
    payload = data[_HEADER_SIZE:total]
    return payload.decode("utf-8"), data[total:]


class SocketTransport(BaseTransport):
    """Unix Domain Socket transport using Frame Profile.

    One peer acts as server (bind), others connect as clients.
    Messages are routed by 'to' field in the envelope.
    """

    def __init__(self, sock_path, is_server=False):
        self._sock_path = str(sock_path)
        self._is_server = is_server
        self._server_sock = None
        self._connections = {}       # peer_name -> socket
        self._buffers = {}           # peer_name -> bytes (recv buffer)
        self._inbox = {}             # peer_name -> [message_str, ...]
        self._lock = threading.Lock()
        self._selector = selectors.DefaultSelector()
        self._running = False
        self._accept_thread = None
        self._peer_name = None       # set after first send/recv

        if is_server:
            self._start_server()

    def _start_server(self):
        if os.path.exists(self._sock_path):
            os.unlink(self._sock_path)
        self._server_sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self._server_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._server_sock.bind(self._sock_path)
        self._server_sock.listen(8)
        self._server_sock.setblocking(False)
        self._selector.register(self._server_sock, selectors.EVENT_READ)
        self._running = True
        self._accept_thread = threading.Thread(target=self._io_loop, daemon=True)
        self._accept_thread.start()

    def _io_loop(self):
        while self._running:
            events = self._selector.select(timeout=0.01)
            for key, mask in events:
                if key.fileobj is self._server_sock:
                    self._accept_connection()
                else:
                    self._read_from(key.fileobj, key.data)

    def _accept_connection(self):
        conn, _ = self._server_sock.accept()
        conn.setblocking(False)
        self._selector.register(conn, selectors.EVENT_READ, data=conn)

    def _read_from(self, conn, data):
        try:
            chunk = conn.recv(65536)
        except (ConnectionResetError, BrokenPipeError):
            self._remove_connection(conn)
            return
        if not chunk:
            self._remove_connection(conn)
            return

        with self._lock:
            # Find which peer this connection belongs to
            peer = None
            for name, sock in self._connections.items():
                if sock is conn:
                    peer = name
                    break

            buf_key = id(conn)
            self._buffers.setdefault(buf_key, b"")
            self._buffers[buf_key] += chunk

            while True:
                msg, self._buffers[buf_key] = frame_decode(self._buffers[buf_key])
                if msg is None:
                    break
                # Route by 'to' field
                try:
                    envelope = json.loads(msg)
                    to_peer = envelope.get("to", "")
                    from_peer = envelope.get("from", "")
                    # Register the connection for the sender
                    if from_peer and from_peer not in self._connections:
                        self._connections[from_peer] = conn
                    self._inbox.setdefault(to_peer, []).append(msg)
                except json.JSONDecodeError:
                    pass  # discard malformed

    def _remove_connection(self, conn):
        try:
            self._selector.unregister(conn)
        except (KeyError, ValueError):
            pass
        try:
            conn.close()
        except OSError:
            pass
        with self._lock:
            for name, sock in list(self._connections.items()):
                if sock is conn:
                    del self._connections[name]
                    break
            self._buffers.pop(id(conn), None)

    def _ensure_connected(self, to_peer=None):
        """Client: connect to server socket if not already connected."""
        if self._is_server:
            return
        if not hasattr(self, "_client_sock") or self._client_sock is None:
            self._client_sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            self._client_sock.connect(self._sock_path)
            self._recv_buffer = b""

    def send(self, to_peer, from_peer, data):
        """Send framed message via socket."""
        if isinstance(data, str):
            # For socket transport, strip LF from JSONL profile
            payload = data.rstrip("\n")
        else:
            payload = data.decode("utf-8").rstrip("\n") if isinstance(data, bytes) else data

        frame = frame_encode(payload)

        if self._is_server:
            with self._lock:
                conn = self._connections.get(to_peer)
            if conn:
                try:
                    conn.sendall(frame)
                except (BrokenPipeError, ConnectionResetError, OSError):
                    self._remove_connection(conn)
        else:
            self._ensure_connected()
            self._client_sock.sendall(frame)

    def recv(self, peer_name, limit=100):
        """Receive messages for peer_name."""
        if self._is_server:
            # Server: messages are already in inbox from io_loop
            with self._lock:
                msgs = self._inbox.pop(peer_name, [])
            return msgs[:limit]
        else:
            # Client: read from socket directly
            self._ensure_connected()
            self._client_sock.setblocking(False)
            messages = []
            try:
                chunk = self._client_sock.recv(65536)
                if chunk:
                    self._recv_buffer += chunk
            except BlockingIOError:
                pass
            except (ConnectionResetError, BrokenPipeError):
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
        if self._server_sock:
            try:
                self._selector.unregister(self._server_sock)
            except (KeyError, ValueError):
                pass
            self._server_sock.close()
        for conn in list(self._connections.values()):
            try:
                conn.close()
            except OSError:
                pass
        if hasattr(self, "_client_sock") and self._client_sock:
            try:
                self._client_sock.close()
            except OSError:
                pass
            self._client_sock = None
        self._selector.close()
        if self._is_server and os.path.exists(self._sock_path):
            os.unlink(self._sock_path)
        self._connections.clear()
        self._buffers.clear()
        self._inbox.clear()
