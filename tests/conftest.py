import socket

import pytest


@pytest.fixture
def no_network(monkeypatch):
    """Fails the test if anything tries to open a network connection."""

    def refuse(*args, **kwargs):
        raise AssertionError("the network was used")

    monkeypatch.setattr(socket.socket, "connect", refuse)
    monkeypatch.setattr(socket, "create_connection", refuse)
