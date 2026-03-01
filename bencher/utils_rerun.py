import logging
from importlib.metadata import version as get_package_version, PackageNotFoundError

import rerun as rr
import panel as pn
from rerun_notebook import Viewer
from .utils import publish_file, gen_rerun_data_path


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


def capture_rerun_window(width: int = 500, height: int = 500):
    rrd_path = gen_rerun_data_path()
    rr.save(rrd_path)
    path = rrd_path.split("cachedir")[1]
    return rrd_to_pane(f"http://127.0.0.1:8001/{path}", width=width, height=height)
