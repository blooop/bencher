"""Serve files from a directory over HTTP with CORS headers (stdlib only)."""

import functools
import logging
import threading
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

logger = logging.getLogger(__name__)


class _CORSHandler(SimpleHTTPRequestHandler):
    """Static file handler with full CORS support (including preflight)."""

    def end_headers(self) -> None:
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "*")
        super().end_headers()

    def do_OPTIONS(self) -> None:
        self.send_response(200)
        self.end_headers()

    def log_message(self, *_args: object, **_kwargs: object) -> None:
        pass  # suppress per-request console spam


class _ReusableServer(ThreadingHTTPServer):
    allow_reuse_address = True


def create_server(directory: str | Path, port: int = 8001) -> ThreadingHTTPServer:
    """Create an HTTP server serving *directory* on *port*."""
    handler = functools.partial(_CORSHandler, directory=str(directory))
    return _ReusableServer(
        ("0.0.0.0", port),  # noqa: S104 - serves rerun files to viewers in other containers
        handler,
    )


def run_file_server(
    directory: str | Path | None = None, port: int = 8001
) -> ThreadingHTTPServer | None:
    """Start a background HTTP file server (daemon thread).

    If *port* is already in use the existing server is assumed to be running
    and the function returns ``None`` instead of raising.

    Returns the ``ThreadingHTTPServer`` so callers can query
    ``server.server_address[1]`` for the actual port (useful when *port=0*).
    """
    if directory is None:
        directory = Path("cachedir/").absolute().as_posix()
    try:
        server = create_server(directory, port)
    except OSError:
        logger.info(f"File server port {port} already in use — assuming server is already running")
        return None
    threading.Thread(target=server.serve_forever, daemon=True).start()
    actual_port = server.server_address[1]
    logger.info(f"File server is running on port {actual_port} serving files from {directory}")
    return server
