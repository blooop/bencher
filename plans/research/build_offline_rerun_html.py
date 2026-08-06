"""Prototype for wayfinder #1107: build a fully offline, single-file HTML rerun viewer.

Produces ONE self-contained HTML file that opens a .rrd recording with ZERO network
access (works from file://). Ingredients, all sourced from the installed rerun-sdk:

1. ``re_viewer.js``   — wasm-bindgen "no-modules" glue (~220 KB), fetched once from the
   SDK's own bundled asset server (``rr.start_web_viewer_server()``, which embeds the
   full standalone web-viewer app inside ``rerun_bindings``).
2. ``re_viewer_bg.wasm`` — the viewer itself (~40 MB raw), inlined as gzip+base64
   (~15 MB gz -> ~20 MB b64) and decompressed in-browser via DecompressionStream
   (the same trick ``rerun_notebook``'s RERUN_NOTEBOOK_ASSET=inline mode uses).
3. The ``.rrd`` data, inlined as base64 and pushed through
   ``WebHandle.open_channel`` / ``send_rrd_to_channel`` — no fetch of the recording.

Usage:
    pixi run python plans/research/build_offline_rerun_html.py INPUT.rrd OUTPUT.html

Throwaway quality — no error handling polish; exists to measure feasibility and size.
"""

from __future__ import annotations

import base64
import gzip
import sys
import time
import urllib.request
from pathlib import Path

ASSET_PORT = 9631

HTML_TEMPLATE = """\
<!doctype html>
<html><head><meta charset="utf-8"/>
<title>offline rerun viewer prototype (#1107)</title>
<style>html,body{{margin:0;padding:0;width:100%;height:100%;overflow:hidden;background:#0d1011}}
canvas{{position:absolute;top:0;left:0;width:100%;height:100%}}</style>
</head><body>
<canvas id="cv"></canvas>
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
}}
main().catch((e) => {{
  document.getElementById("err").textContent = e.message + "\\n" + (e.stack || "");
}});
</script>
</body></html>
"""


def fetch_sdk_viewer_assets() -> tuple[str, bytes]:
    """Fetch re_viewer.js + re_viewer_bg.wasm from the SDK's bundled asset server."""
    import rerun as rr

    rr.start_web_viewer_server(port=ASSET_PORT)
    time.sleep(1.0)
    base = f"http://localhost:{ASSET_PORT}"
    with urllib.request.urlopen(f"{base}/re_viewer.js") as r:
        js = r.read().decode("utf-8")
    with urllib.request.urlopen(f"{base}/re_viewer_bg.wasm") as r:
        wasm = r.read()
    return js, wasm


def build(rrd_path: Path, out_path: Path) -> None:
    js, wasm = fetch_sdk_viewer_assets()
    wasm_gz_b64 = base64.b64encode(gzip.compress(wasm, 6)).decode("ascii")
    rrd_b64 = base64.b64encode(rrd_path.read_bytes()).decode("ascii")
    html = HTML_TEMPLATE.format(wasm_gz_b64=wasm_gz_b64, rrd_b64=rrd_b64, re_viewer_js=js)
    out_path.write_text(html, encoding="utf-8")
    print(f"rrd:  {rrd_path.stat().st_size:>12,} bytes  {rrd_path}")
    print(f"wasm: {len(wasm):>12,} bytes raw, {len(wasm_gz_b64):,} as gz+b64")
    print(f"html: {out_path.stat().st_size:>12,} bytes  {out_path}")


if __name__ == "__main__":
    build(Path(sys.argv[1]), Path(sys.argv[2]))
