"""Rerun integration for bencher — embed rerun viewer panes in Panel reports.

Architecture
------------
Displaying rerun data inside a Panel/Bokeh report requires three cooperating
pieces.  Getting any one of them wrong results in blank viewers, CORS errors,
or "data source left unexpectedly" messages.

1. **Data capture** — ``capture_rerun_rrd()`` drains the in-memory rerun
   recording to a *complete* ``.rrd`` file on disk.  Using ``rr.save()``
   (which streams to an open file) does NOT work because the file is still
   being written when the viewer tries to fetch it.  Always call
   ``rr.log(...)`` first, then ``capture_rerun_rrd()`` / ``capture_rerun_window()``.

2. **File serving** — The Panel server (Tornado) serves the ``.rrd`` files at
   ``/rrd_static/`` with full CORS headers (including OPTIONS preflight).
   This is configured in ``bench_plot_server.py`` via ``_rrd_extra_patterns()``.
   A separate stdlib file server (``file_server.py``) also exists for
   standalone use but is NOT needed for the normal report flow.

   CORS is critical: the rerun web viewer runs on a different origin
   (localhost:9090) and fetches ``.rrd`` files from the Panel origin
   (localhost:8051).  Without ``Access-Control-Allow-Origin: *`` **and**
   ``OPTIONS`` preflight handling, browsers silently block the fetch and the
   viewer shows 0 B of data.

3. **Viewer** — ``rr.start_web_viewer_server()`` launches a *local* rerun
   web viewer on port 9090.  This is the viewer that actually renders the
   data.  Do NOT use ``app.rerun.io`` — the CDN viewer's ``web_event://``
   postMessage protocol does not work when embedded in Panel's Bokeh Div
   (innerHTML does not execute ``<script>`` tags).

Alternatives that were tried and do NOT work
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
- **app.rerun.io + postMessage (``as_html()``)** — Panel sets innerHTML which
  does not execute scripts, so the base64 data never reaches the viewer.
  Wrapping in ``<iframe srcdoc="...">`` executes the script but the nested
  postMessage still fails to deliver data (viewer shows 0 B).
- **Data URIs in the viewer URL** — the rerun viewer cannot parse ``data:``
  URIs as the ``?url=`` parameter.
- **``rr.save()`` to a file + external file server** — the file is incomplete
  (still being written) when the viewer fetches it, causing "data source
  left unexpectedly" errors.  Also requires a separate server process which
  is fragile (port conflicts, zombie processes).
"""

import logging
from importlib.metadata import version as get_package_version, PackageNotFoundError
from pathlib import Path

import rerun as rr
import panel as pn
from .utils import publish_file, gen_rerun_data_path


# Port for the local rerun web viewer server.
_RERUN_VIEWER_PORT = 9090
_viewer_started = False

# Port for the Panel server (must be known at render time so iframe URLs can be built).
PANEL_PORT = 8051


def _ensure_rerun_init():  # pragma: no cover
    """Ensure a rerun recording exists, creating one if needed."""
    if rr.get_global_data_recording() is None:
        rr.init("bencher")


def _ensure_rerun_viewer():  # pragma: no cover
    """Start the local rerun web viewer server if not already running."""
    global _viewer_started  # noqa: PLW0603  # pylint: disable=global-statement
    if not _viewer_started:
        rr.start_web_viewer_server(port=_RERUN_VIEWER_PORT)
        _viewer_started = True


def _get_rerun_version() -> str:
    """Get the installed rerun package version."""
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
    branch_name,
    content_callback: callable,
    version: str | None = None,
):  # pragma: no cover
    publish_file(file_path, remote=remote, branch_name="test_rrd")
    publish_path = content_callback(remote, branch_name, file_path)
    logging.info(publish_path)
    return rrd_to_pane(publish_path, version=version)


def capture_rerun_rrd(recording: rr.RecordingStream | None = None) -> str:  # pragma: no cover
    """Save the current rerun recording to an .rrd file and return the path.

    Data must be logged BEFORE calling this function so that the in-memory
    recording has content to drain.  Calls ``rr.init()`` automatically if no
    recording exists yet.
    """
    _ensure_rerun_init()
    rec = recording or rr.get_global_data_recording()
    rrd_bytes = rec.memory_recording().drain_as_bytes()
    file_path = gen_rerun_data_path()
    with open(file_path, "wb") as f:
        f.write(rrd_bytes)
    return file_path


def rrd_file_to_pane(
    file_path, width: int = 300, height: int = 300, **kwargs
):  # pragma: no cover  # pylint: disable=unused-argument
    """Create a rerun viewer pane from an .rrd file path.

    Uses an HTML iframe with the local rerun web viewer. The .rrd file is
    served via the Panel server's CORS-enabled /rrd_static/ route.
    """
    _ensure_rerun_viewer()
    rrd_path = Path(file_path).resolve()
    cache_root = Path("cachedir/rrd").resolve()
    relative = rrd_path.relative_to(cache_root)
    rrd_url = f"http://localhost:{PANEL_PORT}/rrd_static/{relative}"
    viewer_url = f"http://localhost:{_RERUN_VIEWER_PORT}/?url={rrd_url}"
    return pn.pane.HTML(
        f'<iframe src="{viewer_url}" width="{width}" height="{height}"'
        f' frameborder="0" allowfullscreen></iframe>',
        width=width,
        height=height,
    )


def rerun_to_pane(
    width: int = 950, height: int = 712, recording: rr.RecordingStream | None = None
):  # pragma: no cover
    """Render the current rerun recording as an inline HTML pane."""
    file_path = capture_rerun_rrd(recording=recording)
    return rrd_file_to_pane(file_path, width=width, height=height)


def capture_rerun_window(
    width: int = 500, height: int = 500, recording: rr.RecordingStream | None = None
):  # pragma: no cover
    """Capture the current rerun recording as an inline Panel widget.

    Data must be logged BEFORE calling this function so that the in-memory
    recording has content to drain.
    """
    return rerun_to_pane(width=width, height=height, recording=recording)
