"""Tests for bencher/file_server.py"""

import threading
import time
import tempfile
import unittest
import urllib.request
import urllib.error
from pathlib import Path

from bencher.file_server import create_server, run_file_server


class TestFileServer(unittest.TestCase):
    def test_create_server(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            test_file = Path(tmpdir) / "test.txt"
            test_file.write_text("hello world")

            server = create_server(tmpdir, port=0)
            threading.Thread(target=server.serve_forever, daemon=True).start()
            port = server.server_address[1]
            time.sleep(0.3)

            try:
                with urllib.request.urlopen(f"http://127.0.0.1:{port}/test.txt") as resp:
                    self.assertEqual(resp.status, 200)
                    self.assertEqual(resp.read(), b"hello world")
            finally:
                server.shutdown()
                server.server_close()

    def test_create_server_missing_file(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            server = create_server(tmpdir, port=0)
            threading.Thread(target=server.serve_forever, daemon=True).start()
            port = server.server_address[1]
            time.sleep(0.3)

            try:
                with self.assertRaises(urllib.error.HTTPError) as ctx:
                    urllib.request.urlopen(  # pylint: disable=consider-using-with
                        f"http://127.0.0.1:{port}/nonexistent.txt"
                    )
                self.assertEqual(ctx.exception.code, 404)
            finally:
                server.shutdown()
                server.server_close()

    def test_run_file_server(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            test_file = Path(tmpdir) / "health.txt"
            test_file.write_text("ok")

            server = run_file_server(directory=tmpdir, port=0)
            port = server.server_address[1]
            time.sleep(0.3)

            try:
                with urllib.request.urlopen(f"http://127.0.0.1:{port}/health.txt") as resp:
                    self.assertEqual(resp.read(), b"ok")
            finally:
                server.shutdown()
                server.server_close()
