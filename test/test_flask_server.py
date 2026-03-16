"""Tests for bencher/flask_server.py"""

import unittest
import tempfile
from pathlib import Path

from bencher.flask_server import create_server, run_flask_in_thread


class TestFlaskServer(unittest.TestCase):
    def test_create_server(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            # Write a test file
            test_file = Path(tmpdir) / "test.txt"
            test_file.write_text("hello world")

            app = create_server(tmpdir)
            self.assertIsNotNone(app)

            # Use Flask test client to verify GET
            with app.test_client() as client:
                resp = client.get("/test.txt")
                self.assertEqual(resp.status_code, 200)
                self.assertEqual(resp.data, b"hello world")

    def test_create_server_missing_file(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            app = create_server(tmpdir)
            with app.test_client() as client:
                resp = client.get("/nonexistent.txt")
                self.assertEqual(resp.status_code, 404)

    def test_run_flask_in_thread(self):
        import time
        import urllib.request
        import urllib.error

        with tempfile.TemporaryDirectory() as tmpdir:
            test_file = Path(tmpdir) / "health.txt"
            test_file.write_text("ok")

            run_flask_in_thread(directory=tmpdir, port=18901)
            time.sleep(0.5)

            # Verify the server is actually serving requests
            with urllib.request.urlopen("http://127.0.0.1:18901/health.txt") as resp:
                self.assertEqual(resp.read(), b"ok")
