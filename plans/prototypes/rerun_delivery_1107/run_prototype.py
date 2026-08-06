"""Driver for the #1107 delivery prototype: build, measure, verify.

1. Runs the #1112 reference sweep shape (ControlSystemSweep, damping_ratio x omega_n,
   15 samples, one .rrd per sample) to get representative recordings.
2. Builds a representative blueprint (.rbl) — one time-series view over /response
   (blueprint *strategy* is #1106/#1113's problem; this just proves the pipe).
3. Calls ``save_rerun_native()`` -> report.html (offline single-file),
   report.rrd (bare merged recording), report_cdn.html (today's pinned-CDN wrapper).
4. Verifies the version stamped in the HTML matches the .rrd RRF2 header.
5. Best-effort time-to-first-render via headless Chrome:
   - report.html from file:// with DNS blackholed (proves offline);
   - report_cdn.html over a throwaway localhost HTTP server with network up.
   Skips gracefully when Chrome is unavailable.

Run:
    pixi run python plans/prototypes/rerun_delivery_1107/run_prototype.py
"""

from __future__ import annotations

import functools
import http.server
import re
import shutil
import subprocess
import sys
import threading
import time
from pathlib import Path

PROTO_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(PROTO_DIR))

from save_rerun_native import (
    fetch_sdk_viewer_assets,
    read_rrd_writer_version,
    save_rerun_native,
)

REPORT_DIR = PROTO_DIR / "out"


def run_reference_sweep() -> tuple[list[Path], float]:
    """Run the #1112 reference sweep and return the per-sample .rrd paths."""
    import bencher as bn
    from bencher.example.example_rerun_over_time import ControlSystemSweep

    t0 = time.perf_counter()
    bench = ControlSystemSweep().to_bench(bn.BenchRunCfg())
    res = bench.plot_sweep(
        input_vars=["damping_ratio", "omega_n"],
        result_vars=["out_overshoot", "out_settling_time", "out_rerun"],
        title="rerun delivery prototype (#1107)",
        plot_callbacks=[],  # no report panes needed; we only want the recordings
    )
    sweep_s = time.perf_counter() - t0
    paths = [Path(p) for p in res.ds["out_rerun"].values.flatten().tolist() if p]
    return paths, sweep_s


def build_blueprint(out_path: Path) -> Path | None:
    """Save a representative blueprint for the control-system recordings."""
    try:
        import rerun.blueprint as rrb

        bp = rrb.Blueprint(
            rrb.TimeSeriesView(origin="/response", name="step response"),
            collapse_panels=True,
        )
        # Must match the application id bencher records under (utils_rerun.py: rr.init("bencher")).
        bp.save("bencher", str(out_path))
        return out_path
    # Blueprint is a nice-to-have for the prototype; any SDK failure (pyo3
    # exceptions don't map to specific Python types) degrades to data-only.
    except Exception as e:  # noqa: BLE001  # pylint: disable=broad-except
        print(f"blueprint save skipped: {e}")
        return None


# --- best-effort headless-Chrome time-to-first-render ---


def _find_chrome() -> str | None:
    for name in ("google-chrome", "chromium", "chromium-browser"):
        path = shutil.which(name)
        if path:
            return path
    return None


# Wrapper page for the TTFR probe.  headless Chrome's --dump-dom dumps at the
# top page's load event, which for a fully-inline report fires *before* the
# async viewer pipeline finishes.  The wrapper embeds the report in an iframe
# and holds its own load event open with a server-delayed <img>, then mirrors
# the report's #status stamp into its own DOM every 200 ms, so the dump taken
# at load time contains the final reading.
_PROBE_TEMPLATE = """\
<!doctype html><html><head><meta charset="utf-8"/><title>probe</title></head><body>
<iframe id="f" src="{target}" style="width:1280px;height:800px"></iframe>
<img src="/hang?s={hold_s}" style="display:none"/>
<div id="probe">PROBE:waiting</div>
<script>
setInterval(() => {{
  try {{
    const s = document.getElementById("f").contentDocument.getElementById("status");
    if (s) document.getElementById("probe").textContent = "PROBE:" + s.textContent;
  }} catch (e) {{ document.getElementById("probe").textContent = "PROBE:" + e.message; }}
}}, 200);
</script></body></html>
"""

_PROBE_HOLD_S = 35


def measure_ttfr(report_dir: Path, target: str, base_url: str, offline: bool, label: str) -> str:
    """Load *target* (relative to the local server) in headless Chrome via the
    probe wrapper; return the page-reported readiness time.

    'viewer ready in N ms' is stamped once the viewer has started and the
    recording has been delivered — a lower bound on time-to-first-render (a
    paint-based rAF stamp never fires in headless Chrome).  Needs GPU-backed
    headless: with --disable-gpu the viewer's shaders compile on SwiftShader
    and take minutes.  Offline runs blackhole every host except the local
    server, so any CDN dependence would fail loudly.
    """
    chrome = _find_chrome()
    if chrome is None:
        return "skipped (no Chrome/Chromium found)"
    probe_name = f"probe_{label}.html"
    (report_dir / probe_name).write_text(
        _PROBE_TEMPLATE.format(target=target, hold_s=_PROBE_HOLD_S), encoding="utf-8"
    )
    cmd = [chrome, "--headless=new", "--no-sandbox", "--timeout=120000", "--dump-dom"]
    if offline:
        # blackhole everything except the local server (MAP * also matches IP literals)
        cmd.append("--host-resolver-rules=MAP * ~NOTFOUND, EXCLUDE 127.0.0.1")
    cmd.append(f"{base_url}/{probe_name}")
    t0 = time.perf_counter()
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=180, check=False)
    except subprocess.TimeoutExpired:
        return "timed out after 180s"
    wall_s = time.perf_counter() - t0
    m = re.search(r"PROBE:viewer ready in (\d+) ms", proc.stdout)
    if m:
        return f"{int(m.group(1))} ms in-page ({wall_s:.1f}s Chrome wall) [{label}]"
    state = re.search(r"PROBE:([^<]{1,120})", proc.stdout)
    return f"NOT ready (wall {wall_s:.1f}s, {state.group(1) if state else 'no probe'}) [{label}]"


class _HangHandler(http.server.SimpleHTTPRequestHandler):
    """Static handler plus a /hang endpoint that delays its response.

    The delayed response holds the probe page's load event open so headless
    Chrome's --dump-dom snapshot is taken after the viewer had time to start.
    """

    def do_GET(self):
        if self.path.startswith("/hang"):
            time.sleep(_PROBE_HOLD_S)
            self.send_response(204)
            self.end_headers()
            return
        super().do_GET()

    def log_message(self, *args):  # quiet
        pass


def serve_dir(directory: Path, port: int = 8123) -> http.server.ThreadingHTTPServer:
    handler = functools.partial(_HangHandler, directory=str(directory))
    httpd = http.server.ThreadingHTTPServer(("127.0.0.1", port), handler)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    return httpd


def human(n: int) -> str:
    return f"{n:,} B ({n / 1e6:.2f} MB)"


def main() -> None:
    rrd_paths, sweep_s = run_reference_sweep()
    total_rrd = sum(p.stat().st_size for p in rrd_paths)
    print(f"\nsweep: {len(rrd_paths)} recordings, {human(total_rrd)} total, {sweep_s:.1f}s")

    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    blueprint = build_blueprint(REPORT_DIR / "blueprint.rbl")

    assets = fetch_sdk_viewer_assets()
    result = save_rerun_native(REPORT_DIR, rrd_paths, blueprint=blueprint, viewer_assets=assets)

    print("\n=== save_rerun_native outputs ===")
    for name, size in result.sizes_bytes.items():
        print(f"  {name:18s} {human(size)}")
    print("build times:", {k: f"{v:.3f}s" for k, v in result.build_times_s.items()})

    # version carry: header -> HTML meta tag round trip
    header_version = read_rrd_writer_version(result.report_rrd)
    html_text = result.report_html.read_text(encoding="utf-8")
    m = re.search(r'<meta name="rerun-sdk-version" content="([^"]+)"', html_text)
    stamped = m.group(1) if m else "MISSING"
    ok = "OK" if stamped == header_version else "MISMATCH"
    print(f"\nversion carry: RRF2 header={header_version}  html meta={stamped}  -> {ok}")
    for p in rrd_paths[:1]:
        print(f"  (per-sample rrd {p.name}: header says {read_rrd_writer_version(p)})")

    # offline proof: no external URLs in the offline HTML
    externals = re.findall(r"https?://[a-zA-Z0-9./_-]+", html_text)
    print(f"external URLs in report.html: {len(externals)} {externals[:3]}")

    print("\n=== time-to-viewer-ready (best effort, headless Chrome) ===")
    httpd = serve_dir(REPORT_DIR)
    base = f"http://127.0.0.1:{httpd.server_address[1]}"
    try:
        print(
            "report.html (DNS blackholed):     ",
            measure_ttfr(REPORT_DIR, "report.html", base, True, "offline"),
        )
        print(
            "report_cdn.html (network up, CDN):",
            measure_ttfr(REPORT_DIR, "report_cdn.html", base, False, "cdn"),
        )
    finally:
        httpd.shutdown()

    print("\ndone; outputs in", REPORT_DIR)


if __name__ == "__main__":
    main()
