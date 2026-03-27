"""Serve files from a directory over HTTP with CORS headers (stdlib only)."""

import functools
import threading
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path


class _CORSHandler(SimpleHTTPRequestHandler):
    """Static file handler that adds Access-Control-Allow-Origin: *."""

    def end_headers(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        super().end_headers()

    def log_message(self, *_args, **_kwargs):
        pass  # suppress per-request console spam


def create_server(directory, port=8001):
    """Create an HTTP server serving *directory* on *port*."""
    handler = functools.partial(_CORSHandler, directory=str(directory))
    return ThreadingHTTPServer(("127.0.0.1", port), handler)


def run_file_server(directory=None, port=8001):
    """Start a background HTTP file server (daemon thread).

    Returns the ``ThreadingHTTPServer`` so callers can query
    ``server.server_address[1]`` for the actual port (useful when *port=0*).
    """
    if directory is None:
        directory = Path("cachedir/").absolute().as_posix()
    server = create_server(directory, port)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    actual_port = server.server_address[1]
    print(f"File server is running on port {actual_port} serving files from {directory}")
    return server
