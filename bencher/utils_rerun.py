"""Rerun SDK integration for bencher — capture live recordings.

This module requires the ``rerun-sdk`` package.  For functions that work
with pre-recorded ``.rrd`` files without the SDK, see ``utils_rrd.py``.

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
   (localhost:9090) and fetches ``.rrd`` files from the Panel server.
   Without ``Access-Control-Allow-Origin: *`` **and** ``OPTIONS`` preflight
   handling, browsers silently block the fetch and the viewer shows 0 B of
   data.  The Panel port is auto-assigned (port 0) so that multiple
   benchmarks can run in parallel; iframe URLs are built with JavaScript
   to resolve the actual port at render time.

3. **Viewer** — ``rr.start_web_viewer_server()`` launches a *local* rerun
   web viewer on port 9090.  This is the viewer that actually renders the
   data.  When the SDK is not available, ``rrd_file_to_pane`` (in
   ``utils_rrd.py``) falls back to the hosted viewer at ``app.rerun.io``.
"""

import rerun as rr

from .utils import gen_rerun_data_path
from .utils_rrd import _RERUN_VIEWER_PORT, rrd_file_to_pane

_viewer_started = False


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
