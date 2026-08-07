"""Prototype for #1116 candidate B: screenshot the offline rerun report headlessly.

Measures, per browser config:
- t_ready:   time until the report page stamps READY (viewer started + rrd delivered)
- t_content: time until a screenshot actually SHOWS the rendered report (first
             screenshot whose non-background pixel fraction crosses a threshold)
- renderer:  the WebGL renderer string actually in use (so "GPU" vs SwiftShader
             is measured, not assumed)
- PNG size of the final screenshot

Configs:
- gpu:         system google-chrome, headless, no --disable-gpu
- swiftshader: system google-chrome, headless, --disable-gpu  (the CI/RTD condition:
               GitHub-hosted standard runners and RTD builders have no GPU)

Overall per-config budget: 300 s; a config that produces no content by then is
recorded as "exceeds 300 s".

Also emits ``out/site/page_b_screenshot.html`` — the candidate-B gallery page
(static PNG + download links) — and measures it.

Run (docs env has playwright + Pillow):
    pixi run -e docs python plans/prototypes/docs_gallery_1116/screenshot_bench.py
"""

from __future__ import annotations

import io
import json
import time
from pathlib import Path

from PIL import Image

PROTO_DIR = Path(__file__).resolve().parent
SITE_DIR = PROTO_DIR / "out" / "site"
REPORT_HTML = SITE_DIR / "_reports" / "example_rerun_reference" / "report.html"

BUDGET_S = 300
CONTENT_THRESHOLD = 0.02  # fraction of pixels brighter than the viewer's dark bg
BRIGHTNESS_CUTOFF = 60


def bright_fraction(png_bytes: bytes) -> float:
    img = Image.open(io.BytesIO(png_bytes)).convert("L").resize((320, 200))
    hist = img.histogram()
    total = sum(hist)
    bright = sum(hist[BRIGHTNESS_CUTOFF:])
    return bright / total if total else 0.0


def renderer_string(page) -> str:
    return page.evaluate(
        """() => {
          try {
            const c = document.createElement('canvas');
            const gl = c.getContext('webgl2') || c.getContext('webgl');
            if (!gl) return 'no webgl context';
            const ext = gl.getExtension('WEBGL_debug_renderer_info');
            return ext ? gl.getParameter(ext.UNMASKED_RENDERER_WEBGL)
                       : gl.getParameter(gl.RENDERER);
          } catch (e) { return 'error: ' + e.message; }
        }"""
    )


def bench_config(label: str, launch_kwargs: dict, out_png: Path) -> dict:
    from playwright.sync_api import sync_playwright

    result: dict = {"label": label}
    t0 = time.perf_counter()
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, **launch_kwargs)
        page = browser.new_page(viewport={"width": 1280, "height": 800})
        try:
            page.goto(REPORT_HTML.resolve().as_uri(), timeout=60000)
            result["renderer"] = renderer_string(page)
            # phase 1: viewer started + rrd delivered
            try:
                page.wait_for_function(
                    "document.title.startsWith('READY')", timeout=BUDGET_S * 1000
                )
                result["t_ready_s"] = round(time.perf_counter() - t0, 1)
            except Exception:  # noqa: BLE001  # pylint: disable=broad-except
                result["t_ready_s"] = f"exceeds {BUDGET_S}s"
                result["t_content_s"] = f"exceeds {BUDGET_S}s"
                return result
            # phase 2: poll screenshots until the report is actually visible
            last_png = b""
            while time.perf_counter() - t0 < BUDGET_S:
                last_png = page.screenshot()
                frac = bright_fraction(last_png)
                if frac >= CONTENT_THRESHOLD:
                    result["t_content_s"] = round(time.perf_counter() - t0, 1)
                    result["bright_fraction"] = round(frac, 4)
                    break
                time.sleep(1.0)
            else:
                result["t_content_s"] = f"exceeds {BUDGET_S}s"
                result["bright_fraction"] = round(bright_fraction(last_png), 4)
            if last_png:
                out_png.parent.mkdir(parents=True, exist_ok=True)
                out_png.write_bytes(last_png)
                result["png_bytes"] = len(last_png)
        finally:
            browser.close()
    result["total_wall_s"] = round(time.perf_counter() - t0, 1)
    return result


_B_PAGE = """\
<!doctype html>
<html><head><meta charset="utf-8"/><title>Example Rerun Reference (B: screenshot + downloads)</title>
<style>body{{font:15px sans-serif;max-width:960px;margin:2em auto;padding:0 1em}}
img{{max-width:100%;border:1px solid #ccc}}</style></head><body>
<h1>Example Rerun Reference (B: screenshot + download links)</h1>
<details open><summary>Source Code</summary><pre>def example_rerun_reference(run_cfg): ...</pre></details>
<h2>Results:</h2>
<a href="{href}"><img src="_thumbs/example_rerun_reference.png" alt="rerun report screenshot"></a>
<p>Static screenshot. Interact with the real report:
<a href="_reports/example_rerun_reference/report.html" download>Download report.html</a> &middot;
<a href="_reports/example_rerun_reference/report.rrd" download>Download report.rrd</a></p>
</body></html>
"""


def main() -> None:
    if not REPORT_HTML.exists():
        raise SystemExit("run build_pages.py first")
    results = []
    chrome = "/usr/bin/google-chrome"
    configs = [
        ("gpu", {"executable_path": chrome, "args": []}),
        ("swiftshader", {"executable_path": chrome, "args": ["--disable-gpu"]}),
    ]
    for label, kwargs in configs:
        png = PROTO_DIR / "out" / f"screenshot_{label}.png"
        print(f"--- config {label} ---")
        r = bench_config(label, kwargs, png)
        print(json.dumps(r))
        results.append(r)

    # candidate-B gallery page, using the best available screenshot
    best = next((r for r in results if isinstance(r.get("t_content_s"), float)), None)
    if best:
        src = PROTO_DIR / "out" / f"screenshot_{best['label']}.png"
        thumb = SITE_DIR / "_thumbs" / "example_rerun_reference.png"
        thumb.parent.mkdir(parents=True, exist_ok=True)
        thumb.write_bytes(src.read_bytes())
        page_b = SITE_DIR / "page_b_screenshot.html"
        page_b.write_text(
            _B_PAGE.format(href="_reports/example_rerun_reference/report.html"),
            encoding="utf-8",
        )
        results.append(
            {
                "label": "page_b_payload",
                "page_bytes": page_b.stat().st_size,
                "png_bytes": thumb.stat().st_size,
                "with_downloads_bytes": page_b.stat().st_size
                + thumb.stat().st_size
                + (SITE_DIR / "_reports/example_rerun_reference/report.html").stat().st_size
                + (SITE_DIR / "_reports/example_rerun_reference/report.rrd").stat().st_size,
            }
        )
        print(json.dumps(results[-1]))

    (PROTO_DIR / "out" / "measurements_screenshot.json").write_text(json.dumps(results, indent=2))


if __name__ == "__main__":
    main()
