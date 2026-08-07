"""Prototype for #1116: build every candidate docs-gallery page form for a
rerun-native report and measure its size.

Candidates (all built from the same #1112-shaped reference report):

- A1  ``page_a1_iframe_asset.html``  — docs-style page, ``<iframe src=...>`` a
       shipped copy of the 17.7MB+ offline ``report.html`` static asset.
       Per-example payload = the full offline report.
- A2  ``page_a2_srcdoc.html``        — the offline report escaped into
       ``<iframe srcdoc="...">`` so the page itself is self-contained.
       Measures the escaping inflation.
- C   ``page_c_cdn.html``            — docs-style page iframing the ~1.4KB
       pinned-CDN wrapper + ``report.rrd`` sidecar (today's saved-report
       exception form; needs jsDelivr at view time).
- S   ``page_s_selfhosted.html``     — docs-style page iframing a viewer that
       loads ``re_viewer.js`` + ``re_viewer_bg.wasm`` from a SHARED
       ``_static/rerun_viewer/`` directory (paid once per docs site, not per
       example) and fetches ``report.rrd`` as a relative-URL sidecar.
       No CDN, no per-page viewer copy. This is the "self-hosted CDN" form.

Output tree (out/site/) mimics the docs layout: shared assets under
``_static/``, per-example assets under ``_reports/``.

Run:
    pixi run python plans/prototypes/docs_gallery_1116/build_pages.py
    pixi run python plans/prototypes/docs_gallery_1116/build_pages.py --skip-sweep
"""

from __future__ import annotations

import argparse
import gzip
import html as html_lib
import json
import sys
import time
from pathlib import Path

PROTO_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(PROTO_DIR))

from save_rerun_native import (  # noqa: E402
    build_cdn_wrapper_html,
    build_offline_html,
    fetch_sdk_viewer_assets,
    merge_rrds,
    read_rrd_writer_version,
)

OUT_DIR = PROTO_DIR / "out"
SITE_DIR = OUT_DIR / "site"
RRD_CACHE = OUT_DIR / "rrds"

# Number of rerun examples registered in generate_meta_rerun.py today
# (capture_window, regression, sweep, composable_{right,down,sequence,overlay}, summary).
N_RERUN_EXAMPLES_TODAY = 8


def run_reference_sweep() -> tuple[list[Path], float]:
    """Run the #1112 reference sweep shape and return per-sample .rrd paths."""
    import bencher as bn
    from bencher.example.example_rerun_over_time import ControlSystemSweep

    t0 = time.perf_counter()
    bench = ControlSystemSweep().to_bench(bn.BenchRunCfg())
    res = bench.plot_sweep(
        input_vars=["damping_ratio", "omega_n"],
        result_vars=["out_overshoot", "out_settling_time", "out_rerun"],
        title="rerun docs-gallery prototype (#1116)",
        plot_callbacks=[],
    )
    sweep_s = time.perf_counter() - t0
    paths = [Path(p) for p in res.ds["out_rerun"].values.flatten().tolist() if p]
    return paths, sweep_s


def build_blueprint(out_path: Path) -> Path | None:
    try:
        import rerun.blueprint as rrb

        bp = rrb.Blueprint(
            rrb.TimeSeriesView(origin="/response", name="step response"),
            collapse_panels=True,
        )
        bp.save("bencher", str(out_path))
        return out_path
    except Exception as e:  # noqa: BLE001  # pylint: disable=broad-except
        print(f"blueprint save skipped: {e}")
        return None


# --- docs-style wrapper page (mimics the RST-emitted report region) ---

_DOCS_PAGE_TEMPLATE = """\
<!doctype html>
<html><head><meta charset="utf-8"/><title>{title}</title>
<style>body{{font:15px sans-serif;max-width:960px;margin:2em auto;padding:0 1em}}
iframe{{width:100%;height:640px;border:1px solid #ccc}}</style>
</head><body>
<h1>{title}</h1>
<p>Docs-gallery stand-in page for a rerun-native example ({form}).</p>
<details open><summary>Source Code</summary><pre>def example_rerun_reference(run_cfg): ...</pre></details>
<h2>Results:</h2>
{embed}
<p><a href="{report_href}" download>Download report.html</a> &middot;
<a href="{rrd_href}" download>Download report.rrd</a></p>
</body></html>
"""


def docs_page(title: str, form: str, embed: str, report_href: str, rrd_href: str) -> str:
    return _DOCS_PAGE_TEMPLATE.format(
        title=title, form=form, embed=embed, report_href=report_href, rrd_href=rrd_href
    )


# --- candidate S: shared self-hosted viewer (viewer paid once per SITE) ---

_SELFHOSTED_VIEWER_TEMPLATE = """\
<!doctype html>
<html><head><meta charset="utf-8"/>
<meta name="rerun-sdk-version" content="{version}"/>
<title>rerun viewer (self-hosted)</title>
<style>html,body{{margin:0;padding:0;width:100%;height:100%;overflow:hidden;background:#0d1011}}
canvas{{position:absolute;top:0;left:0;width:100%;height:calc(100% - 18px)}}
#foot{{position:absolute;bottom:0;left:0;right:0;height:18px;color:#888;background:#0d1011;
font:11px monospace;text-align:right;padding-right:6px}}</style>
</head><body>
<canvas id="cv"></canvas>
<div id="foot">rerun-sdk {version} (self-hosted viewer, rrd sidecar) &mdash;
<span id="status">loading&hellip;</span></div>
<div id="err" style="color:red;font:12px monospace;white-space:pre-wrap;position:absolute;top:0"></div>
<script src="re_viewer.js"></script>
<script>
const t0 = performance.now();
async function main() {{
  const p = new URLSearchParams(location.search);
  const url = p.get("url");
  if (!url) throw new Error("Missing ?url= parameter");
  await wasm_bindgen("re_viewer_bg.wasm");
  const handle = new wasm_bindgen.WebHandle({{hide_welcome_screen: true, persist: false}});
  await handle.start(document.getElementById("cv"));
  const rrdResp = await fetch(new URL(url, location.href));
  if (!rrdResp.ok) throw new Error("rrd fetch failed: " + rrdResp.status);
  const rrd = new Uint8Array(await rrdResp.arrayBuffer());
  handle.open_channel("sidecar", "sidecar rrd");
  handle.send_rrd_to_channel("sidecar", rrd);
  handle.close_channel("sidecar");
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


def build_selfhosted_viewer(
    viewer_assets: tuple[str, bytes], version: str, static_dir: Path
) -> dict[str, int]:
    """Write the shared viewer (js + wasm + loader page) into _static/rerun_viewer/."""
    js, wasm = viewer_assets
    vdir = static_dir / "rerun_viewer"
    vdir.mkdir(parents=True, exist_ok=True)
    (vdir / "re_viewer.js").write_text(js, encoding="utf-8")
    (vdir / "re_viewer_bg.wasm").write_bytes(wasm)
    (vdir / "viewer.html").write_text(
        _SELFHOSTED_VIEWER_TEMPLATE.format(version=version), encoding="utf-8"
    )
    sizes = {
        "re_viewer.js": (vdir / "re_viewer.js").stat().st_size,
        "re_viewer_bg.wasm": (vdir / "re_viewer_bg.wasm").stat().st_size,
        "viewer.html": (vdir / "viewer.html").stat().st_size,
    }
    # what the wire cost looks like with standard gzip content-encoding
    sizes["re_viewer_bg.wasm (gzip)"] = len(gzip.compress(wasm, 6))
    sizes["re_viewer.js (gzip)"] = len(gzip.compress(js.encode(), 6))
    return sizes


def human(n: int) -> str:
    return f"{n:,} B ({n / 1e6:.2f} MB)"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--skip-sweep", action="store_true", help="reuse out/rrds from a prior run")
    args = parser.parse_args()

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    measurements: dict = {}

    if args.skip_sweep and RRD_CACHE.exists() and list(RRD_CACHE.glob("*.rrd")):
        rrd_paths = sorted(RRD_CACHE.glob("sample_*.rrd"))
        sweep_s = 0.0
        print(f"reusing {len(rrd_paths)} cached recordings")
    else:
        rrd_paths, sweep_s = run_reference_sweep()
        RRD_CACHE.mkdir(parents=True, exist_ok=True)
        stable = []
        for i, p in enumerate(rrd_paths):
            dest = RRD_CACHE / f"sample_{i:02d}.rrd"
            dest.write_bytes(p.read_bytes())
            stable.append(dest)
        rrd_paths = stable
    total_rrd = sum(p.stat().st_size for p in rrd_paths)
    print(f"sweep: {len(rrd_paths)} recordings, {human(total_rrd)}, {sweep_s:.1f}s")
    measurements["sweep_s"] = round(sweep_s, 1)
    measurements["n_samples"] = len(rrd_paths)
    measurements["per_sample_rrd_total"] = total_rrd

    # --- shared report artifacts ---
    reports_dir = SITE_DIR / "_reports" / "example_rerun_reference"
    reports_dir.mkdir(parents=True, exist_ok=True)
    blueprint = build_blueprint(OUT_DIR / "blueprint.rbl")

    t = time.perf_counter()
    report_rrd = merge_rrds(rrd_paths, reports_dir / "report.rrd", blueprint=blueprint)
    merge_s = time.perf_counter() - t
    version = read_rrd_writer_version(report_rrd)

    t = time.perf_counter()
    viewer_assets = fetch_sdk_viewer_assets()
    fetch_assets_s = time.perf_counter() - t

    t = time.perf_counter()
    report_html = build_offline_html(report_rrd, reports_dir / "report.html", viewer_assets)
    offline_build_s = time.perf_counter() - t

    cdn_html = build_cdn_wrapper_html(report_rrd, reports_dir / "report_cdn.html")

    measurements["writer_version"] = version
    measurements["merge_s"] = round(merge_s, 2)
    measurements["fetch_viewer_assets_s"] = round(fetch_assets_s, 2)
    measurements["build_offline_html_s"] = round(offline_build_s, 2)
    measurements["report.rrd"] = report_rrd.stat().st_size
    measurements["report.html (offline)"] = report_html.stat().st_size
    measurements["report_cdn.html"] = cdn_html.stat().st_size

    rrd_href = "_reports/example_rerun_reference/report.rrd"
    html_href = "_reports/example_rerun_reference/report.html"

    # --- A1: iframe src -> shipped offline report asset ---
    a1 = SITE_DIR / "page_a1_iframe_asset.html"
    a1.write_text(
        docs_page(
            "Example Rerun Reference (A1: offline report as static asset)",
            "A1",
            f'<iframe src="{html_href}"></iframe>',
            html_href,
            rrd_href,
        ),
        encoding="utf-8",
    )

    # --- A2: iframe srcdoc, page fully self-contained ---
    t = time.perf_counter()
    srcdoc = html_lib.escape(report_html.read_text(encoding="utf-8"), quote=True)
    a2 = SITE_DIR / "page_a2_srcdoc.html"
    a2.write_text(
        docs_page(
            "Example Rerun Reference (A2: offline report inlined via srcdoc)",
            "A2",
            f'<iframe srcdoc="{srcdoc}"></iframe>',
            html_href,
            rrd_href,
        ),
        encoding="utf-8",
    )
    measurements["a2_srcdoc_build_s"] = round(time.perf_counter() - t, 2)

    # --- C: CDN wrapper page + rrd sidecar ---
    c = SITE_DIR / "page_c_cdn.html"
    c.write_text(
        docs_page(
            "Example Rerun Reference (C: pinned-CDN wrapper + rrd sidecar)",
            "C",
            '<iframe src="_reports/example_rerun_reference/report_cdn.html"></iframe>',
            html_href,
            rrd_href,
        ),
        encoding="utf-8",
    )

    # --- S: shared self-hosted viewer + rrd sidecar ---
    static_dir = SITE_DIR / "_static"
    shared_sizes = build_selfhosted_viewer(viewer_assets, version, static_dir)
    s = SITE_DIR / "page_s_selfhosted.html"
    s.write_text(
        docs_page(
            "Example Rerun Reference (S: shared self-hosted viewer + rrd sidecar)",
            "S",
            f'<iframe src="_static/rerun_viewer/viewer.html?url=../../{rrd_href}"></iframe>',
            html_href,
            rrd_href,
        ),
        encoding="utf-8",
    )

    # --- size table ---
    n = N_RERUN_EXAMPLES_TODAY
    rrd_sz = report_rrd.stat().st_size
    off_sz = report_html.stat().st_size
    shared_total = sum(
        v for k, v in shared_sizes.items() if not k.endswith("(gzip)")
    )
    per_page = {
        "A1 iframe->asset": a1.stat().st_size + off_sz + rrd_sz,
        "A2 srcdoc": a2.stat().st_size + off_sz + rrd_sz,  # download links still ship assets
        "A2 srcdoc (page only)": a2.stat().st_size,
        "C cdn wrapper": c.stat().st_size + cdn_html.stat().st_size + rrd_sz,
        "S self-hosted": s.stat().st_size + rrd_sz,
    }
    measurements["shared_viewer_assets"] = shared_sizes
    measurements["shared_viewer_total"] = shared_total
    measurements["per_page_payload"] = per_page
    measurements["projected_site_cost"] = {
        "A1 x8": per_page["A1 iframe->asset"] * n,
        "A2 x8": per_page["A2 srcdoc"] * n,
        "C x8": per_page["C cdn wrapper"] * n,
        "S x8 (+shared once)": per_page["S self-hosted"] * n + shared_total,
    }

    print("\n=== artifact sizes ===")
    for k in ("report.rrd", "report.html (offline)", "report_cdn.html"):
        print(f"  {k:26s} {human(measurements[k])}")
    print("\n=== shared self-hosted viewer (paid once per docs site) ===")
    for k, v in shared_sizes.items():
        print(f"  {k:26s} {human(v)}")
    print(f"  {'TOTAL (uncompressed)':26s} {human(shared_total)}")
    print("\n=== per-example page payload (page + everything it ships) ===")
    for k, v in per_page.items():
        print(f"  {k:26s} {human(v)}")
    print(f"\n=== projected docs-site cost for the {n} rerun examples registered today ===")
    for k, v in measurements["projected_site_cost"].items():
        print(f"  {k:26s} {human(v)}")

    (OUT_DIR / "measurements_build.json").write_text(json.dumps(measurements, indent=2))
    print(f"\nwrote {OUT_DIR / 'measurements_build.json'}; site under {SITE_DIR}")


if __name__ == "__main__":
    main()
