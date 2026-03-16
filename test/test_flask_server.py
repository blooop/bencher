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

        with tempfile.TemporaryDirectory() as tmpdir:
            # Use a high port to avoid conflicts
            run_flask_in_thread(directory=tmpdir, port=18901)
            # Give the thread a moment to start
            time.sleep(0.5)
            # The server should be running (we can't easily verify the thread
            # but we can verify it didn't crash)
