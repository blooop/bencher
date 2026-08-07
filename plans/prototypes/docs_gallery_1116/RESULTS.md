# Prototype results — #1116: rerun-native reports in the generated docs gallery

Prototype evidence for a decision, not production code. Built on `prototype/docs-gallery-1116`
from `origin/main` (cfd551a3), using the #1112 reference-report shape (ControlSystemSweep,
`damping_ratio × omega_n`, 15 samples) and the #1107 offline-HTML builder (vendored as
`save_rerun_native.py`).

## Scripts

| Script | What it does |
|---|---|
| `build_pages.py` | Runs the reference sweep, merges the 15 per-sample `.rrd`s (+ blueprint), builds every candidate gallery-page form under `out/site/`, prints/records sizes. |
| `probe_load.py` | Serves `out/site/` on localhost, loads each page in headless Chrome with all non-local DNS blackholed (1107 technique), records viewer readiness. |
| `screenshot_bench.py` | Screenshots the offline `report.html` via Playwright, GPU vs `--disable-gpu`, records the *actual* WebGL renderer string, time-to-ready, time-to-visible-content, PNG size; emits the candidate-B page. |
| `gpu_attempt.py` | One-off attempt to force genuinely GPU-backed headless Chrome (Vulkan/ANGLE flags). |

Raw numbers: `out/measurements_build.json`, `out/measurements_probe.json`,
`out/measurements_screenshot.json` (out/ is not committed; regenerate with the commands in
each script's docstring).

## Correction to the ticket's premise: there is no notebook pipeline

`bencher/example/meta/generate_examples.py` does **not** emit notebooks. Per example it
emits: a saved Panel HTML report under `docs/_extra/reference/meta/<section>/_reports/<stem>/`,
a Playwright-cropped PNG thumbnail under `_thumbs/`, and an **RST page** whose report region
is a plain `.. raw:: html` iframe pointing at the report. Sphinx (myst_parser for .md, RST
otherwise; no nbsphinx/nbsite/myst-nb anywhere) copies `docs/_extra/` verbatim via
`html_extra_path`. Raw HTML/iframe outputs therefore already survive the converter — every
existing example page is one. (The "generate-docs writes notebooks" comment in
pyproject.toml is stale.)

**Deployment:** Read the Docs (`.readthedocs.yaml`), which installs Playwright Chromium and
runs `generate_examples.py` in `pre_build` — so thumbnails are generated **on RTD**, with no
GPU. The GHA `ci` job only runs phase-1 `generate-examples` (file generation, no
reports/thumbnails). RTD Community limits ([build resources](https://docs.readthedocs.com/platform/latest/builds.html)):
15 min build time, 7 GB memory, 5 GB disk (soft); **no documented output-artifact size limit**.

**Status quo:** rerun examples are already in this pipeline — 8 registered
(`generate_meta_rerun.py`: capture_window, regression, sweep, composable_{right,down,
sequence,overlay}, summary) under the "Rerun Integration" gallery section — and the built
docs **already ship the CDN wrapper**: `BenchReport.save()` → `inline_rrd_iframes()` writes
`_rrd/viewer_0.35.0.html` (jsDelivr `@rerun-io/web-viewer@<pinned>`) + per-sample `.rrd`
sidecars next to each saved report. Candidate C is not hypothetical; it is what ships today.

## Candidate forms built and measured

All from the same merged reference recording (`report.rrd` = 351,165 B; writer 0.35.0).
Offline `report.html` = 18,146,265 B (18.15 MB; 17.8 MB viewer floor + ~1.33× rrd).
Build cost per example at docs-build time: merge 0.04 s + offline-HTML build 1.28 s
(+1.06 s one-time viewer-asset fetch).

| Form | Page + shipped assets per example | ×8 examples (site cost) | Loads offline (DNS blackholed)? |
|---|---|---|---|
| **A1** iframe → offline `report.html` as static asset | 18.50 MB | **148.0 MB** | **YES** — viewer ready in 739 ms |
| **A2** offline report inlined via `<iframe srcdoc>` | 36.65 MB (page alone 18.15 MB, escaping ≈2×… plus download-link assets) | 293.2 MB | **NO — broken**: `wasm_bindgen is not defined` inside `about:srcdoc`; the 18 MB attribute-escaped script does not execute |
| **B** screenshot PNG + download links | 0.31 MB page+PNG (18.8 MB with downloadable report.html+rrd) | 2.5 MB (150 MB with downloads) | n/a (static) |
| **C** pinned-CDN wrapper (1,348 B) + `report.rrd` sidecar | 0.35 MB | **2.8 MB** | **NO** (expected): `Failed to fetch … cdn.jsdelivr.net` offline; READY in 586 ms with network up |
| **S** *(new)* shared self-hosted viewer + `report.rrd` sidecar | 0.35 MB | **42.8 MB** (40.0 MB of it paid **once**: `re_viewer_bg.wasm` 39.8 MB + `re_viewer.js` 0.22 MB in `_static/rerun_viewer/`; 13.1 MB on the wire gzipped) | **YES** — viewer ready in 487 ms |

Form S is the CDN wrapper's page shape with the viewer served from the docs site's own
`_static/` instead of jsDelivr: per-example marginal cost identical to C (~rrd size), no
third-party dependency, viewer version pinned by the build itself. It needs an HTTP origin
(docs sites are one) and was proven to make **zero** external requests.

## Screenshot / thumbnail cost (candidate B and the thumbnail question)

The 1107 caveat "with `--disable-gpu` the viewer's shaders compile on SwiftShader and take
minutes" **does not reproduce** on rerun 0.35 / Chrome 151 / Playwright 1.5x:

| Config | Actual renderer (measured in-page) | Viewer ready | Content visible in screenshot | Total wall incl. browser launch |
|---|---|---|---|---|
| system Chrome headless, no `--disable-gpu` | SwiftShader (Playwright headless forces it) | 2.9 s | 3.9 s | 7.5 s |
| system Chrome headless, `--disable-gpu` | SwiftShader | 3.9 s | 5.0 s | 9.1 s |
| forced Vulkan/ANGLE GPU flags | no WebGL context at all | never (>300 s) | never | failed |

The SwiftShader screenshot (`out/screenshot_gpu.png`, 309 KB at 1280×800) **fully shows the
report**: time-series panel with error/output/setpoint curves, timeline, "Software
rasterizer" banner. So the software-rendering path — the only one available on RTD builders
and GHA standard runners — costs **~5–10 s per example**, not minutes. (GHA standard runners
have no GPU; GPU is a paid "larger runner" option — [GitHub changelog](https://github.blog/changelog/2024-07-08-github-actions-gpu-hosted-runners-are-now-generally-available/),
[runner docs](https://docs.github.com/actions/using-github-hosted-runners/about-github-hosted-runners) — irrelevant here since docs build on RTD.)

**Current pipeline, measured end-to-end** (`generate_examples.py --only example_rerun_sweep`,
docs env, Playwright chromium-headless-shell 149): exec+save 0.5 s, thumbnail 13.5 s. The
produced thumbnail shows the report's **Bokeh scalar plots** (overshoot/settling-time curves
+ heatmaps), not the rerun viewer — the crop machinery's `.bk-Figure` tier outranks iframes,
which it never screenshots. So rerun examples already get a working (if rerun-less)
thumbnail today with zero new machinery; making the thumbnail show the *viewer* would mean
adding `iframe` (or a rendered-viewer wait) to the selector tiers, at the measured ~5–10 s
SwiftShader cost per example.

## Pipeline fit (question D)

Nothing about rerun-native pages needs a separate gallery section or different page
machinery:

- The RST template's report region is already an iframe; pointing it at (A1) the offline
  `report.html`, (C) the CDN wrapper, or (S) the self-hosted viewer page is a one-line
  difference in what `generate_examples.py` writes / what `BenchReport.save()` emits.
- Assets ride `docs/_extra/` → `html_extra_path` verbatim copy; a shared viewer would sit in
  `docs/_static/rerun_viewer/` (or `_extra`) written once by the generator. Copy cost of
  40 MB is noise next to the existing example-execution budget; the binding RTD constraint
  is the 15-minute build, and per-example costs measured here (0.5 s exec, ~1.3 s offline-
  HTML build if chosen, 5–13 s thumbnail) fit the existing per-example budget envelope.
- Thumbnails: same `_thumbs/<section>/<stem>.png` machinery, already producing usable output
  for rerun examples.

## Evidence-weighted read (for the coordinating session)

Judged against "long-term correct, scales well":

- **A2 (srcdoc)** is eliminated: broken outright, and 2× size on top of 18 MB.
- **A1 (offline report per example)** honors the #1107 renders-forever promise on every
  gallery page, but costs 18.5 MB **per example page view** and ~18.5 MB × N of docs storage
  (148 MB at today's N=8). RTD has no hard artifact limit, so it *tolerates* it; every
  reader pays it. It scales linearly in the one asset (the viewer) that never varies.
- **B (screenshot + download links)** is cheap (~0.3 MB/page, ~5–13 s CI per example) but
  demotes the docs gallery to static images when the whole point of the integration is an
  interactive viewer; the download links still ship the 18 MB report per example if offered.
- **C (CDN)** is today's shipped behavior. The rot argument is real for *saved* reports but
  materially weaker for docs: docs rebuild every release, re-pinning the CDN version each
  time, and a stale docs page is regenerable — unlike a user's archived report. Remaining
  exposure: jsDelivr availability at *view* time and offline reading.
- **S (self-hosted viewer)** dominates C on its only weakness: identical page shape and
  per-example cost (~rrd size), but the viewer is served from the docs site itself — no
  third-party network dependence, version pinned by the build, proven zero external
  requests, 487 ms to ready. Site-wide cost is one 40 MB (13 MB wire) asset regardless of N,
  so it scales O(1) in examples where A1 scales O(N)×18 MB. It slots into the existing
  RST/iframe/thumbnail pipeline unchanged.

The scaling-honest recommendation is **S for the embedded viewer on gallery pages** (with
per-example `report.rrd` sidecars), keeping **A1's offline `report.html` as the download
link target** for the renders-forever artifact, and leaving thumbnails on the existing
machinery (optionally teaching the crop tiers about the viewer iframe at ~5–10 s/example).
This is prototype evidence; the resolution belongs to the coordinating session.
