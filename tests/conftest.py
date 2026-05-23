import socket

import pytest
from dotenv import load_dotenv

load_dotenv("/app/.env")


def pytest_configure(config):
    config.addinivalue_line("markers", "network: hits live chain RPCs (mainnet)")
    config.addinivalue_line("markers", "supersim: requires a local supersim daemon (Lisk on :4445, Uni on :4446)")


def _port_open(host: str, port: int, timeout: float = 1.0) -> bool:
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(timeout)
    try:
        return sock.connect_ex((host, port)) == 0
    finally:
        sock.close()


def pytest_collection_modifyitems(config, items):
    if _port_open("127.0.0.1", 4445) and _port_open("127.0.0.1", 4446):
        return
    skip = pytest.mark.skip(reason="supersim not running (need Lisk on :4445 and Uni on :4446)")
    for item in items:
        if "supersim" in item.keywords:
            item.add_marker(skip)
