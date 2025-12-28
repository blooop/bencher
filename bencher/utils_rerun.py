import logging
from importlib.metadata import version as get_package_version, PackageNotFoundError
from rerun.legacy_notebook import as_html
import rerun as rr
import panel as pn
from .utils import publish_file, gen_rerun_data_path


def _get_rerun_version() -> str:
    """Get the installed rerun package version."""
    try:
        return get_package_version("rerun-sdk")
    except PackageNotFoundError:
        return "0.20.1"  # Fallback version


def rrd_to_pane(
    url: str, width: int = 500, height: int = 600, version: str | None = None
):  # pragma: no cover
    if version is None:
        version = _get_rerun_version()
    return pn.pane.HTML(
        f'<iframe src="https://app.rerun.io/version/{version}/?url={url}" width={width} height={height}></iframe>'
    )


def to_pane(path: str):
    as_html()
    return rrd_to_pane(path)


def publish_and_view_rrd(
    file_path: str,
    remote: str,
    branch_name,
    content_callback: callable,
    version: str | None = None,
):  # pragma: no cover
    as_html()
    publish_file(file_path, remote=remote, branch_name="test_rrd")
    publish_path = content_callback(remote, branch_name, file_path)
    logging.info(publish_path)
    return rrd_to_pane(publish_path, version=version)


def capture_rerun_window(width: int = 500, height: int = 500):
    rrd_path = gen_rerun_data_path()
    rr.save(rrd_path)
    path = rrd_path.split("cachedir")[1]
    return rrd_to_pane(f"http://127.0.0.1:8001/{path}", width=width, height=height)
