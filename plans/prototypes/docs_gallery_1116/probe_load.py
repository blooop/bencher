"""Prototype for #1116: does each candidate gallery page actually load, offline?

Serves ``out/site`` over localhost and loads each candidate page in headless
Chrome with every non-local hostname DNS-blackholed (the 1107 technique), so
any CDN dependence fails loudly. The CDN page (C) is probed both offline
(expected: FAIL — that is its rot/network coupling) and with network up.

The probe wrapper holds its own load event open with a server-delayed <img>
and mirrors the embedded report's ``#status`` stamp into its DOM every 200 ms,
so ``--dump-dom`` (taken at load) contains the final reading.

Run (after build_pages.py):
    pixi run python plans/prototypes/docs_gallery_1116/probe_load.py
"""

from __future__ import annotations

import functools
import http.server
import json
import re
import shutil
import subprocess
import threading
import time
from pathlib import Path

PROTO_DIR = Path(__file__).resolve().parent
SITE_DIR = PROTO_DIR / "out" / "site"

_PROBE_HOLD_S = 35

# The candidate pages embed the report one level down (docs page -> iframe ->
# [report page or viewer page]); for A2 the report is srcdoc-inlined. The probe
# walks same-origin frames recursively looking for a #status element.
_PROBE_TEMPLATE = """\
<!doctype html><html><head><meta charset="utf-8"/><title>probe</title></head><body>
<iframe id="f" src="{target}" style="width:1280px;height:900px"></iframe>
<img src="/hang?s={hold_s}" style="display:none"/>
<div id="probe">PROBE:waiting</div>
<script>
function findStatus(win) {{
  try {{
    const s = win.document && win.document.getElementById("status");
    if (s) return s;
    for (let i = 0; i < win.frames.length; i++) {{
      const r = findStatus(win.frames[i]);
      if (r) return r;
    }}
  }} catch (e) {{}}
  return null;
}}
setInterval(() => {{
  const s = findStatus(document.getElementById("f").contentWindow);
  if (s) document.getElementById("probe").textContent = "PROBE:" + s.textContent;
  // also surface viewer errors
  try {{
    const w = document.getElementById("f").contentWindow;
    function findErr(win) {{
      try {{
        const e = win.document && win.document.getElementById("e") || win.document.getElementById("err");
        if (e && e.textContent.trim()) return e;
        for (let i = 0; i < win.frames.length; i++) {{ const r = findErr(win.frames[i]); if (r) return r; }}
      }} catch (x) {{}}
      return null;
    }}
    const err = findErr(w);
    if (err) document.getElementById("probe").textContent = "PROBE:ERROR " + err.textContent.slice(0, 160);
  }} catch (e) {{}}
}}, 200);
</script></body></html>
"""


class _HangHandler(http.server.SimpleHTTPRequestHandler):
    def do_GET(self):
        if self.path.startswith("/hang"):
            time.sleep(_PROBE_HOLD_S)
            self.send_response(204)
            self.end_headers()
            return
        super().do_GET()

    def log_message(self, *args):
        pass


def serve_site(port: int = 8124) -> http.server.ThreadingHTTPServer:
    handler = functools.partial(_HangHandler, directory=str(SITE_DIR))
    httpd = http.server.ThreadingHTTPServer(("127.0.0.1", port), handler)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    return httpd


def find_chrome() -> str | None:
    for name in ("google-chrome", "chromium", "chromium-browser"):
        path = shutil.which(name)
        if path:
            return path
    return None


def probe(chrome: str, base_url: str, target: str, offline: bool, label: str) -> dict:
    probe_name = f"probe_{label}.html"
    (SITE_DIR / probe_name).write_text(
        _PROBE_TEMPLATE.format(target=target, hold_s=_PROBE_HOLD_S), encoding="utf-8"
    )
    cmd = [chrome, "--headless=new", "--no-sandbox", "--timeout=100000", "--dump-dom"]
    if offline:
        cmd.append("--host-resolver-rules=MAP * ~NOTFOUND, EXCLUDE 127.0.0.1")
    cmd.append(f"{base_url}/{probe_name}")
    t0 = time.perf_counter()
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=150, check=False)
    except subprocess.TimeoutExpired:
        return {"label": label, "result": "timed out after 150s"}
    wall = time.perf_counter() - t0
    m = re.search(r"PROBE:viewer ready in (\d+) ms", proc.stdout)
    if m:
        return {
            "label": label,
            "result": "READY",
            "in_page_ms": int(m.group(1)),
            "chrome_wall_s": round(wall, 1),
        }
    state = re.search(r"PROBE:([^<]{1,200})", proc.stdout)
    return {
        "label": label,
        "result": "NOT ready",
        "state": state.group(1).strip() if state else "no probe output",
        "chrome_wall_s": round(wall, 1),
    }


def main() -> None:
    chrome = find_chrome()
    if chrome is None:
        raise SystemExit("no Chrome/Chromium found")
    httpd = serve_site()
    base = f"http://127.0.0.1:{httpd.server_address[1]}"
    results = []
    try:
        cases = [
            ("page_a1_iframe_asset.html", True, "a1_offline"),
            ("page_a2_srcdoc.html", True, "a2_offline"),
            ("page_s_selfhosted.html", True, "s_offline"),
            ("page_c_cdn.html", True, "c_offline_expected_fail"),
            ("page_c_cdn.html", False, "c_network_up"),
        ]
        for target, offline, label in cases:
            r = probe(chrome, base, target, offline, label)
            results.append(r)
            print(json.dumps(r))
    finally:
        httpd.shutdown()
    (PROTO_DIR / "out" / "measurements_probe.json").write_text(json.dumps(results, indent=2))


if __name__ == "__main__":
    main()
