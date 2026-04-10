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

# Root directory for cached .rrd files and viewer pages.
_RRD_CACHE_DIR = Path("cachedir/rrd")

# Pattern for valid viewer version strings (semver-like, e.g. "0.30.1", "0.30.0-alpha.1").
_VERSION_RE = re.compile(r"^[0-9A-Za-z._-]+$")


def _get_rerun_version() -> str:
    """Get the installed rerun package version, or a sensible default."""
    try:
        return get_package_version("rerun-sdk")
    except PackageNotFoundError:
        return "0.31.1"


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

    Uses an HTML iframe to display the .rrd file.  By default the viewer
    is loaded from the ``@rerun-io/web-viewer`` CDN at the installed
    ``rerun-sdk`` version.  The viewer page and the ``.rrd`` data are
    both served from the Panel server's ``/rrd_static/`` route, keeping
    everything on a single origin (no CORS, no extra ports).

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
        Rerun web-viewer version to load from CDN.  Defaults to the
        installed ``rerun-sdk`` version.  Set explicitly when the .rrd
        was recorded with a different SDK version.
    report_dir:
        When set, copies the .rrd and viewer HTML into this directory
        and uses relative URLs in the iframe.  This makes the report
        portable — it works when served from any HTTP origin without a
        live Panel server.
    """
    rrd_path = Path(file_path).resolve()

    # Resolve viewer version: explicit > installed SDK > fallback.
    if viewer_version is None:
        viewer_version = _get_rerun_version()
    if not _VERSION_RE.match(viewer_version):
        raise ValueError(f"Invalid viewer_version {viewer_version!r}: must match [0-9A-Za-z._-]+")

    if report_dir is not None:
        return _portable_rrd_pane(rrd_path, viewer_version, Path(report_dir), width, height)

    cache_root = _RRD_CACHE_DIR.resolve()
    try:
        relative = rrd_path.relative_to(cache_root)
    except ValueError:
        raise ValueError(
            f"rrd_file_to_pane expects files under {cache_root}, got {rrd_path}"
        ) from None

    # CDN viewer page is served from the same Panel origin — relative URL works.
    viewer_url = _cdn_viewer_url(relative, viewer_version)
    return pn.pane.HTML(
        f'<iframe src="{viewer_url}" width="{width}" height="{height}"'
        f' frameborder="0" allowfullscreen></iframe>',
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

# Cache of written viewer page filenames, keyed by version (for /rrd_static/ URLs).
_cdn_viewer_files: dict[str, str] = {}

# Cache of rendered viewer HTML strings, keyed by version (for portable reports).
_cdn_viewer_html: dict[str, str] = {}


def _cdn_viewer_url(rrd_relative: Path, version: str) -> str:
    """Return the iframe URL for a CDN-based viewer at the given version.

    Writes a ``viewer_<version>.html`` page into ``cachedir/rrd/`` (served
    by the Panel server at ``/rrd_static/``) that loads the rerun web viewer
    from the jsDelivr CDN.  Both the viewer page and the .rrd are on the
    same HTTP origin, avoiding mixed-content blocks.
    """
    if version not in _cdn_viewer_files:
        html = _CDN_VIEWER_TEMPLATE.format(version=version)
        filename = f"viewer_{version}.html"
        viewer_path = _RRD_CACHE_DIR.resolve() / filename
        viewer_path.parent.mkdir(parents=True, exist_ok=True)
        if not viewer_path.exists() or viewer_path.read_text() != html:
            viewer_path.write_text(html)
        _cdn_viewer_files[version] = filename

    filename = _cdn_viewer_files[version]
    rrd_url = quote(f"/rrd_static/{rrd_relative.as_posix()}", safe="/:")
    return f"/rrd_static/{filename}?url={rrd_url}"


def _get_cdn_viewer_html(version: str) -> str:
    """Return the viewer HTML string for a given rerun version (cached)."""
    if version not in _cdn_viewer_html:
        _cdn_viewer_html[version] = _CDN_VIEWER_TEMPLATE.format(version=version)
    return _cdn_viewer_html[version]


def _write_rrd_sidecar(rrd_path: Path, version: str, dest_dir: Path) -> tuple[str, str]:
    """Copy an .rrd file and its CDN viewer page into *dest_dir*.

    Returns ``(viewer_filename, rrd_filename)`` — both relative to *dest_dir*.
    The viewer page is written idempotently (skipped if already up-to-date).
    """
    dest_dir.mkdir(parents=True, exist_ok=True)

    # Preserve the per-job-key subdirectory structure used by gen_path()
    # to avoid collisions when multiple .rrd files share the same basename.
    job_key = rrd_path.parent.name
    rrd_subdir = dest_dir / job_key
    rrd_subdir.mkdir(parents=True, exist_ok=True)
    shutil.copy2(rrd_path, rrd_subdir / rrd_path.name)

    viewer_html = _get_cdn_viewer_html(version)
    viewer_name = f"viewer_{version}.html"
    viewer_path = dest_dir / viewer_name
    if not viewer_path.exists() or viewer_path.read_text() != viewer_html:
        viewer_path.write_text(viewer_html, encoding="utf-8")

    return viewer_name, f"{job_key}/{rrd_path.name}"


def _portable_rrd_pane(
    rrd_path: Path,
    version: str,
    report_dir: Path,
    width: int,
    height: int,
) -> pn.pane.HTML:
    """Create a self-contained pane with files copied into the report directory.

    Copies the .rrd and a CDN viewer HTML page into ``report_dir/_rrd/`` and
    returns an iframe with a relative URL.  The resulting report can be served
    from any HTTP origin without a live Panel server.
    """
    rrd_subdir = report_dir / "_rrd"
    viewer_name, rrd_name = _write_rrd_sidecar(rrd_path, version, rrd_subdir)

    viewer_url = f"_rrd/{viewer_name}?url={quote(rrd_name)}"
    return pn.pane.HTML(
        f'<iframe src="{viewer_url}" width="{width}" height="{height}"'
        f' frameborder="0" allowfullscreen></iframe>',
        width=width,
        height=height,
    )


# --- Static .rrd support for saved reports ---

# Regex matching rerun viewer iframes in Panel-saved HTML.
# Panel's Bokeh serialization double-escapes: < → &amp;lt; " → &amp;quot;
# Captures: (1) viewer version, (2) rrd file relative path, (3) width, (4) height.
#
# FRAGILE: This pattern depends on Bokeh's exact double-entity-encoding behaviour
# (tested with Bokeh 3.9 / Panel 1.6).  If Bokeh changes its serialization (attribute
# order, quoting style, escaping depth), this regex will silently miss iframes.
# inline_rrd_iframes() logs a warning when it detects /rrd_static/ references but
# the regex finds no matches.
_RRD_IFRAME_RE = re.compile(
    r"&amp;lt;iframe src=&amp;quot;/rrd_static/viewer_([0-9A-Za-z._-]+)\.html"
    r"\?url=/rrd_static/([^&]+\.rrd)&amp;quot;"
    r" width=&amp;quot;(\d+)&amp;quot;"
    r" height=&amp;quot;(\d+)&amp;quot;"
    r" frameborder=&amp;quot;0&amp;quot;"
    r" allowfullscreen&amp;gt;&amp;lt;/iframe&amp;gt;"
)


def inline_rrd_iframes(html_path: Path) -> None:
    """Post-process a saved HTML report for static hosting.

    Scans the HTML file for rerun viewer iframes (those pointing at
    ``/rrd_static/``), copies the referenced ``.rrd`` files from the
    local cache, writes a CDN viewer HTML page alongside each one, and
    rewrites the iframe ``src`` to a relative URL.  The result works on
    any static host (RTD, GitHub Pages, ``file://``) without a Panel
    server.

    Called automatically by ``BenchReport.save()``.
    """
    html = html_path.read_text(encoding="utf-8")
    cache_root = _RRD_CACHE_DIR.resolve()
    report_dir = html_path.parent
    rrd_dir = report_dir / "_rrd"

    changed = False

    def _replace(m: re.Match) -> str:
        nonlocal changed
        version, rrd_rel, width, height = m.group(1), m.group(2), m.group(3), m.group(4)
        rrd_path = cache_root / rrd_rel
        if not rrd_path.is_file():
            logging.warning("inline_rrd_iframes: %s not found, skipping", rrd_path)
            return m.group(0)

        viewer_name, rrd_name = _write_rrd_sidecar(rrd_path, version, rrd_dir)

        # Rewrite the iframe src to the local viewer + rrd.
        # Keep the same double encoding (&amp;lt;) as Panel's save uses for
        # all HTML content — Bokeh JS decodes two levels when rendering.
        relative_url = f"_rrd/{viewer_name}?url={rrd_name}"
        changed = True
        return (
            f"&amp;lt;iframe src=&amp;quot;{relative_url}&amp;quot;"
            f" width=&amp;quot;{width}&amp;quot;"
            f" height=&amp;quot;{height}&amp;quot;"
            f" frameborder=&amp;quot;0&amp;quot;"
            f" allowfullscreen&amp;gt;&amp;lt;/iframe&amp;gt;"
        )

    new_html = _RRD_IFRAME_RE.sub(_replace, html)
    if changed:
        html_path.write_text(new_html, encoding="utf-8")
    elif "/rrd_static/" in html:
        logging.warning(
            "inline_rrd_iframes: %s contains /rrd_static/ references but the iframe "
            "regex matched nothing — Bokeh's HTML encoding may have changed",
            html_path,
        )
