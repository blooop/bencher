"""Prototype for #1107: ``save_rerun_native(report_dir)`` — both candidate on-disk forms.

Takes ONE merged ``.rrd`` (+ optional blueprint) and emits every delivery candidate
side by side so they can be measured against each other:

- ``report.html``      — fully offline single-file HTML: SDK-bundled viewer JS + wasm
                         (gzip+base64) + the recording (base64) inlined.  Zero network,
                         works from ``file://``.  Adapted from
                         ``plans/research/build_offline_rerun_html.py`` (branch
                         ``research/rerun-delivery-1107``).
- ``report.rrd``       — the bare merged recording for the desktop viewer
                         (``rerun report.rrd``).  Self-describing: the writer SDK
                         version is embedded in its RRF2 header.
- ``report_cdn.html``  — tiny wrapper using today's pinned-CDN viewer
                         (``@rerun-io/web-viewer`` from jsDelivr, exactly the template
                         ``bencher/utils_rrd.py`` uses), loading ``report.rrd`` as a
                         sidecar.  Needs the CDN *and* an HTTP origin at view time.

Version carry (#1107 question 4 made concrete): ``read_rrd_writer_version()`` parses
the RRF2 magic out of the saved ``.rrd`` and ``save_rerun_native`` stamps it into the
HTML as a ``<meta name="rerun-sdk-version">`` tag + visible footer — a saved report
carries its own required viewer version in-band, no sidecar metadata to lose.

This module deliberately does NOT modify any bencher module; it imports and wraps.

Usage (via the driver):
    pixi run python plans/prototypes/rerun_delivery_1107/run_prototype.py
"""

from __future__ import annotations

import base64
import gzip
import struct
import subprocess
import time
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path

ASSET_PORT = 9631

# --- 1. Version carry: read the writer SDK version back out of the .rrd header ---

_RRF2_MAGIC = b"RRF2"


def read_rrd_writer_version(rrd_path: Path) -> str:
    """Parse the writer SDK version out of a .rrd file's RRF2 header.

    Layout (verified against files written by rerun-sdk 0.35.0, and documented in
    the #1107 research dossier): 4-byte magic ``RRF2`` followed by a 4-byte crate
    version ``major, minor, patch, meta`` (one byte each, big-endian-ish order as
    written: 00 23 00 00 == 0.35.0).
    """
    header = rrd_path.read_bytes()[:8]
    if header[:4] != _RRF2_MAGIC:
        raise ValueError(f"{rrd_path} is not an RRF2 rerun recording (magic={header[:4]!r})")
    major, minor, patch, _meta = struct.unpack("BBBB", header[4:8])
    return f"{major}.{minor}.{patch}"


# --- 2. Merge many per-sample recordings into ONE .rrd (+ optional blueprint) ---


def merge_rrds(rrd_paths: list[Path], out_path: Path, blueprint: Path | None = None) -> Path:
    """Merge per-sample recordings (and optionally a blueprint) into one .rrd.

    Prefers the SDK CLI (``rerun rrd merge``); falls back to byte concatenation,
    which the rrd container format explicitly supports (a file is a sequence of
    streams).  The real merging strategy is #1113's problem — this just produces
    a representative single-file recording.
    """
    inputs = [str(p) for p in rrd_paths]
    if blueprint is not None:
        inputs.append(str(blueprint))
    out_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        subprocess.run(
            ["rerun", "rrd", "merge", *inputs, "-o", str(out_path)],
            check=True,
            capture_output=True,
            text=True,
        )
        return out_path
    except (FileNotFoundError, subprocess.CalledProcessError):
        # Concatenated rrd streams are a valid rrd file.
        with open(out_path, "wb") as f:
            f.writelines(
                Path(p).read_bytes() for p in rrd_paths + ([blueprint] if blueprint else [])
            )
        return out_path


# --- 3a. Offline single-file HTML (viewer + data inlined, zero network) ---

_OFFLINE_TEMPLATE = """\
<!doctype html>
<html><head><meta charset="utf-8"/>
<meta name="rerun-sdk-version" content="{version}"/>
<title>{title}</title>
<style>html,body{{margin:0;padding:0;width:100%;height:100%;overflow:hidden;background:#0d1011}}
canvas{{position:absolute;top:0;left:0;width:100%;height:calc(100% - 18px)}}
#foot{{position:absolute;bottom:0;left:0;right:0;height:18px;color:#888;background:#0d1011;
font:11px monospace;text-align:right;padding-right:6px}}</style>
</head><body>
<canvas id="cv"></canvas>
<div id="foot">rerun-sdk {version} (viewer + data self-contained) &mdash;
<span id="status">loading&hellip;</span></div>
<div id="err" style="color:red;font:12px monospace;white-space:pre-wrap;position:absolute;top:0"></div>
<script id="wasm-gz-b64" type="application/octet-stream">{wasm_gz_b64}</script>
<script id="rrd-b64" type="application/octet-stream">{rrd_b64}</script>
<script>
// file:// pages cannot use instantiateStreaming on opaque responses; force the
// ArrayBuffer path (same workaround as the SDK's own bundled index.html).
delete WebAssembly.instantiateStreaming;
</script>
<script>{re_viewer_js}</script>
<script>
const t0 = performance.now();
async function main() {{
  const b64ToBytes = (id) => {{
    const b64 = document.getElementById(id).textContent.trim();
    const bin = atob(b64);
    const out = new Uint8Array(bin.length);
    for (let i = 0; i < bin.length; i++) out[i] = bin.charCodeAt(i);
    return out;
  }};
  // 1. decompress the wasm and initialize wasm-bindgen from an in-memory Response
  const gz = b64ToBytes("wasm-gz-b64");
  const ds = new DecompressionStream("gzip");
  const stream = new Blob([gz]).stream().pipeThrough(ds);
  const wasmBuf = await new Response(stream).arrayBuffer();
  await wasm_bindgen(new Response(wasmBuf, {{headers: {{"Content-Type": "application/wasm"}}}}));
  // 2. start the viewer with no URL (nothing to fetch)
  const handle = new wasm_bindgen.WebHandle({{hide_welcome_screen: true, persist: false}});
  await handle.start(document.getElementById("cv"));
  // 3. push the inlined recording through a channel (no network)
  const rrd = b64ToBytes("rrd-b64");
  handle.open_channel("inline", "inline rrd");
  handle.send_rrd_to_channel("inline", rrd);
  handle.close_channel("inline");
  // 4. report readiness: viewer started + recording delivered.  A paint-based
  //    stamp (rAF) never fires in headless Chrome, so this measures
  //    time-to-data-delivered, a lower bound on time-to-first-render.
  setTimeout(() => {{
    const ms = Math.round(performance.now() - t0);
    document.getElementById("status").textContent = "viewer ready in " + ms + " ms";
    document.title = "READY " + ms + "ms";
  }}, 0);
}}
main().catch((e) => {{
  document.getElementById("err").textContent = e.message + "\\n" + (e.stack || "");
  document.title = "ERROR";
}});
</script>
</body></html>
"""


def fetch_sdk_viewer_assets(port: int = ASSET_PORT) -> tuple[str, bytes]:
    """Fetch re_viewer.js + re_viewer_bg.wasm from the SDK's own bundled asset server.

    ``rerun_bindings`` embeds the complete standalone web viewer; this guarantees
    the viewer version always matches the SDK that wrote the recording.
    """
    import rerun as rr

    rr.start_web_viewer_server(port=port)
    time.sleep(1.0)
    base = f"http://localhost:{port}"
    with urllib.request.urlopen(f"{base}/re_viewer.js") as r:
        js = r.read().decode("utf-8")
    with urllib.request.urlopen(f"{base}/re_viewer_bg.wasm") as r:
        wasm = r.read()
    return js, wasm


def build_offline_html(
    rrd_path: Path,
    out_path: Path,
    viewer_assets: tuple[str, bytes] | None = None,
    title: str = "bencher report (rerun-native, offline)",
) -> Path:
    """Emit a fully self-contained offline HTML for *rrd_path*.

    The viewer version stamped into the page is read from the recording's own
    RRF2 header — not from the installed package — so the page describes the
    data it actually carries.
    """
    js, wasm = viewer_assets if viewer_assets is not None else fetch_sdk_viewer_assets()
    version = read_rrd_writer_version(rrd_path)
    wasm_gz_b64 = base64.b64encode(gzip.compress(wasm, 6)).decode("ascii")
    rrd_b64 = base64.b64encode(rrd_path.read_bytes()).decode("ascii")
    html = _OFFLINE_TEMPLATE.format(
        version=version,
        title=title,
        wasm_gz_b64=wasm_gz_b64,
        rrd_b64=rrd_b64,
        re_viewer_js=js,
    )
    out_path.write_text(html, encoding="utf-8")
    return out_path


# --- 3b. CDN wrapper (today's pinned-CDN iframe path, for comparison) ---

_CDN_WRAPPER_TEMPLATE = """\
<!DOCTYPE html>
<html><head><meta charset="utf-8"/>
<meta name="rerun-sdk-version" content="{version}"/>
<title>bencher report (rerun, pinned CDN)</title>
<style>html,body{{margin:0;padding:0;width:100%;height:100%;overflow:hidden}}</style>
</head><body>
<div id="c" style="width:100vw;height:calc(100vh - 18px)"></div>
<div style="height:18px;color:#888;font:11px monospace;text-align:right;padding-right:6px">
rerun-sdk {version} (viewer from jsDelivr CDN, data sidecar: {rrd_name}) &mdash;
<span id="status">loading&hellip;</span></div>
<div id="e" style="color:red;padding:20px;font-family:monospace;white-space:pre-wrap"></div>
<script type="module">
const t0 = performance.now();
try {{
  const {{WebViewer}} = await import(
    "https://cdn.jsdelivr.net/npm/@rerun-io/web-viewer@{version}/+esm"
  );
  const v = new WebViewer();
  await v.start(new URL("{rrd_name}", location.href).href,
                document.getElementById("c"),
                {{hide_welcome_screen:true,width:"100%",height:"100%"}});
  setTimeout(() => {{
    const ms = Math.round(performance.now() - t0);
    document.getElementById("status").textContent = "viewer ready in " + ms + " ms";
    document.title = "READY " + ms + "ms";
  }}, 0);
}} catch(e) {{
  document.getElementById("e").textContent = e.message + "\\n" + e.stack;
  document.title = "ERROR";
}}
</script></body></html>
"""


def build_cdn_wrapper_html(rrd_path: Path, out_path: Path) -> Path:
    """Emit today's pinned-CDN viewer page pointing at *rrd_path* as a sidecar.

    Same viewer bootstrap as ``bencher/utils_rrd.py:_CDN_VIEWER_TEMPLATE`` (jsDelivr
    ``@rerun-io/web-viewer@<version>/+esm``), with the version pinned from the
    recording's RRF2 header instead of a query parameter.  Requires network access
    to jsDelivr AND an HTTP origin (the CDN module cannot fetch a file:// sidecar).
    """
    version = read_rrd_writer_version(rrd_path)
    html = _CDN_WRAPPER_TEMPLATE.format(version=version, rrd_name=rrd_path.name)
    out_path.write_text(html, encoding="utf-8")
    return out_path


# --- 4. The prototype save target ---


@dataclass
class SaveResult:
    """Paths + measurements for one save_rerun_native() run."""

    report_html: Path
    report_rrd: Path
    report_cdn_html: Path
    writer_version: str
    build_times_s: dict[str, float] = field(default_factory=dict)
    sizes_bytes: dict[str, int] = field(default_factory=dict)


def save_rerun_native(
    report_dir: Path,
    rrd_paths: list[Path],
    blueprint: Path | None = None,
    viewer_assets: tuple[str, bytes] | None = None,
) -> SaveResult:
    """Save a rerun-native report: merged .rrd + both candidate HTML forms.

    Parameters
    ----------
    report_dir: destination directory (created if needed).
    rrd_paths: the per-sample recordings to merge (merge strategy itself is #1113).
    blueprint: optional .rbl to merge in (blueprint compat is #1106's problem).
    viewer_assets: pre-fetched (js, wasm) to avoid re-starting the asset server.
    """
    report_dir = Path(report_dir)
    report_dir.mkdir(parents=True, exist_ok=True)
    times: dict[str, float] = {}

    t = time.perf_counter()
    report_rrd = merge_rrds(rrd_paths, report_dir / "report.rrd", blueprint=blueprint)
    times["merge_rrd"] = time.perf_counter() - t

    version = read_rrd_writer_version(report_rrd)

    t = time.perf_counter()
    if viewer_assets is None:
        viewer_assets = fetch_sdk_viewer_assets()
    times["fetch_viewer_assets"] = time.perf_counter() - t

    t = time.perf_counter()
    report_html = build_offline_html(report_rrd, report_dir / "report.html", viewer_assets)
    times["build_offline_html"] = time.perf_counter() - t

    t = time.perf_counter()
    report_cdn = build_cdn_wrapper_html(report_rrd, report_dir / "report_cdn.html")
    times["build_cdn_html"] = time.perf_counter() - t

    return SaveResult(
        report_html=report_html,
        report_rrd=report_rrd,
        report_cdn_html=report_cdn,
        writer_version=version,
        build_times_s=times,
        sizes_bytes={
            "report.html": report_html.stat().st_size,
            "report.rrd": report_rrd.stat().st_size,
            "report_cdn.html": report_cdn.stat().st_size,
        },
    )
