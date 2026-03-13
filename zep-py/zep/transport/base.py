"""ZEP transport base interface."""

from abc import ABC, abstractmethod


class BaseTransport(ABC):
    @abstractmethod
    def send(self, to_peer, from_peer, data):
        """Send serialized message bytes to target peer."""
        ...

    @abstractmethod
    def recv(self, peer_name, limit=100):
        """Receive up to `limit` raw message strings for peer."""
        ...

    @abstractmethod
    def close(self):
        """Release resources."""
        ...
