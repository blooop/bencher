import logging
from importlib.metadata import version as get_package_version, PackageNotFoundError
from pathlib import Path

import rerun as rr
import panel as pn
from .utils import publish_file


# Directory where .rrd files are stored, served at /rrd_static/ by the Panel server.
RRD_CACHE_DIR = str(Path("cachedir/rrd").resolve())

# Port for the local rerun web viewer server.
_RERUN_VIEWER_PORT = 9090
_viewer_started = False

# Port for the Panel server (must be known at render time so iframe URLs can be built).
PANEL_PORT = 8051


def _ensure_rerun_viewer():  # pragma: no cover
    """Start the local rerun web viewer server if not already running."""
    global _viewer_started  # noqa: PLW0603
    if not _viewer_started:
        rr.start_web_viewer_server(port=_RERUN_VIEWER_PORT)
        _viewer_started = True


def _get_rerun_version() -> str:
    """Get the installed rerun package version."""
    try:
        return get_package_version("rerun-sdk")
    except PackageNotFoundError:
        return "0.30.0"


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
    recording has content to drain.

    Args:
        recording: Optional recording stream. Uses global recording if None.

    Returns:
        str: Path to the saved .rrd file.
    """
    from bencher.utils import gen_rerun_data_path

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

    Args:
        file_path: Path to the .rrd file.
        width: Viewer width in pixels.
        height: Viewer height in pixels.

    Returns:
        pn.pane.HTML: An HTML pane with an embedded rerun viewer iframe.
    """
    _ensure_rerun_viewer()
    rrd_path = Path(file_path).resolve()
    cache_root = Path(RRD_CACHE_DIR)
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
    """Render the current rerun recording as an inline HTML pane.

    Saves the recording to an .rrd file and displays it via the rerun web viewer.
    """
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
