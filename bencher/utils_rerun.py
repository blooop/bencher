import logging
from importlib.metadata import version as get_package_version, PackageNotFoundError

import rerun as rr
import panel as pn
from rerun_notebook import Viewer
from .utils import publish_file


def _get_rerun_version() -> str:
    """Get the installed rerun package version."""
    try:
        return get_package_version("rerun-sdk")
    except PackageNotFoundError:
        return "0.30.0"


def rerun_to_pane(
    width: int = 950, height: int = 712, recording: rr.RecordingStream | None = None
):  # pragma: no cover
    """Render the current rerun recording as an inline Panel widget."""
    if recording is None:
        recording = rr.get_global_data_recording()
    viewer = Viewer(width=width, height=height)
    viewer.send_rrd(recording.memory_recording().drain_as_bytes())
    return pn.pane.IPyWidget(viewer)


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


def rrd_file_to_pane(file_path, **kwargs):  # pragma: no cover  # pylint: disable=unused-argument
    """Create a rerun Viewer widget from an .rrd file path.

    Args:
        file_path: Path to the .rrd file.

    Returns:
        pn.pane.IPyWidget: A Panel widget wrapping the rerun Viewer.
    """
    viewer = Viewer()
    with open(file_path, "rb") as f:
        viewer.send_rrd(f.read())
    return pn.pane.IPyWidget(viewer)


def capture_rerun_window(
    width: int = 500, height: int = 500, recording: rr.RecordingStream | None = None
):  # pragma: no cover
    """Capture the current rerun recording as an inline Panel widget.

    Data must be logged BEFORE calling this function so that the in-memory
    recording has content to drain.
    """
    return rerun_to_pane(width=width, height=height, recording=recording)
