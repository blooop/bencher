"""Generate Python example files, run them, save HTML reports, and generate RST for docs."""

import importlib
import os
import shutil
import subprocess
from pathlib import Path

import bencher as bch


GENERATED_DIR = Path("bencher/example/meta/generated")
META_DOCS_DIR = Path("docs/reference/meta")
# Reports go under docs/_extra/ so html_extra_path copies them to match the built output structure
REPORTS_EXTRA_DIR = Path("docs/_extra/reference/meta")


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
    module_path = ".".join(("bencher.example.meta.generated", *rel.parts))
    return importlib.import_module(module_path)


def _find_example_function(mod):
    """Find the example_* function in a module."""
    for name, obj in vars(mod).items():
        if name.startswith("example_") and callable(obj):
            return obj
    return None


def run_example_and_save(py_file: Path, docs_dir: Path, generated_dir: Path):
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

    run_cfg = bch.BenchRunCfg()
    run_cfg.level = 4
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


SECTION_ICONS = {
    "0_float": (
        "#4CAF50",
        '<path d="M3 17h2v-7H3v7zm4 0h2V7H7v10zm4 0h2v-4h-2v4zm4 0h2v-9h-2v9zm4 0h2V3h-2v14z"/>',
    ),
    "1_float": (
        "#2196F3",
        '<path d="M3.5 18.5l6-6 4 4L22 6.92 20.59 5.5l-7.09 8.07-4-4L2 17z"/>',
    ),
    "2_float": (
        "#9C27B0",
        '<path d="M19 3H5c-1.1 0-2 .9-2 2v14c0 1.1.9 2 2 2h14c1.1 0 2-.9'
        ' 2-2V5c0-1.1-.9-2-2-2zM9 17H7v-7h2v7zm4 0h-2V7h2v10zm4 0h-2v-4h2v4z"/>',
    ),
    "3_float": (
        "#FF5722",
        '<circle cx="7" cy="14" r="3"/><circle cx="11" cy="6" r="3"/><circle cx="16.6" '
        'cy="17.6" r="3"/>',
    ),
    "result_types": (
        "#FF9800",
        '<path d="M19 3H5c-1.1 0-2 .9-2 2v14c0 1.1.9 2 2 2h14c1.1 0 2-.9'
        ' 2-2V5c0-1.1-.9-2-2-2zm-5 14H7v-2h7v2zm3-4H7v-2h10v2zm0-4H7V7h10v2z"/>',
    ),
    "plot_types": (
        "#E91E63",
        '<path d="M5 9.2h3V19H5V9.2zM10.6 5h2.8v14h-2.8V5zm5.6 8H19v6h-2.8v-6z"/>',
    ),
    "optimization": (
        "#00BCD4",
        '<circle cx="12" cy="12" r="3.2"/><path d="M9 2L7.2 4.8l2.8 2.8L7.2'
        ' 10.4 9 13.2l3-3 3 3 1.8-2.8-2.8-2.8 2.8-2.8L15 2l-3 3z"/>',
    ),
    "sampling": (
        "#795548",
        '<circle cx="6" cy="18" r="2"/><circle cx="12" cy="10" r="2"/><circle cx="18"'
        ' cy="16" r="2"/><circle cx="8" cy="6" r="2"/><circle cx="16" cy="6" r="2"/>',
    ),
    "const_vars": (
        "#607D8B",
        '<path d="M14 4l2.29 2.29-2.88 2.88 1.42 1.42 2.88-2.88L20 10V4h-6zm-4'
        ' 0H4v6l2.29-2.29 4.71 4.7V20h2v-8.41l-5.29-5.3z"/>',
    ),
    "statistics": (
        "#3F51B5",
        '<path d="M2 20h20v-2H2v2zM4 14c.6-3.3 3.5-5.5 6.8-5 2.3.4 4.2 2.2'
        ' 4.6 4.5.1.5.1 1 .1 1.5h4c0-5.5-4.5-10-10-10C4.5 5 .3 9.6 0 14h4z"/>',
    ),
}


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


def _icon_for_section(section_rel: str):
    """Return (color, svg_path_data) for a section by matching its path prefix."""
    for prefix, val in SECTION_ICONS.items():
        if section_rel.startswith(prefix):
            return val
    return ("#9E9E9E", '<circle cx="12" cy="12" r="6"/>')


def generate_gallery_page(examples_metadata: list[dict], docs_dir: Path):
    """Generate a single gallery.rst page with a CSS grid of cards grouped by section."""
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
        "All examples at a glance. Click any card to see the full example with source and report.",
        "",
        ".. raw:: html",
        "",
        '   <div class="gallery-container">',
    ]

    for section_title, info in grouped.items():
        if not info["examples"]:
            continue
        color, svg_path = _icon_for_section(info["rel_path"])
        lines.append(
            f'   <h3 class="gallery-section-title"'
            f' style="border-left: 4px solid {color};">{section_title}</h3>'
        )
        lines.append('   <div class="gallery-grid">')
        for ex in info["examples"]:
            href = f"{ex['rst_rel']}.html"
            subtitle = info["rel_path"].replace("/", " / ").replace("_", " ").title()
            lines.append(f'   <a class="gallery-card" href="{href}">')
            lines.append('     <div class="gallery-card-icon">')
            lines.append(
                f'       <svg viewBox="0 0 24 24" width="48" height="48"'
                f' fill="{color}">{svg_path}</svg>'
            )
            lines.append("     </div>")
            lines.append(f'     <div class="gallery-card-title">{ex["title"]}</div>')
            lines.append(f'     <div class="gallery-card-subtitle">{subtitle}</div>')
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
    for py_file in py_files:
        if py_file.name == "__init__.py":
            continue
        meta = run_example_and_save(py_file, META_DOCS_DIR, GENERATED_DIR)
        if meta:
            examples_metadata.append(meta)

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
