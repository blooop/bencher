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
import re
import shutil
from importlib.metadata import PackageNotFoundError, version as get_package_version
from pathlib import Path
from urllib.parse import quote

import panel as pn

from .utils import publish_file

# Port for the Panel server (must be known at render time so iframe URLs can be built).
PANEL_PORT = 8051

# Port for the local rerun web viewer server (when rerun-sdk is available).
_RERUN_VIEWER_PORT = 9090

# Root directory for cached .rrd files and viewer pages.
_RRD_CACHE_DIR = Path("cachedir/rrd")

# Pattern for valid viewer version strings (semver-like, e.g. "0.30.1", "0.30.0-alpha.1").
_VERSION_RE = re.compile(r"^[0-9A-Za-z._-]+$")


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


def rrd_file_to_pane(  # pragma: no cover
    file_path,
    width: int = 300,
    height: int = 300,
    viewer_version: str | None = None,
    report_dir: str | Path | None = None,
):
    """Create a rerun viewer pane from an .rrd file path.

    Uses an HTML iframe to display the .rrd file.  If the ``rerun-sdk``
    package is installed, a local viewer server is started on port 9090
    for best results.  Otherwise the hosted viewer at ``app.rerun.io`` is
    used (requires the Panel server's CORS-enabled ``/rrd_static/`` route
    so the hosted viewer can fetch the file from localhost).

    The file must be located under ``cachedir/rrd/``.

    Parameters
    ----------
    file_path:
        Path to the .rrd file (must be under ``cachedir/rrd/``).
    width:
        Width of the viewer iframe in pixels.
    height:
        Height of the viewer iframe in pixels.
    viewer_version:
        When set, uses a self-contained viewer page loaded from the
        ``@rerun-io/web-viewer`` CDN at this exact version instead of the
        locally installed ``rerun-sdk``.  This is useful when the .rrd was
        recorded with a different SDK version than the one installed (e.g.
        a C++ SDK at 0.30.x while the Python SDK is 0.26.x).  The viewer
        page is written to ``cachedir/rrd/`` and served from the same
        HTTP origin as the .rrd files, avoiding mixed-content issues.
    report_dir:
        When set (together with ``viewer_version``), copies the .rrd and
        viewer HTML into this directory and uses relative URLs in the iframe.
        This makes the report portable — it works when served from any HTTP
        origin (e.g. CI report hosting on GCS/S3) without a live Panel
        server.  When ``None``, files stay in ``cachedir/rrd/`` and are
        served by the Panel server at ``/rrd_static/``.
    """
    rrd_path = Path(file_path).resolve()

    if report_dir is not None and viewer_version is not None:
        if not _VERSION_RE.match(viewer_version):
            raise ValueError(
                f"Invalid viewer_version {viewer_version!r}: must match [0-9A-Za-z._-]+"
            )
        return _portable_rrd_pane(rrd_path, viewer_version, Path(report_dir), width, height)

    cache_root = _RRD_CACHE_DIR.resolve()
    try:
        relative = rrd_path.relative_to(cache_root)
    except ValueError:
        raise ValueError(
            f"rrd_file_to_pane expects files under {cache_root}, got {rrd_path}"
        ) from None
    rrd_static_path = f"/rrd_static/{relative.as_posix()}"

    if viewer_version is not None and not _VERSION_RE.match(viewer_version):
        raise ValueError(f"Invalid viewer_version {viewer_version!r}: must match [0-9A-Za-z._-]+")

    if viewer_version is not None:
        # CDN viewer page is served from the same Panel origin — relative URL works.
        viewer_url = _cdn_viewer_url(relative, viewer_version)
        return pn.pane.HTML(
            f'<iframe src="{viewer_url}" width="{width}" height="{height}"'
            f' frameborder="0" allowfullscreen></iframe>',
            width=width,
            height=height,
        )

    # For the local rerun viewer or hosted viewer, the .rrd URL must be
    # absolute (cross-origin fetch).  Use JavaScript so the correct Panel
    # server port is resolved at render time instead of being hardcoded.
    try:
        from .utils_rerun import _ensure_rerun_viewer

        _ensure_rerun_viewer()
        viewer_tpl = f"http://localhost:{_RERUN_VIEWER_PORT}/?url="
    except (ImportError, ModuleNotFoundError):
        version = _get_rerun_version()
        viewer_tpl = f"https://app.rerun.io/version/{version}/?url="

    return pn.pane.HTML(
        f'<div id="rrd-wrap-{id(rrd_path)}"></div>'
        f"<script>"
        f"(function(){{"
        f'var rrdUrl=window.location.origin+"{rrd_static_path}";'
        f'var el=document.getElementById("rrd-wrap-{id(rrd_path)}");'
        f"el.innerHTML="
        f"""'<iframe src="{viewer_tpl}'+encodeURIComponent(rrdUrl)+'"'"""
        f""" +' width="{width}" height="{height}" frameborder="0"'"""
        f""" +' allowfullscreen></iframe>';"""
        f"}})();"
        f"</script>",
        width=width,
        height=height,
    )


# --- CDN viewer support ---

_CDN_VIEWER_TEMPLATE = """\
<!DOCTYPE html>
<html><head><meta charset="utf-8"/>
<style>html,body{{margin:0;padding:0;width:100%;height:100%;overflow:hidden}}</style>
</head><body>
<div id="c" style="width:100vw;height:100vh"></div>
<div id="e" style="color:red;padding:20px;font-family:monospace;white-space:pre-wrap"></div>
<script type="module">
try {{
  const p = new URLSearchParams(location.search);
  const url = p.get("url");
  if (!url) throw new Error("Missing ?url= parameter");
  const {{WebViewer}} = await import(
    "https://cdn.jsdelivr.net/npm/@rerun-io/web-viewer@{version}/+esm"
  );
  const v = new WebViewer();
  await v.start(new URL(url, location.href).href,
                document.getElementById("c"),
                {{hide_welcome_screen:true,width:"100%",height:"100%"}});
}} catch(e) {{
  document.getElementById("e").textContent = e.message + "\\n" + e.stack;
}}
</script></body></html>
"""

# Cache of generated viewer HTML pages keyed by version.
_cdn_viewer_versions: dict[str, str] = {}


def _cdn_viewer_url(rrd_relative: Path, version: str) -> str:
    """Return the iframe URL for a CDN-based viewer at the given version.

    Writes a ``viewer_<version>.html`` page into ``cachedir/rrd/`` (served
    by the Panel server at ``/rrd_static/``) that loads the rerun web viewer
    from the jsDelivr CDN.  Both the viewer page and the .rrd are on the
    same HTTP origin, avoiding mixed-content blocks.
    """
    if version not in _cdn_viewer_versions:
        html = _CDN_VIEWER_TEMPLATE.format(version=version)
        filename = f"viewer_{version}.html"
        viewer_path = _RRD_CACHE_DIR.resolve() / filename
        viewer_path.parent.mkdir(parents=True, exist_ok=True)
        if not viewer_path.exists() or viewer_path.read_text() != html:
            viewer_path.write_text(html)
        _cdn_viewer_versions[version] = filename

    filename = _cdn_viewer_versions[version]
    rrd_url = quote(f"/rrd_static/{rrd_relative.as_posix()}", safe="/:")
    return f"/rrd_static/{filename}?url={rrd_url}"


def _get_cdn_viewer_html(version: str) -> str:
    """Return the viewer HTML string for a given rerun version (cached)."""
    if version not in _cdn_viewer_versions:
        _cdn_viewer_versions[version] = _CDN_VIEWER_TEMPLATE.format(version=version)
    return _cdn_viewer_versions[version]


def _portable_rrd_pane(
    rrd_path: Path,
    version: str,
    report_dir: Path,
    width: int,
    height: int,
) -> pn.pane.HTML:
    """Create a self-contained pane with files copied into the report directory.

    Copies the .rrd and a CDN viewer HTML page into ``report_dir/rrd/`` and
    returns an iframe with a relative URL.  The resulting report can be served
    from any HTTP origin without a live Panel server.
    """
    rrd_subdir = report_dir / "rrd"
    rrd_subdir.mkdir(parents=True, exist_ok=True)

    # Copy .rrd
    rrd_dest = rrd_subdir / rrd_path.name
    shutil.copy2(rrd_path, rrd_dest)

    # Write viewer HTML (idempotent)
    html = _get_cdn_viewer_html(version)
    viewer_path = rrd_subdir / "viewer.html"
    if not viewer_path.exists() or viewer_path.read_text() != html:
        viewer_path.write_text(html)

    viewer_url = f"rrd/viewer.html?url={quote(rrd_path.name)}"
    return pn.pane.HTML(
        f'<iframe src="{viewer_url}" width="{width}" height="{height}"'
        f' frameborder="0" allowfullscreen></iframe>',
        width=width,
        height=height,
    )
