"""Utilities for serving and viewing .rrd files without the rerun Python SDK.

This module provides functions for displaying pre-recorded .rrd files
(e.g. those produced by the C++ rerun library) in Panel reports.  It does
NOT depend on the ``rerun-sdk`` package, so downstream projects that cannot
install it (e.g. because of a NumPy 2 requirement) can still use these
utilities.

See ``utils_rerun.py`` for functions that require the rerun Python SDK
(live capture, recording management, etc.).
"""

import logging
from importlib.metadata import PackageNotFoundError, version as get_package_version
from pathlib import Path

import panel as pn

from .utils import publish_file

# Port for the Panel server (must be known at render time so iframe URLs can be built).
PANEL_PORT = 8051

# Port for the local rerun web viewer server (when rerun-sdk is available).
_RERUN_VIEWER_PORT = 9090


def _get_rerun_version() -> str:
    """Get the installed rerun package version, or a sensible default."""
    try:
        return get_package_version("rerun-sdk")
    except PackageNotFoundError:
        return "0.30.1"


def rrd_to_pane(
    url: str, width: int = 500, height: int = 600, version: str | None = None
):  # pragma: no cover
    """Display an .rrd file from a URL using the hosted rerun web viewer."""
    if version is None:
        version = _get_rerun_version()
    return pn.pane.HTML(
        f'<iframe src="https://app.rerun.io/version/{version}/?url={url}"'
        f" width={width} height={height}></iframe>"
    )


def publish_and_view_rrd(
    file_path: str,
    remote: str,
    branch_name: str,
    content_callback: callable,
    version: str | None = None,
):  # pragma: no cover
    publish_file(file_path, remote=remote, branch_name=branch_name)
    publish_path = content_callback(remote, branch_name, file_path)
    logging.info(publish_path)
    return rrd_to_pane(publish_path, version=version)


def rrd_file_to_pane(file_path, width: int = 300, height: int = 300):  # pragma: no cover
    """Create a rerun viewer pane from an .rrd file path.

    Uses an HTML iframe to display the .rrd file.  If the ``rerun-sdk``
    package is installed, a local viewer server is started on port 9090
    for best results.  Otherwise the hosted viewer at ``app.rerun.io`` is
    used (requires the Panel server's CORS-enabled ``/rrd_static/`` route
    so the hosted viewer can fetch the file from localhost).

    The file must be located under ``cachedir/rrd/``.
    """
    rrd_path = Path(file_path).resolve()
    cache_root = Path("cachedir/rrd").resolve()
    try:
        relative = rrd_path.relative_to(cache_root)
    except ValueError:
        raise ValueError(
            f"rrd_file_to_pane expects files under {cache_root}, got {rrd_path}"
        ) from None
    rrd_url = f"http://localhost:{PANEL_PORT}/rrd_static/{relative}"

    # Prefer the local rerun viewer when the SDK is available.
    try:
        from .utils_rerun import _ensure_rerun_viewer

        _ensure_rerun_viewer()
        viewer_url = f"http://localhost:{_RERUN_VIEWER_PORT}/?url={rrd_url}"
    except (ImportError, ModuleNotFoundError):
        version = _get_rerun_version()
        viewer_url = f"https://app.rerun.io/version/{version}/?url={rrd_url}"

    return pn.pane.HTML(
        f'<iframe src="{viewer_url}" width="{width}" height="{height}"'
        f' frameborder="0" allowfullscreen></iframe>',
        width=width,
        height=height,
    )
