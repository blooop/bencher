"""Generate Python example files, run them, save HTML reports, and generate RST for docs."""

import ast
import html
import importlib
import io
import os
import shutil
import subprocess
from pathlib import Path

import bencher as bch


GENERATED_DIR = Path("bencher/example/generated")


def _extract_run_kwargs(py_file: Path) -> dict:
    """Extract kwargs from bch.run() call in __main__ block."""
    source = py_file.read_text()
    tree = ast.parse(source)
    for node in ast.walk(tree):
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == "run"
            and isinstance(node.func.value, ast.Name)
            and node.func.value.id == "bch"
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


def _resize_and_save_png(png_data: bytes, thumb_path: Path, thumb_width: int = 480) -> None:
    """Resize screenshot PNG data to thumbnail width and save to disk."""
    from PIL import Image

    img = Image.open(io.BytesIO(png_data))
    ratio = thumb_width / img.width
    img = img.resize((thumb_width, int(img.height * ratio)), Image.Resampling.LANCZOS)
    thumb_path.parent.mkdir(parents=True, exist_ok=True)
    img.save(thumb_path)


def _take_thumbnail(
    html_path: Path,
    thumb_path: Path,
    page=None,
    width: int = 1200,
    height: int = 900,
    thumb_width: int = 480,
) -> None:
    """Screenshot an HTML report and save as a resized PNG thumbnail.

    Uses the provided playwright page if given; otherwise creates a temporary browser.
    """
    from playwright.sync_api import sync_playwright  # pylint: disable=import-error

    def _screenshot_with(pg) -> bytes:
        pg.set_viewport_size({"width": width, "height": height})
        pg.goto(html_path.resolve().as_uri(), wait_until="load", timeout=15000)
        # Brief pause for Bokeh/Panel JS to render plots after DOM load
        pg.wait_for_timeout(2000)
        return pg.screenshot()

    if page is not None:
        png_data = _screenshot_with(page)
        _resize_and_save_png(png_data, thumb_path, thumb_width)
        return

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        tmp_page = browser.new_page(viewport={"width": width, "height": height})
        try:
            png_data = _screenshot_with(tmp_page)
            _resize_and_save_png(png_data, thumb_path, thumb_width)
        finally:
            browser.close()


def generate_python_files():
    """Phase 1: Run meta generators to produce Python example files."""
    if GENERATED_DIR.exists():
        shutil.rmtree(GENERATED_DIR)
    GENERATED_DIR.mkdir(parents=True, exist_ok=True)

    from bencher.example.meta.generate_meta import example_meta
    from bencher.example.meta.generate_meta_advanced import example_meta_advanced
    from bencher.example.meta.generate_meta_bool_plot_types import example_meta_bool_plot_types
    from bencher.example.meta.generate_meta_composable import example_meta_composable
    from bencher.example.meta.generate_meta_const_vars import example_meta_const_vars
    from bencher.example.meta.generate_meta_image_video import example_meta_image_video
    from bencher.example.meta.generate_meta_optimization import example_meta_optimization
    from bencher.example.meta.generate_meta_plot_types import example_meta_plot_types
    from bencher.example.meta.generate_meta_result_types import example_meta_result_types
    from bencher.example.meta.generate_meta_sampling import example_meta_sampling
    from bencher.example.meta.generate_meta_statistics import example_meta_statistics
    from bencher.example.meta.generate_meta_workflows import example_meta_workflows

    example_meta()
    example_meta_result_types()
    example_meta_image_video()
    example_meta_composable()
    example_meta_plot_types()
    example_meta_sampling()
    example_meta_statistics()
    example_meta_const_vars()
    example_meta_optimization()
    example_meta_workflows()
    example_meta_advanced()
    example_meta_bool_plot_types()

    # Write __init__.py files so generated examples are importable
    for d in GENERATED_DIR.rglob("*"):
        if d.is_dir() and d.name != "__pycache__":
            init = d / "__init__.py"
            if not init.exists():
                init.touch()
    init = GENERATED_DIR / "__init__.py"
    if not init.exists():
        init.touch()

    # Format all generated files in a single pass
    if shutil.which("ruff"):
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


def run_example_and_save(py_file: Path, docs_dir: Path, generated_dir: Path, page=None):
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
    run_cfg = bch.BenchRunCfg()
    run_cfg.level = run_kwargs.get("level", 4)
    run_cfg.repeats = run_kwargs.get("repeats", 1)
    if "use_optuna" in run_kwargs:
        run_cfg.use_optuna = run_kwargs["use_optuna"]
    print(f"Running {py_file}...")
    bench = example_fn(run_cfg)

    # Save reports under _extra/ so html_extra_path copies them alongside built RST pages
    reports_output_dir = REPORTS_EXTRA_DIR / rel.parent
    reports_output_dir.mkdir(parents=True, exist_ok=True)
    report_dir = reports_output_dir / f"_reports/{stem}"
    report_path = bench.report.save(
        directory=str(report_dir),
        in_html_folder=False,
    )
    print(f"  Saved report to {report_path}")

    # Generate thumbnail screenshot
    thumb_path = THUMBS_EXTRA_DIR / rel.parent / f"{stem}.png"
    try:
        _take_thumbnail(Path(report_path), thumb_path, page=page)
        print(f"  Saved thumbnail to {thumb_path}")
    except Exception as e:  # pylint: disable=broad-except
        print(f"  WARNING: Failed to save thumbnail for {stem}: {e}")

    # Generate RST that shows source + embeds HTML report
    title_text = stem.replace("_", " ").title()
    underline = "=" * len(title_text)
    # Compute relative path from RST location to the Python source
    rst_path = output_dir / f"{stem}.rst"
    py_rel = os.path.relpath(py_file, rst_path.parent)

    rst_content = f"""{title_text}
{underline}

.. literalinclude:: {py_rel}
   :language: python

.. raw:: html

   <iframe src="_reports/{stem}/{bench.bench_name}.html"
           style="width:100%; height:800px; border:1px solid #ccc;">
   </iframe>
"""
    rst_path.write_text(rst_content, encoding="utf-8")

    return {
        "stem": stem,
        "title": title_text,
        "section_rel": str(rel.parent),
        "rst_rel": str(rel.with_suffix("").as_posix()),
        "bench_name": bench.bench_name,
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


SECTIONS = {
    "0 Float Inputs": "0_float/no_repeats",
    "0 Float Inputs (Repeated)": "0_float/with_repeats",
    "0 Float Inputs (Over Time)": "0_float/over_time",
    "1 Float Input": "1_float/no_repeats",
    "1 Float Input (Repeated)": "1_float/with_repeats",
    "1 Float Input (Over Time)": "1_float/over_time",
    "2 Float Inputs": "2_float/no_repeats",
    "2 Float Inputs (Repeated)": "2_float/with_repeats",
    "2 Float Inputs (Over Time)": "2_float/over_time",
    "3 Float Inputs": "3_float/no_repeats",
    "3 Float Inputs (Repeated)": "3_float/with_repeats",
    "3 Float Inputs (Over Time)": "3_float/over_time",
    "Result Types": "result_types",
    "Plot Types": "plot_types",
    "Bool Plot Types": "bool_plot_types",
    "Optimization": "optimization",
    "Sampling Strategies": "sampling",
    "Composable Containers": "composable_containers",
    "Constant Variables": "const_vars",
    "Statistics": "statistics",
    "Workflows": "workflows",
    "Advanced Patterns": "advanced",
}


def generate_gallery_page(examples_metadata: list[dict], docs_dir: Path):
    """Generate a single gallery.rst page with PNG thumbnail cards grouped by section."""
    from collections import OrderedDict

    grouped = OrderedDict()
    for title, rel_path in SECTIONS.items():
        grouped[title] = {"rel_path": rel_path, "examples": []}

    for meta in examples_metadata:
        for title, rel_path in SECTIONS.items():
            if _match_section(meta["section_rel"], rel_path):
                grouped[title]["examples"].append(meta)
                break

    lines = [
        "Gallery Overview",
        "================",
        "",
        "All examples at a glance. Click any card to see the full example"
        " with source code and interactive report.",
        "",
        ".. raw:: html",
        "",
        '   <div class="gallery-container">',
    ]

    for section_title, info in grouped.items():
        if not info["examples"]:
            continue
        lines.append(f'   <h3 class="gallery-section-title">{html.escape(section_title)}</h3>')
        lines += _render_subgrouped_gallery(
            info["examples"],
            info["rel_path"],
            href_fn=lambda ex: f"{ex['rst_rel']}.html",
            thumb_src_fn=lambda ex: f"_thumbs/{ex['section_rel']}/{ex['stem']}.png",
            heading_tag="h4",
            heading_class="gallery-subsection-title",
        )

    lines.append("   </div>")
    lines.append("")

    gallery_path = docs_dir / "gallery.rst"
    gallery_path.write_text("\n".join(lines), encoding="utf-8")
    print(f"  Generated gallery page: {gallery_path}")


def generate_all() -> list[Path]:
    """Generate Python examples, run them, save HTML reports, generate RST for docs."""
    # Clean output directories
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

    # Create a shared playwright browser for thumbnail screenshots
    pw_context = None
    browser = None
    page = None
    try:
        from playwright.sync_api import sync_playwright  # pylint: disable=import-error

        pw_context = sync_playwright().start()
        browser = pw_context.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1200, "height": 900})
        print("Started headless Chromium for thumbnail screenshots")
    except Exception as e:  # pylint: disable=broad-except
        print(f"WARNING: Could not start browser for thumbnails: {e}")

    try:
        for py_file in py_files:
            if py_file.name == "__init__.py":
                continue
            meta = run_example_and_save(py_file, META_DOCS_DIR, GENERATED_DIR, page=page)
            if meta:
                examples_metadata.append(meta)
    finally:
        if browser is not None:
            browser.close()
        if pw_context is not None:
            pw_context.stop()
            print("Closed headless Chromium")

    # Phase 3: Generate section index files
    meta_by_section = {}
    for meta in examples_metadata:
        for _title, rel_path in SECTIONS.items():
            if _match_section(meta["section_rel"], rel_path):
                meta_by_section.setdefault(rel_path, []).append(meta)
                break

    for title, rel_path in SECTIONS.items():
        section_dir = META_DOCS_DIR / rel_path
        if section_dir.exists():
            generate_section_index(section_dir, title, meta_by_section.get(rel_path, []), rel_path)

    # Phase 4: Generate gallery overview page
    generate_gallery_page(examples_metadata, META_DOCS_DIR)

    # Generate top-level meta index
    meta_index_entries = []
    for rel_path in SECTIONS.values():
        section_dir = META_DOCS_DIR / rel_path
        if (section_dir / "index.rst").exists():
            meta_index_entries.append(f"   {rel_path}/index")

    entries_str = "\n".join(meta_index_entries)
    meta_index = f"""Reference Gallery
=================

.. toctree::
   :maxdepth: 2

   gallery
{entries_str}
"""
    (META_DOCS_DIR / "index.rst").write_text(meta_index, encoding="utf-8")

    return sorted(META_DOCS_DIR.rglob("*.rst"))


if __name__ == "__main__":
    generate_all()
