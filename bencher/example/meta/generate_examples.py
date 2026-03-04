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
    """Run a Python example, save HTML report, write RST doc page."""
    rel = py_file.relative_to(generated_dir)
    output_dir = docs_dir / rel.parent
    output_dir.mkdir(parents=True, exist_ok=True)
    stem = py_file.stem

    mod = _import_example_module(py_file)
    example_fn = _find_example_function(mod)
    if example_fn is None:
        print(f"WARNING: No example_* function found in {py_file}, skipping")
        return

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
    py_files = sorted(GENERATED_DIR.rglob("*.py"))
    for py_file in py_files:
        if py_file.name == "__init__.py":
            continue
        run_example_and_save(py_file, META_DOCS_DIR, GENERATED_DIR)

    # Phase 3: Generate section index files
    for title, rel_path in SECTIONS.items():
        section_dir = META_DOCS_DIR / rel_path
        if section_dir.exists():
            generate_section_index(section_dir, title)

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

{entries_str}
"""
    (META_DOCS_DIR / "index.rst").write_text(meta_index, encoding="utf-8")

    return sorted(META_DOCS_DIR.rglob("*.rst"))


if __name__ == "__main__":
    generate_all()
