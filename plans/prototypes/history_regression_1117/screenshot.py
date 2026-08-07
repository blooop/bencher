"""Headless-Chrome screenshots of the #1117 prototype recordings.

Builds a fully offline single-file HTML viewer page per recording (viewer
JS+wasm from the SDK's own bundled asset server + the .rrd inlined — the
technique from ``plans/prototypes/rerun_delivery_1107/save_rerun_native.py``
on branch ``prototype/rerun-delivery-1107``), serves it locally, and takes a
screenshot with headless Chrome.  The screenshot fires at the top page's load
event, which a server-delayed <img> holds open long enough for the wasm
viewer (SwiftShader) to render.

Run (after history_regression.py):
    pixi run python plans/prototypes/history_regression_1117/screenshot.py

Outputs:
    out/screens/s1_blueprint_layout.png     data + pinned blueprint
    out/screens/s2_default_no_blueprint.png same data, viewer's default selection
"""

from __future__ import annotations

import base64
import functools
import gzip
import http.server
import shutil
import struct
import subprocess
import threading
import time
import urllib.request
from pathlib import Path

PROTO_DIR = Path(__file__).resolve().parent
OUT_DIR = PROTO_DIR / "out"
SCREEN_DIR = OUT_DIR / "screens"

ASSET_PORT = 9632
HOLD_S = 20  # how long the /hang endpoint holds the load event open

_OFFLINE_TEMPLATE = """\
<!doctype html>
<html><head><meta charset="utf-8"/>
<title>{title}</title>
<style>html,body{{margin:0;padding:0;width:100%;height:100%;overflow:hidden;background:#0d1011}}
canvas{{position:absolute;top:0;left:0;width:100%;height:100%}}</style>
</head><body>
<canvas id="cv"></canvas>
<div id="err" style="color:red;font:12px monospace;white-space:pre-wrap;position:absolute;top:0"></div>
<script id="wasm-gz-b64" type="application/octet-stream">{wasm_gz_b64}</script>
<script id="rrd-b64" type="application/octet-stream">{rrd_b64}</script>
<script>delete WebAssembly.instantiateStreaming;</script>
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
  const gz = b64ToBytes("wasm-gz-b64");
  const ds = new DecompressionStream("gzip");
  const stream = new Blob([gz]).stream().pipeThrough(ds);
  const wasmBuf = await new Response(stream).arrayBuffer();
  await wasm_bindgen(new Response(wasmBuf, {{headers: {{"Content-Type": "application/wasm"}}}}));
  const handle = new wasm_bindgen.WebHandle({{hide_welcome_screen: true, persist: false}});
  await handle.start(document.getElementById("cv"));
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

# Top page: iframe with the report + a server-delayed <img> that holds the load
# event open, so `--screenshot` (taken at load) captures a rendered viewer.
_SHOT_TEMPLATE = """\
<!doctype html><html><head><meta charset="utf-8"/><title>shot</title>
<style>html,body{{margin:0;padding:0}}iframe{{border:0;display:block}}</style></head><body>
<iframe src="{target}" width="{w}" height="{h}"></iframe>
<img src="/hang?s={hold}" style="display:none"/>
</body></html>
"""


def read_rrd_writer_version(rrd_path: Path) -> str:
    header = rrd_path.read_bytes()[:8]
    if header[:4] != b"RRF2":
        raise ValueError(f"{rrd_path} is not an RRF2 rerun recording")
    major, minor, patch, _ = struct.unpack("BBBB", header[4:8])
    return f"{major}.{minor}.{patch}"


def fetch_sdk_viewer_assets(port: int = ASSET_PORT) -> tuple[str, bytes]:
    import rerun as rr

    rr.start_web_viewer_server(port=port)
    time.sleep(1.0)
    base = f"http://localhost:{port}"
    with urllib.request.urlopen(f"{base}/re_viewer.js") as r:
        js = r.read().decode("utf-8")
    with urllib.request.urlopen(f"{base}/re_viewer_bg.wasm") as r:
        wasm = r.read()
    return js, wasm


def build_offline_html(rrd_path: Path, out_path: Path, assets: tuple[str, bytes]) -> Path:
    js, wasm = assets
    html = _OFFLINE_TEMPLATE.format(
        title=rrd_path.stem,
        wasm_gz_b64=base64.b64encode(gzip.compress(wasm, 6)).decode("ascii"),
        rrd_b64=base64.b64encode(rrd_path.read_bytes()).decode("ascii"),
        re_viewer_js=js,
    )
    out_path.write_text(html, encoding="utf-8")
    return out_path


class _HangHandler(http.server.SimpleHTTPRequestHandler):
    def do_GET(self):
        if self.path.startswith("/hang"):
            time.sleep(HOLD_S)
            self.send_response(204)
            self.end_headers()
            return
        super().do_GET()

    def log_message(self, *args):
        pass


def _find_chrome() -> str | None:
    for name in ("google-chrome", "chromium", "chromium-browser"):
        path = shutil.which(name)
        if path:
            return path
    return None


def screenshot(base_url: str, report_name: str, png: Path, w: int = 1920, h: int = 1080) -> bool:
    chrome = _find_chrome()
    if chrome is None:
        print("no Chrome/Chromium found; skipping screenshots")
        return False
    shot_name = f"shot_{png.stem}.html"
    (OUT_DIR / shot_name).write_text(
        _SHOT_TEMPLATE.format(target=report_name, w=w, h=h, hold=HOLD_S), encoding="utf-8"
    )
    cmd = [
        chrome,
        "--headless=new",
        "--no-sandbox",
        f"--window-size={w},{h}",
        "--hide-scrollbars",
        f"--screenshot={png}",
        f"{base_url}/{shot_name}",
    ]
    t0 = time.perf_counter()
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=180, check=False)
    ok = png.exists() and png.stat().st_size > 20_000
    print(f"  {png.name}: {'OK' if ok else 'FAILED'} ({time.perf_counter() - t0:.1f}s)")
    if not ok:
        print(proc.stderr[-800:])
    return ok


def main() -> None:
    SCREEN_DIR.mkdir(parents=True, exist_ok=True)
    assets = fetch_sdk_viewer_assets()
    for rrd in (
        "history_regression.rrd",
        "history_regression_noblueprint.rrd",
        "history_regression_sweepmode.rrd",
    ):
        p = OUT_DIR / rrd
        print(f"{rrd}: writer sdk {read_rrd_writer_version(p)}")
        build_offline_html(p, OUT_DIR / (p.stem + ".html"), assets)

    handler = functools.partial(_HangHandler, directory=str(OUT_DIR))
    httpd = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    base = f"http://127.0.0.1:{httpd.server_address[1]}"
    try:
        screenshot(base, "history_regression.html", SCREEN_DIR / "s1_blueprint_layout.png")
        screenshot(
            base,
            "history_regression_noblueprint.html",
            SCREEN_DIR / "s2_default_no_blueprint.png",
        )
        screenshot(
            base,
            "history_regression_sweepmode.html",
            SCREEN_DIR / "s3_sweep_timeline_mode.png",
        )
    finally:
        httpd.shutdown()
    print("screenshots in", SCREEN_DIR)


if __name__ == "__main__":
    main()
