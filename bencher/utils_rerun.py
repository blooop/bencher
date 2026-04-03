"""Rerun SDK integration for bencher — capture live recordings.

This module requires the ``rerun-sdk`` package.  For functions that work
with pre-recorded ``.rrd`` files without the SDK, see ``utils_rrd.py``.

Architecture
------------
Displaying rerun data inside a Panel/Bokeh report requires two pieces:

1. **Data capture** — ``capture_rerun_rrd()`` drains the in-memory rerun
   recording to a *complete* ``.rrd`` file on disk.  Using ``rr.save()``
   (which streams to an open file) does NOT work because the file is still
   being written when the viewer tries to fetch it.  Always call
   ``rr.log(...)`` first, then ``capture_rerun_rrd()`` / ``capture_rerun_window()``.

2. **Viewer** — ``rrd_file_to_pane()`` (in ``utils_rrd.py``) writes a
   small HTML page that loads the ``@rerun-io/web-viewer`` from CDN and
   points it at the ``.rrd`` file.  Both the viewer page and the data are
   served by the Panel server at ``/rrd_static/``, keeping everything on
   the same HTTP origin (no CORS, no extra ports).
"""

import rerun as rr

from .utils import gen_rerun_data_path
from .utils_rrd import rrd_file_to_pane


def _ensure_rerun_init():  # pragma: no cover
    """Ensure a rerun recording exists, creating one if needed."""
    if rr.get_global_data_recording() is None:
        rr.init("bencher")


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


def capture_rerun_window(recording: rr.RecordingStream | None = None, **_kwargs) -> str:  # pragma: no cover
    """Capture the current rerun recording and return the .rrd file path.

    Data must be logged BEFORE calling this function so that the in-memory
    recording has content to drain.  The returned path is stored by
    ``ResultRerun``; rendering into an HTML viewer pane happens later via
    ``ResultRerun.to_container()``.

    .. note::
       Viewer dimensions (``width``/``height``) are now taken from the
       ``ResultRerun`` descriptor, so any keyword arguments passed here
       are accepted but ignored.
    """
    return capture_rerun_rrd(recording=recording)
