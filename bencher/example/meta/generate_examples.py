"""Generate Python example files, run them, save HTML reports, and generate RST for docs."""

import ast
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


def _create_driver():
    """Create a reusable headless Firefox driver for thumbnail screenshots."""
    from selenium import webdriver
    from selenium.webdriver.firefox.options import Options

    options = Options()
    options.add_argument("--headless")
    driver = webdriver.Firefox(options=options)
    driver.set_window_size(1200, 900)
    return driver


def _take_thumbnail(
    html_path: Path,
    thumb_path: Path,
    driver=None,
    width: int = 1200,
    height: int = 900,
    thumb_width: int = 480,
) -> None:
    """Screenshot an HTML report and save as a resized PNG thumbnail.

    Uses the provided driver if given; otherwise creates a temporary one.
    """
    from selenium import webdriver
    from selenium.webdriver.firefox.options import Options
    from selenium.webdriver.support.ui import WebDriverWait

    def _screenshot_with(drv: webdriver.Firefox) -> bytes:
        drv.set_window_size(width, height)
        drv.get(html_path.resolve().as_uri())
        WebDriverWait(drv, 10).until(
            lambda d: d.execute_script("return document.readyState") == "complete"
        )
        return drv.get_screenshot_as_png()

    if driver is not None:
        png_data = _screenshot_with(driver)
        _resize_and_save_png(png_data, thumb_path, thumb_width)
        return

    options = Options()
    options.add_argument("--headless")
    tmp_driver = webdriver.Firefox(options=options)
    try:
        png_data = _screenshot_with(tmp_driver)
        _resize_and_save_png(png_data, thumb_path, thumb_width)
    finally:
        tmp_driver.quit()


def generate_python_files():
    """Phase 1: Run meta generators to produce Python example files."""
    if GENERATED_DIR.exists():
        shutil.rmtree(GENERATED_DIR)
    GENERATED_DIR.mkdir(parents=True, exist_ok=True)

    from bencher.example.meta.generate_meta import example_meta
    from bencher.example.meta.generate_meta_const_vars import example_meta_const_vars
    from bencher.example.meta.generate_meta_optimization import example_meta_optimization
    from bencher.example.meta.generate_meta_plot_types import example_meta_plot_types
    from bencher.example.meta.generate_meta_result_types import example_meta_result_types
    from bencher.example.meta.generate_meta_sampling import example_meta_sampling
    from bencher.example.meta.generate_meta_statistics import example_meta_statistics

    example_meta()
    example_meta_result_types()
    example_meta_plot_types()
    example_meta_sampling()
    example_meta_statistics()
    example_meta_const_vars()
    example_meta_optimization()

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


def run_example_and_save(py_file: Path, docs_dir: Path, generated_dir: Path, driver=None):
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
        _take_thumbnail(Path(report_path), thumb_path, driver=driver)
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


def generate_section_index(section_path: Path, section_title: str):
    """Generate an index.rst for a docs section with a toctree."""
    rst_files = sorted(section_path.rglob("*.rst"))
    rst_files = [f for f in rst_files if f.name != "index.rst"]

    if not rst_files:
        return

    entries = []
    for f in rst_files:
        rel = f.relative_to(section_path).with_suffix("")
        entries.append(f"   {rel}")

    underline = "=" * len(section_title)
    entries_str = "\n".join(entries)
    content = f"""{section_title}
{underline}

.. toctree::
   :maxdepth: 1

{entries_str}
"""
    index_path = section_path / "index.rst"
    index_path.write_text(content, encoding="utf-8")


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
    "Result Types: ResultVar": "result_types/result_var",
    "Result Types: ResultBool": "result_types/result_bool",
    "Result Types: ResultVec": "result_types/result_vec",
    "Result Types: ResultString": "result_types/result_string",
    "Result Types: ResultPath": "result_types/result_path",
    "Result Types: ResultDataSet": "result_types/result_dataset",
    "Plot Types": "plot_types",
    "Optimization": "optimization",
    "Sampling Strategies": "sampling",
    "Constant Variables": "const_vars",
    "Statistics": "statistics",
}


def generate_gallery_page(examples_metadata: list[dict], docs_dir: Path):
    """Generate a single gallery.rst page with PNG thumbnail cards grouped by section."""
    from collections import OrderedDict

    grouped = OrderedDict()
    for title, rel_path in SECTIONS.items():
        grouped[title] = {"rel_path": rel_path, "examples": []}

    for meta in examples_metadata:
        for title, rel_path in SECTIONS.items():
            if meta["section_rel"] == rel_path:
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
        lines.append(f'   <h3 class="gallery-section-title">{section_title}</h3>')
        lines.append('   <div class="gallery-grid">')
        for ex in info["examples"]:
            href = f"{ex['rst_rel']}.html"
            thumb_src = f"_thumbs/{ex['section_rel']}/{ex['stem']}.png"
            lines.append(f'   <a class="gallery-card" href="{href}">')
            lines.append('     <div class="gallery-thumb-wrap">')
            lines.append(
                f'       <img class="gallery-thumb" src="{thumb_src}"'
                f' loading="lazy" alt="{ex["title"]}">'
            )
            lines.append("     </div>")
            lines.append(f'     <div class="gallery-card-title">{ex["title"]}</div>')
            lines.append("   </a>")
        lines.append("   </div>")

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

    # Create a shared browser driver for thumbnail screenshots
    driver = None
    try:
        driver = _create_driver()
        print("Started headless Firefox for thumbnail screenshots")
    except Exception as e:  # pylint: disable=broad-except
        print(f"WARNING: Could not start Firefox for thumbnails: {e}")

    try:
        for py_file in py_files:
            if py_file.name == "__init__.py":
                continue
            meta = run_example_and_save(py_file, META_DOCS_DIR, GENERATED_DIR, driver=driver)
            if meta:
                examples_metadata.append(meta)
    finally:
        if driver is not None:
            driver.quit()
            print("Closed headless Firefox")

    # Phase 3: Generate section index files
    for title, rel_path in SECTIONS.items():
        section_dir = META_DOCS_DIR / rel_path
        if section_dir.exists():
            generate_section_index(section_dir, title)

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
