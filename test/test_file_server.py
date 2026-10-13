"""Tests for bencher/file_server.py"""

import socket
import tempfile
import threading
import time
import unittest
import urllib.error
import urllib.request
from pathlib import Path

import pytest

from bencher.file_server import create_server, run_file_server


def wait_for_port(port: int, timeout: float = 5.0, step: float = 0.1) -> None:
    """Poll until the server accepts TCP connections, instead of a fixed sleep."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=step):
                return
        except OSError:
            time.sleep(step)
    raise TimeoutError(f"Server on port {port} did not accept connections within {timeout}s")


class TestFileServer(unittest.TestCase):
    def test_create_server(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            test_file = Path(tmpdir) / "test.txt"
            test_file.write_text("hello world")

            server = create_server(tmpdir, port=0)
            threading.Thread(target=server.serve_forever, daemon=True).start()
            port = server.server_address[1]
            wait_for_port(port)

            try:
                with urllib.request.urlopen(f"http://127.0.0.1:{port}/test.txt") as resp:
                    assert resp.status == 200
                    assert resp.read() == b"hello world"
            finally:
                server.shutdown()
                server.server_close()

    def test_create_server_missing_file(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            server = create_server(tmpdir, port=0)
            threading.Thread(target=server.serve_forever, daemon=True).start()
            port = server.server_address[1]
            wait_for_port(port)

            try:
                with pytest.raises(urllib.error.HTTPError) as ctx:
                    urllib.request.urlopen(f"http://127.0.0.1:{port}/nonexistent.txt")
                assert ctx.value.code == 404
            finally:
                server.shutdown()
                server.server_close()

    def test_run_file_server(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            test_file = Path(tmpdir) / "health.txt"
            test_file.write_text("ok")

            server = run_file_server(directory=tmpdir, port=0)
            port = server.server_address[1]
            wait_for_port(port)

            try:
                with urllib.request.urlopen(f"http://127.0.0.1:{port}/health.txt") as resp:
                    assert resp.read() == b"ok"
            finally:
                server.shutdown()
                server.server_close()
