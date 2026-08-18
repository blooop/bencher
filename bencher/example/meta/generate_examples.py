"""Generate Python example files, run them, save HTML reports, and generate RST for docs."""

import ast
import html
import importlib
import io
import os
import re
import shutil
import subprocess
import time
from pathlib import Path

import bencher as bn

GENERATED_DIR = Path("bencher/example/generated")


def _extract_run_kwargs(py_file: Path) -> dict:
    """Extract kwargs from bn.run() call in __main__ block."""
    source = py_file.read_text()
    tree = ast.parse(source)
    for node in ast.walk(tree):
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == "run"
            and isinstance(node.func.value, ast.Name)
            and node.func.value.id == "bn"
        ):
            kwargs = {}
            for kw in node.keywords:
                try:
                    kwargs[kw.arg] = ast.literal_eval(kw.value)
                except (ValueError, TypeError):
                    continue
            return kwargs
    return {}


META_DOCS_DIR = Path("docs/reference/meta")
# Reports go under docs/_extra/ so html_extra_path copies them to match the built output structure
REPORTS_EXTRA_DIR = Path("docs/_extra/reference/meta")
THUMBS_EXTRA_DIR = REPORTS_EXTRA_DIR / "_thumbs"
# The scorecard example is a standalone HTML page (not a Bench report), rendered
# into _extra/ so the docs/scorecard.md page can iframe it.
SCORECARD_EXTRA_DIR = Path("docs/_extra/scorecard_example")


def generate_scorecard_example():
    """Render the standalone scorecard example into _extra for docs/scorecard.md."""
    from bencher.example.example_scorecard import example_scorecard

    if SCORECARD_EXTRA_DIR.exists():
        shutil.rmtree(SCORECARD_EXTRA_DIR)
    out = example_scorecard(SCORECARD_EXTRA_DIR)
    print(f"  Generated scorecard example: {out}")


# Thumbnail geometry. Screenshots are captured at THUMB_SCALE device pixels per CSS
# pixel and downscaled, so thumbnails stay sharp on high-DPI screens. The saved PNG is
# fitted inside THUMB_MAX_W x THUMB_MAX_H without distortion and never upscaled. This is
# only a resolution cap — the displayed size and aspect ratio are set by
# --gallery-thumb-aspect / --gallery-card-min-width in docs/_static/custom.css, so keep
# these at or above 2x the widest card the CSS can produce.
THUMB_MAX_W = 480
THUMB_MAX_H = 480
THUMB_SCALE = 2
# Ignore elements smaller than this when hunting for the results region — it filters out
# Bokeh toolbar icons, colour swatches and other chrome.
MIN_RESULT_W = 100
MIN_RESULT_H = 80
# Stop growing the crop once it is this much taller than it is wide. Reports often stack
# several full-size plots; including them all would shrink each one to an unreadable strip.
MAX_CROP_ASPECT = 1.3
CROP_PAD = 8

# Candidate result elements, most to least preferred. A report's plots and media make a
# better thumbnail than the summary DataFrame table that often precedes them, so a lower
# tier is used only when no element from a higher tier exists below the "Results:" heading.
# Bokeh/Panel render into shadow DOM, so these must be queried through Playwright's
# selector engine (which pierces open shadow roots) rather than document.querySelectorAll.
RESULT_SELECTOR_TIERS = (
    ".bk-Figure, video, img",
    ".bk-Canvas, .bk-DataTable, table",
)
# Everything above the "Results:" heading is title, description and the sweep-shape
# diagram — that text is what made naive top-of-page screenshots useless as thumbnails.
RESULTS_HEADING_SELECTOR = "h1, h2, h3, h4"
# Bokeh's pan/zoom/save toolbar sits inside .bk-Figure, so it would land in the crop. It
# is interactive chrome with no value in a static thumbnail, so it is hidden before the
# region is measured — that way the crop is taken from the post-reflow layout.
TOOLBAR_SELECTOR = ".bk-ToolbarPanel"
# Text results (ResultString, ResultVec, ResultPath) render as Panel markup panes with no
# plot to frame at all. For those the whole results section is cropped instead, using a
# permissive selector and a lower size floor to pick up the small text panes.
SECTION_SELECTOR = "div, pre, table, img, video, canvas"
MIN_SECTION_W = 60
MIN_SECTION_H = 30
# Slack when testing whether an element starts below the "Results:" heading. Candidates
# must *begin* below it, not merely end below it, or the report's page-spanning wrapper
# divs qualify and stretch the crop to the full content width.
MARKER_TOLERANCE = 4
# How long to keep polling for a report's results to become measurable. Reports that
# render nothing pay the full wait, so keep the budget modest.
RESULT_WAIT_ATTEMPTS = 8
RESULT_WAIT_INTERVAL_MS = 250


def _query_all_frames(page, selector: str) -> list:
    """Query every frame in the page, not just the main one.

    over_time reports are a tab bar plus an iframe, so their entire report — plots and
    "Results:" heading alike — lives in a child frame that page.query_selector_all cannot
    see. Element bounding boxes are relative to the main frame's viewport either way, so
    the coordinates compose directly into a top-level screenshot clip.
    """
    handles = []
    for frame in page.frames:
        handles.extend(frame.query_selector_all(selector))
    return handles


def _results_marker_bottom(page) -> float | None:
    """Return the document y of the bottom of the report's "Results:" heading, or None."""
    for handle in _query_all_frames(page, RESULTS_HEADING_SELECTOR):
        raw = handle.text_content() or ""
        # Panel appends a "¶" anchor link to headings, so compare on letters only.
        if re.sub(r"[^a-z]", "", raw.lower()) != "results":
            continue
        box = handle.bounding_box()
        if box is not None:
            return box["y"] + box["height"]
    return None


def _hide_toolbars(page) -> None:
    """Hide Bokeh plot toolbars so they stay out of thumbnails.

    Panel/Bokeh render into shadow DOM, which a page-level stylesheet cannot reach, so
    each toolbar is hidden individually through Playwright's shadow-piercing selectors.
    """
    for handle in _query_all_frames(page, TOOLBAR_SELECTOR):
        try:
            handle.evaluate("el => { el.style.display = 'none'; }")
        except Exception as e:  # pylint: disable=broad-except  # noqa: BLE001
            # A toolbar we cannot hide is cosmetic; keep going rather than lose the thumbnail.
            print(f"  WARNING: Could not hide plot toolbar: {e}")


def _boxes_below_marker(
    page, selector: str, marker_bottom: float | None, min_w: float, min_h: float
) -> list[dict]:
    """Return bounding boxes matching selector that sit below the "Results:" heading."""
    boxes = []
    for handle in _query_all_frames(page, selector):
        box = handle.bounding_box()
        if box is None or box["width"] < min_w or box["height"] < min_h:
            continue
        # Keep only elements that start below the "Results:" heading.
        if marker_bottom is not None and box["y"] < marker_bottom - MARKER_TOLERANCE:
            continue
        boxes.append(box)
    boxes.sort(key=lambda b: (b["y"], b["x"]))
    return boxes


def _grow_region(boxes: list[dict]) -> tuple[float, float, float, float]:
    """Union non-empty boxes in document order, stopping before the region becomes a strip.

    Seeded from the first box, which is therefore always accepted even when it is an
    unusually tall one; the caller clamps the height afterwards.
    """
    first = boxes[0]
    left, top = first["x"], first["y"]
    right, bottom = first["x"] + first["width"], first["y"] + first["height"]
    for box in boxes[1:]:
        n_left = min(left, box["x"])
        n_top = min(top, box["y"])
        n_right = max(right, box["x"] + box["width"])
        n_bottom = max(bottom, box["y"] + box["height"])
        if (n_bottom - n_top) > MAX_CROP_ASPECT * (n_right - n_left):
            break
        left, top, right, bottom = n_left, n_top, n_right, n_bottom
    return left, top, right, bottom


def _page_size(page) -> tuple[float, float]:
    """Return the page's scrollable width and height in a single round-trip."""
    width, height = page.evaluate(
        "() => [document.documentElement.scrollWidth, document.documentElement.scrollHeight]"
    )
    return float(width), float(height)


def _pad_and_clamp(
    left: float, top: float, right: float, bottom: float, page_w: float, page_h: float
) -> dict | None:
    """Pad a region, clamp it to the page, and convert it to a screenshot clip rect."""
    left = max(0.0, left - CROP_PAD)
    top = max(0.0, top - CROP_PAD)
    right = min(page_w, right + CROP_PAD)
    bottom = min(page_h, bottom + CROP_PAD)
    if right - left < 1 or bottom - top < 1:
        return None
    return {"x": left, "y": top, "width": right - left, "height": bottom - top}


def _results_clip(page) -> dict | None:
    """Return a screenshot clip rect covering the report's results, or None.

    Prefers the highest tier of result element present below the "Results:" heading, and
    falls back to the whole results section for reports whose results are plain text.
    """
    marker_bottom = _results_marker_bottom(page)

    boxes = []
    for selector in RESULT_SELECTOR_TIERS:
        boxes = _boxes_below_marker(page, selector, marker_bottom, MIN_RESULT_W, MIN_RESULT_H)
        if boxes:
            break

    if boxes:
        left, top, right, bottom = _grow_region(boxes)
    elif marker_bottom is not None:
        # No plot, table or media: frame the results section itself.
        section = _boxes_below_marker(
            page, SECTION_SELECTOR, marker_bottom, MIN_SECTION_W, MIN_SECTION_H
        )
        if not section:
            return None
        left = min(b["x"] for b in section)
        right = max(b["x"] + b["width"] for b in section)
        top = marker_bottom
        bottom = max(b["y"] + b["height"] for b in section)
    else:
        return None

    # Clamp the height so a single tall result — a stacked video composition, a long
    # DataFrame table — is topped rather than squeezed into an unreadable sliver.
    bottom = min(bottom, top + MAX_CROP_ASPECT * (right - left))

    page_w, page_h = _page_size(page)
    return _pad_and_clamp(left, top, right, bottom, page_w, page_h)


def _wait_for_results(page) -> dict | None:
    """Poll until the report's results region is measurable, or the attempts run out.

    Returns the last clip attempted, which is None for a report that genuinely renders
    nothing.
    """
    for attempt in range(RESULT_WAIT_ATTEMPTS):
        clip = _results_clip(page)
        if clip is not None:
            return clip
        if attempt < RESULT_WAIT_ATTEMPTS - 1:
            page.wait_for_timeout(RESULT_WAIT_INTERVAL_MS)
    return None


def _resize_and_save_png(
    png_data: bytes,
    thumb_path: Path,
    max_width: int = THUMB_MAX_W,
    max_height: int = THUMB_MAX_H,
) -> None:
    """Fit screenshot PNG data inside max_width x max_height and save to disk.

    Aspect ratio is preserved and the image is never upscaled, so a small result (a 200px
    video, say) stays sharp rather than being blown up.
    """
    from PIL import Image

    img = Image.open(io.BytesIO(png_data))
    ratio = min(max_width / img.width, max_height / img.height, 1.0)
    if ratio < 1.0:
        size = (max(1, round(img.width * ratio)), max(1, round(img.height * ratio)))
        img = img.resize(size, Image.Resampling.LANCZOS)
    thumb_path.parent.mkdir(parents=True, exist_ok=True)
    img.save(thumb_path, optimize=True)


def _take_thumbnail(
    html_path: Path,
    thumb_path: Path,
    page=None,
    width: int = 1200,
    height: int = 900,
) -> None:
    """Screenshot an HTML report's results and save as a PNG thumbnail.

    The crop is centred on the report's result plots rather than the top of the page,
    which is mostly title and description text. Falls back to the top of the page when no
    result elements can be found.

    Uses the provided playwright page if given; otherwise creates a temporary browser.
    """

    def _screenshot_with(pg) -> bytes:
        pg.set_viewport_size({"width": width, "height": height})
        pg.goto(html_path.resolve().as_uri(), wait_until="networkidle", timeout=15000)
        # Brief pause for Bokeh/Panel JS to render plots after network settles
        pg.wait_for_timeout(500)
        # networkidle does not mean Bokeh has painted, and a fixed sleep is a coin flip on
        # a cold browser: too short and the region is unmeasurable, so the thumbnail falls
        # back to a screenshot of a blank page. Poll for the results instead.
        if _wait_for_results(pg) is None:
            return pg.screenshot()
        _hide_toolbars(pg)
        # Let Bokeh reflow after the toolbars are removed before measuring the crop.
        pg.wait_for_timeout(150)
        clip = _results_clip(pg)
        if clip is None:
            return pg.screenshot()
        # full_page is required here, not redundant with clip: a report's first plot can
        # sit thousands of pixels down the page (xy_scatter's is at y≈5400 with a 900px
        # viewport), and clip alone then fails with "Clipped area is either empty or
        # outside the resulting image". Resizing the viewport to reach it instead would
        # re-trigger Bokeh's responsive relayout and invalidate the measured geometry.
        return pg.screenshot(full_page=True, clip=clip)

    if page is not None:
        png_data = _screenshot_with(page)
        _resize_and_save_png(png_data, thumb_path)
        return

    # Only the standalone path needs playwright itself; with a caller-supplied page the
    # capture works without it installed, which keeps the crop logic unit-testable.
    from playwright.sync_api import sync_playwright  # pylint: disable=import-error

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        tmp_page = browser.new_page(
            viewport={"width": width, "height": height},
            device_scale_factor=THUMB_SCALE,
        )
        try:
            png_data = _screenshot_with(tmp_page)
            _resize_and_save_png(png_data, thumb_path)
        finally:
            browser.close()


def generate_python_files():
    """Phase 1: Run meta generators to produce Python example files."""
    if GENERATED_DIR.exists():
        shutil.rmtree(GENERATED_DIR)
    GENERATED_DIR.mkdir(parents=True, exist_ok=True)

    from bencher.example.meta.generate_meta import example_meta
    from bencher.example.meta.generate_meta_advanced import example_meta_advanced
    from bencher.example.meta.generate_meta_aggregation import example_meta_aggregation
    from bencher.example.meta.generate_meta_bool_plot_types import example_meta_bool_plot_types
    from bencher.example.meta.generate_meta_cartesian_animation import (
        example_meta_cartesian_animation,
    )
    from bencher.example.meta.generate_meta_composable import example_meta_composable
    from bencher.example.meta.generate_meta_const_vars import example_meta_const_vars
    from bencher.example.meta.generate_meta_container_tabs import example_meta_container_tabs
    from bencher.example.meta.generate_meta_image_video import example_meta_image_video
    from bencher.example.meta.generate_meta_levels import example_meta_levels
    from bencher.example.meta.generate_meta_optimization import (
        example_meta_optimization,
        example_meta_optimization_aggregated,
        example_meta_optimization_over_time,
    )
    from bencher.example.meta.generate_meta_performance import example_meta_performance
    from bencher.example.meta.generate_meta_plot_types import example_meta_plot_types
    from bencher.example.meta.generate_meta_publish import example_meta_publish
    from bencher.example.meta.generate_meta_regression import example_meta_regression
    from bencher.example.meta.generate_meta_rerun import example_meta_rerun
    from bencher.example.meta.generate_meta_result_types import (
        example_meta_result_dataset_over_time,
        example_meta_result_types,
    )
    from bencher.example.meta.generate_meta_sampling import example_meta_sampling
    from bencher.example.meta.generate_meta_statistics import example_meta_statistics
    from bencher.example.meta.generate_meta_workflows import example_meta_workflows
    from bencher.example.meta.generate_meta_yaml import example_meta_yaml

    example_meta()
    example_meta_result_types()
    example_meta_result_dataset_over_time()
    example_meta_image_video()
    example_meta_composable()
    example_meta_plot_types()
    example_meta_levels()
    example_meta_sampling()
    example_meta_statistics()
    example_meta_const_vars()
    example_meta_optimization()
    example_meta_optimization_over_time()
    example_meta_optimization_aggregated()
    example_meta_workflows()
    example_meta_advanced()
    example_meta_bool_plot_types()
    example_meta_regression()
    example_meta_yaml()
    example_meta_performance()
    example_meta_publish()
    example_meta_rerun()
    example_meta_aggregation()
    example_meta_cartesian_animation()
    example_meta_container_tabs()

    # Write __init__.py files so generated examples are importable
    for d in GENERATED_DIR.rglob("*"):
        if d.is_dir() and d.name != "__pycache__":
            init = d / "__init__.py"
            if not init.exists():
                init.touch()
    init = GENERATED_DIR / "__init__.py"
    if not init.exists():
        init.touch()

    # Lint-fix and format all generated files in a single pass. The autofix pass keeps
    # generated output in sync with ruff's rules (notably import sorting) so generators
    # can emit imports in any order without leaving `pixi run lint` dirty.
    if shutil.which("ruff"):
        subprocess.run(
            ["ruff", "check", "--fix-only", "--quiet", str(GENERATED_DIR)],
            check=False,
        )
        subprocess.run(["ruff", "format", str(GENERATED_DIR)], check=False)


def _import_example_module(py_file: Path):
    """Import a generated example module using the normal package path."""
    rel = py_file.relative_to(GENERATED_DIR).with_suffix("")
    module_path = ".".join(("bencher.example.generated", *rel.parts))
    return importlib.import_module(module_path)


def _find_example_function(mod):
    """Find the example_* function in a module."""
    for name, obj in vars(mod).items():
        if name.startswith("example_") and callable(obj):
            return obj
    return None


def run_example_and_save(
    py_file: Path, docs_dir: Path, generated_dir: Path, page=None, skip_thumbnails=False
):
    """Run a Python example, save HTML report, write RST doc page.

    Returns a metadata dict for gallery generation, or None on failure.
    """
    rel = py_file.relative_to(generated_dir)
    output_dir = docs_dir / rel.parent
    output_dir.mkdir(parents=True, exist_ok=True)
    stem = py_file.stem

    mod = _import_example_module(py_file)
    example_fn = _find_example_function(mod)
    if example_fn is None:
        print(f"WARNING: No example_* function found in {py_file}, skipping")
        return None

    run_kwargs = _extract_run_kwargs(py_file)
    run_cfg = bn.BenchRunCfg()
    run_cfg.execution.subsampling_divisions = run_kwargs.get("subsampling_divisions", 4)
    run_cfg.execution.repeats = run_kwargs.get("repeats", 1)
    if "use_optuna" in run_kwargs:
        run_cfg.visualization.use_optuna = run_kwargs["use_optuna"]
    if run_kwargs.get("over_time"):
        run_cfg.time.over_time = True
    optimise = run_kwargs.get("optimise", 0)
    print(f"Running {py_file}...")
    t_exec_start = time.perf_counter()
    bench = example_fn(run_cfg)

    if optimise and bench.results:
        bench.optimize(n_trials=optimise, plot=False)
        for res in bench.results:
            bench.report.append_to_result(res, res.to_optuna_plots())

    # Save reports under _extra/ so html_extra_path copies them alongside built RST pages
    reports_output_dir = REPORTS_EXTRA_DIR / rel.parent
    reports_output_dir.mkdir(parents=True, exist_ok=True)
    report_dir = reports_output_dir / f"_reports/{stem}"
    report_path = bench.report.save(
        directory=str(report_dir),
        in_html_folder=False,
    )
    exec_elapsed = time.perf_counter() - t_exec_start
    print(f"  Saved report to {report_path} ({exec_elapsed:.1f}s)")

    # Generate thumbnail screenshot (skipped on RTD to save build time)
    thumb_path = THUMBS_EXTRA_DIR / rel.parent / f"{stem}.png"
    thumb_elapsed = 0.0
    if skip_thumbnails:
        print(f"  Skipping thumbnail for {stem}")
    else:
        t_thumb_start = time.perf_counter()
        try:
            _take_thumbnail(Path(report_path), thumb_path, page=page)
            thumb_elapsed = time.perf_counter() - t_thumb_start
            print(f"  Saved thumbnail to {thumb_path} ({thumb_elapsed:.1f}s)")
        except Exception as e:  # pylint: disable=broad-except  # noqa: BLE001
            thumb_elapsed = time.perf_counter() - t_thumb_start
            print(f"  WARNING: Failed to save thumbnail for {stem}: {e}")

    # Generate RST that shows source + embeds HTML report
    title_text = stem.replace("_", " ").title()
    underline = "=" * len(title_text)
    # Compute relative path from RST location to the Python source
    rst_path = output_dir / f"{stem}.rst"
    py_rel = os.path.relpath(py_file, rst_path.parent)

    rst_content = f"""{title_text}
{underline}

.. raw:: html

   <details class="bencher-source" open>
   <summary>Source Code</summary>

.. literalinclude:: {py_rel}
   :language: python

.. raw:: html

   </details>

   <a class="bencher-report-link"
      href="_reports/{stem}/{bench.bench_name}.html"
      target="_blank">Open report in new tab &#8599;</a>
   <div class="bencher-report-region">
   <div class="bencher-report-wrap">
   <iframe class="bencher-report"
           src="_reports/{stem}/{bench.bench_name}.html"
           scrolling="no" allowfullscreen
           style="width:100%; min-height:400px; border:none; overflow:hidden;">
   </iframe>
   </div>
   <div class="bencher-hscroll"><div class="bencher-hscroll-inner"></div></div>
   </div>
"""
    rst_path.write_text(rst_content, encoding="utf-8")

    return {
        "stem": stem,
        "title": title_text,
        "section_rel": str(rel.parent),
        "rst_rel": str(rel.with_suffix("").as_posix()),
        "bench_name": bench.bench_name,
        "exec_s": exec_elapsed,
        "thumb_s": thumb_elapsed,
    }


def _render_gallery_cards(examples: list[dict], href_fn, thumb_src_fn) -> list[str]:
    """Render gallery card HTML lines for a list of example metadata dicts."""
    lines = []
    for ex in sorted(examples, key=lambda e: e["stem"]):
        href = href_fn(ex)
        thumb_src = thumb_src_fn(ex)
        title = html.escape(ex["title"])
        lines.append(f'   <a class="gallery-card" href="{href}">')
        lines.append('     <div class="gallery-thumb-wrap">')
        lines.append(
            f'       <img class="gallery-thumb" src="{thumb_src}" loading="lazy" alt="{title}">'
        )
        lines.append("     </div>")
        lines.append(f'     <div class="gallery-card-title">{title}</div>')
        lines.append("   </a>")
    return lines


def _match_section(meta_section_rel, section_rel_path):
    """Check if a metadata entry belongs to a section (exact or directory-prefix match)."""
    meta_parts = Path(meta_section_rel).parts
    section_parts = Path(section_rel_path).parts
    return meta_parts[: len(section_parts)] == section_parts


def _group_by_subdir(examples, section_rel):
    """Group examples by sub-directory within a section.

    Returns a dict mapping sub-directory name (empty string for root) to example list,
    sorted with root first then alphabetically.
    """
    subgroups = {}
    for ex in examples:
        if ex["section_rel"] == section_rel:
            key = ""
        else:
            key = str(Path(ex["section_rel"]).relative_to(section_rel))
        subgroups.setdefault(key, []).append(ex)
    return dict(sorted(subgroups.items(), key=lambda kv: (kv[0] != "", kv[0])))


def _render_subgrouped_gallery(
    examples,
    section_rel,
    href_fn,
    thumb_src_fn,
    heading_tag="h3",
    heading_class="gallery-section-title",
):
    """Render gallery cards grouped by sub-directory with optional sub-headings."""
    lines = []
    subgroups = _group_by_subdir(examples, section_rel)
    for subdir, group_examples in subgroups.items():
        if subdir:
            sub_title = html.escape(subdir.replace("_", " ").title())
            lines.append(f'   <{heading_tag} class="{heading_class}">{sub_title}</{heading_tag}>')
        lines.append('   <div class="gallery-grid">')
        lines += _render_gallery_cards(group_examples, href_fn, thumb_src_fn)
        lines.append("   </div>")
    return lines


def generate_section_index(
    section_path: Path, section_title: str, section_metadata: list[dict], section_rel: str
):
    """Generate an index.rst for a docs section with a gallery grid and hidden toctree."""
    rst_files = sorted(section_path.rglob("*.rst"))
    rst_files = [f for f in rst_files if f.name != "index.rst"]

    if not rst_files:
        return

    toc_entries = [f"   {f.relative_to(section_path).with_suffix('')}" for f in rst_files]

    underline = "=" * len(section_title)

    lines = [
        section_title,
        underline,
        "",
        ".. toctree::",
        "   :hidden:",
        "   :maxdepth: 1",
        "",
        "\n".join(toc_entries),
        "",
    ]

    if section_metadata:
        # Compute relative path from section index to _thumbs root
        depth = len(section_path.relative_to(META_DOCS_DIR).parts)
        thumbs_prefix = "/".join([".."] * depth) + "/_thumbs"
        lines += [
            ".. raw:: html",
            "",
            '   <div class="gallery-container">',
        ]
        lines += _render_subgrouped_gallery(
            section_metadata,
            section_rel,
            href_fn=lambda ex: f"{Path(ex['rst_rel']).relative_to(section_rel)}.html",
            thumb_src_fn=lambda ex, pfx=thumbs_prefix: (
                f"{pfx}/{ex['section_rel']}/{ex['stem']}.png"
            ),
        )
        lines += [
            "   </div>",
            "",
        ]

    index_path = section_path / "index.rst"
    index_path.write_text("\n".join(lines), encoding="utf-8")


# Gallery hierarchy: list of (group_title | None, [(section_title, rel_path), ...])
# Groups with title=None have their sections rendered at the top level.
SECTION_GROUPS = [
    (
        "0 Float Inputs",
        [
            ("No Repeats", "0_float/no_repeats"),
            ("Repeated", "0_float/with_repeats"),
            ("Over Time", "0_float/over_time"),
            ("Over Time + Repeated", "0_float/over_time_repeats"),
        ],
    ),
    (
        "1 Float Input",
        [
            ("No Repeats", "1_float/no_repeats"),
            ("Repeated", "1_float/with_repeats"),
            ("Over Time", "1_float/over_time"),
            ("Over Time + Repeated", "1_float/over_time_repeats"),
        ],
    ),
    (
        "2 Float Inputs",
        [
            ("No Repeats", "2_float/no_repeats"),
            ("Repeated", "2_float/with_repeats"),
            ("Over Time", "2_float/over_time"),
        ],
    ),
    (
        "3 Float Inputs",
        [
            ("No Repeats", "3_float/no_repeats"),
            ("Repeated", "3_float/with_repeats"),
            ("Over Time", "3_float/over_time"),
        ],
    ),
    (
        "Optimisation",
        [
            ("Basic", "optimization"),
            ("Over Time", "optimization_over_time"),
            ("Aggregated", "optimization_aggregated"),
        ],
    ),
    (
        None,
        [
            ("Result Types", "result_types"),
            ("Plot Types", "plot_types"),
            ("Bool Plot Types", "bool_plot_types"),
            ("Subsampling Divisions System", "levels"),
            ("Sampling Strategies", "sampling"),
            ("Composable Containers", "composable_containers"),
            ("Container Tab Layouts", "container_tabs"),
            ("Aggregation", "aggregation"),
            ("Constant Variables", "const_vars"),
            ("Statistics", "statistics"),
            ("Workflows", "workflows"),
            ("YAML Sweeps", "yaml"),
            ("Cartesian Animation", "cartesian_animation"),
            ("Advanced Patterns", "advanced"),
            ("Regression Detection", "regression"),
            ("Performance", "performance"),
            ("Publishing", "publishing"),
            ("Rerun Integration", "rerun"),
        ],
    ),
]


def _flat_sections():
    """Yield (section_title, rel_path) pairs from SECTION_GROUPS."""
    for _group_title, sections in SECTION_GROUPS:
        yield from sections


# Flat view used by section index generation and toctree.
# Keyed by rel_path (unique) rather than title (may repeat across groups).
SECTIONS = {rel_path: title for title, rel_path in _flat_sections()}


def generate_gallery_page(examples_metadata: list[dict], docs_dir: Path):
    """Generate a single gallery.rst page with PNG thumbnail cards grouped by section."""
    from collections import OrderedDict

    # Build lookup: rel_path -> {title, rel_path, examples}
    # Keyed by rel_path (unique) rather than title (may repeat across groups).
    section_lookup = OrderedDict()
    for title, rel_path in _flat_sections():
        section_lookup[rel_path] = {"title": title, "rel_path": rel_path, "examples": []}

    for meta in examples_metadata:
        for _title, rel_path in _flat_sections():
            if _match_section(meta["section_rel"], rel_path):
                section_lookup[rel_path]["examples"].append(meta)
                break

    lines = [
        "Gallery Overview",
        "================",
        "",
        (
            "All examples at a glance. Click any card to see the full example"
            " with source code and interactive report."
        ),
        "",
        ".. raw:: html",
        "",
        '   <div class="gallery-container">',
    ]

    for group_title, sections in SECTION_GROUPS:
        # Check if this group has any examples at all
        group_has_examples = any(section_lookup[rel_path]["examples"] for _, rel_path in sections)
        if not group_has_examples:
            continue

        # Emit group heading if present
        if group_title:
            lines.append(f'   <h2 class="gallery-group-title">{html.escape(group_title)}</h2>')

        section_tag = "h4" if group_title else "h3"
        subsection_tag = "h5" if group_title else "h4"

        for section_title, rel_path in sections:
            info = section_lookup[rel_path]
            if not info["examples"]:
                continue
            lines.append(
                f'   <{section_tag} class="gallery-section-title">'
                f"{html.escape(section_title)}</{section_tag}>"
            )
            lines += _render_subgrouped_gallery(
                info["examples"],
                info["rel_path"],
                href_fn=lambda ex: f"{ex['rst_rel']}.html",
                thumb_src_fn=lambda ex: f"_thumbs/{ex['section_rel']}/{ex['stem']}.png",
                heading_tag=subsection_tag,
                heading_class="gallery-subsection-title",
            )

    lines.append("   </div>")
    lines.append("")

    gallery_path = docs_dir / "gallery.rst"
    gallery_path.write_text("\n".join(lines), encoding="utf-8")
    print(f"  Generated gallery page: {gallery_path}")


def _print_timing_summary(examples_metadata: list[dict]) -> None:
    """Print a summary of example execution and thumbnail times, sorted by total duration."""
    timed = [
        (m.get("exec_s", 0) + m.get("thumb_s", 0), m) for m in examples_metadata if "exec_s" in m
    ]
    timed.sort(key=lambda x: x[0], reverse=True)
    total_exec = sum(m["exec_s"] for m in examples_metadata if "exec_s" in m)
    total_thumb = sum(m["thumb_s"] for m in examples_metadata if "thumb_s" in m)
    print(f"\n{'=' * 70}")
    print(f"Timing summary: {len(timed)} examples")
    print(f"  Total execution+save: {total_exec:.1f}s")
    print(f"  Total thumbnails:     {total_thumb:.1f}s")
    print(f"  Combined:             {total_exec + total_thumb:.1f}s")
    print("\nTop 15 slowest (exec+thumb):")
    for total_s, m in timed[:15]:
        print(
            f"  {total_s:6.2f}s  (exec {m['exec_s']:.1f}s + thumb {m['thumb_s']:.1f}s)  {m['stem']}"
        )
    print(f"{'=' * 70}\n")


def generate_all(only: list[str] | None = None, force_skip_thumbnails: bool = False) -> list[Path]:
    """Generate Python examples, run them, save HTML reports, generate RST for docs.

    Args:
        only: optional list of example stems (substring match). When set, only
            matching examples are regenerated in place — output directories are
            not cleaned and section/gallery index pages are left untouched.
        force_skip_thumbnails: skip thumbnail screenshots even if a browser is
            available.
    """
    t_all_start = time.perf_counter()
    # Clean output directories (full regeneration only)
    if not only:
        if META_DOCS_DIR.exists():
            shutil.rmtree(META_DOCS_DIR)
        META_DOCS_DIR.mkdir(parents=True, exist_ok=True)

        if REPORTS_EXTRA_DIR.exists():
            shutil.rmtree(REPORTS_EXTRA_DIR)
        REPORTS_EXTRA_DIR.mkdir(parents=True, exist_ok=True)

    # Phase 1: Generate Python example files
    generate_python_files()

    # Phase 2: Run each Python file, save HTML report, generate RST
    examples_metadata = []
    py_files = sorted(GENERATED_DIR.rglob("*.py"))
    if only:
        py_files = [f for f in py_files if any(pat in f.stem for pat in only)]
        print(f"--only matched {len(py_files)} example(s): {[f.stem for f in py_files]}")

    # Create a shared playwright browser for thumbnail screenshots
    skip_thumbnails = force_skip_thumbnails
    pw_context = None
    browser = None
    page = None
    if not skip_thumbnails:
        try:
            from playwright.sync_api import sync_playwright  # pylint: disable=import-error

            pw_context = sync_playwright().start()
            browser = pw_context.chromium.launch(headless=True)
            page = browser.new_page(
                viewport={"width": 1200, "height": 900},
                device_scale_factor=THUMB_SCALE,
            )
            print("Started headless Chromium for thumbnail screenshots")
        except Exception as e:  # pylint: disable=broad-except  # noqa: BLE001
            skip_thumbnails = True
            print(f"WARNING: Could not start browser for thumbnails: {e}")

    try:
        for py_file in py_files:
            if py_file.name == "__init__.py":
                continue
            meta = run_example_and_save(
                py_file,
                META_DOCS_DIR,
                GENERATED_DIR,
                page=page,
                skip_thumbnails=skip_thumbnails,
            )
            if meta:
                examples_metadata.append(meta)
    finally:
        if browser is not None:
            browser.close()
        if pw_context is not None:
            pw_context.stop()
            print("Closed headless Chromium")

    if only:
        # Subset regeneration: leave existing section/gallery index pages alone.
        _print_timing_summary(examples_metadata)
        print(f"Total generate_all() time: {time.perf_counter() - t_all_start:.1f}s")
        return sorted(META_DOCS_DIR.rglob("*.rst"))

    # Phase 3: Generate section index files
    meta_by_section = {}
    for meta in examples_metadata:
        for rel_path in SECTIONS:
            if _match_section(meta["section_rel"], rel_path):
                meta_by_section.setdefault(rel_path, []).append(meta)
                break

    for rel_path, title in SECTIONS.items():
        section_dir = META_DOCS_DIR / rel_path
        if section_dir.exists():
            generate_section_index(section_dir, title, meta_by_section.get(rel_path, []), rel_path)

    # Generate group index pages for hierarchical groups
    for group_title, sections in SECTION_GROUPS:
        if group_title is None:
            continue

        group_slug = re.sub(r"[^a-z0-9]+", "_", group_title.lower()).strip("_")
        group_index_dir = META_DOCS_DIR / group_slug
        group_index_dir.mkdir(parents=True, exist_ok=True)

        # Build toctree entries (relative from group index dir)
        toc_entries = []
        for _sec_title, rel_path in sections:
            section_dir = META_DOCS_DIR / rel_path
            if (section_dir / "index.rst").exists():
                toc_entries.append(f"   ../{rel_path}/index")
        if not toc_entries:
            continue

        underline = "=" * len(group_title)
        # Thumbs path relative from the group index directory
        thumbs_prefix = "../_thumbs"

        lines = [
            group_title,
            underline,
            "",
            ".. toctree::",
            "   :hidden:",
            "   :maxdepth: 1",
            "",
            "\n".join(toc_entries),
            "",
        ]

        # Add gallery cards grouped by subsection
        group_examples = []
        for _sec_title, rel_path in sections:
            group_examples.extend(meta_by_section.get(rel_path, []))

        if group_examples:
            lines += [
                ".. raw:: html",
                "",
                '   <div class="gallery-container">',
            ]
            for sec_title, rel_path in sections:
                sec_examples = meta_by_section.get(rel_path, [])
                if not sec_examples:
                    continue
                lines.append(f'   <h3 class="gallery-section-title">{html.escape(sec_title)}</h3>')
                lines.append('   <div class="gallery-grid">')
                lines += _render_gallery_cards(
                    sec_examples,
                    href_fn=lambda ex: f"../{ex['rst_rel']}.html",
                    thumb_src_fn=lambda ex, pfx=thumbs_prefix: (
                        f"{pfx}/{ex['section_rel']}/{ex['stem']}.png"
                    ),
                )
                lines.append("   </div>")
            lines += [
                "   </div>",
                "",
            ]

        (group_index_dir / "index.rst").write_text("\n".join(lines), encoding="utf-8")

    # Phase 4: Generate gallery overview page
    generate_gallery_page(examples_metadata, META_DOCS_DIR)

    # Standalone scorecard example (embedded by docs/scorecard.md).
    generate_scorecard_example()

    # Generate top-level meta index with hierarchy
    meta_index_entries = []
    used_paths = set()
    for group_title, sections in SECTION_GROUPS:
        if group_title:
            group_slug = re.sub(r"[^a-z0-9]+", "_", group_title.lower()).strip("_")
            group_index = META_DOCS_DIR / group_slug / "index.rst"
            if group_index.exists():
                meta_index_entries.append(f"   {group_slug}/index")
                for _, rel_path in sections:
                    used_paths.add(rel_path)
        else:
            for _, rel_path in sections:
                section_dir = META_DOCS_DIR / rel_path
                if (section_dir / "index.rst").exists() and rel_path not in used_paths:
                    meta_index_entries.append(f"   {rel_path}/index")
                    used_paths.add(rel_path)

    entries_str = "\n".join(meta_index_entries)
    meta_index = f"""Reference Gallery
=================

.. toctree::
   :maxdepth: 2

   gallery
{entries_str}
"""
    (META_DOCS_DIR / "index.rst").write_text(meta_index, encoding="utf-8")

    _print_timing_summary(examples_metadata)
    print(f"Total generate_all() time: {time.perf_counter() - t_all_start:.1f}s")

    return sorted(META_DOCS_DIR.rglob("*.rst"))


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Generate example docs pages and reports")
    parser.add_argument(
        "--only",
        type=str,
        default=None,
        help="Comma-separated example stems (substring match) to regenerate in place",
    )
    parser.add_argument(
        "--skip-thumbnails",
        action="store_true",
        help="Skip thumbnail screenshots",
    )
    cli_args = parser.parse_args()
    generate_all(
        only=[s.strip() for s in cli_args.only.split(",")] if cli_args.only else None,
        force_skip_thumbnails=cli_args.skip_thumbnails,
    )
