"""Layer B: exercise the collect/render split across diverse result types.

The single example in ``test_render.py`` only covers a trivial float result. This
module reuses the generated *result-type* example corpus — every ResultImage /
ResultVideo / ResultPath / ResultDataset / ResultString / ResultBool / ResultVec /
ResultVar shape — and pushes each result through the split pipeline:

    plot_sweep -> save_result -> load_result -> render_report

asserting it produces a non-empty HTML report. This catches result types that
fail to pickle, or whose render relies on live state that did not survive
serialization.

The in-process round-trip above shares its serialize/render-from-loaded coverage
with the ``BENCHER_FORCE_SPLIT_RENDER`` suite run, but runs unconditionally in
normal CI and asserts on the rendered HTML directly. The final test additionally
covers the true *process boundary*: a clean interpreter rendering a media-backed
result via ``python -m bencher.render``, where the pickled result references media
files written to disk during collection.
"""

import importlib
import subprocess
import sys
from pathlib import Path

import pytest

import bencher as bn
from bencher import save_result, render_report

GENERATED_DIR = Path("bencher/example/generated")
RESULT_TYPES_DIR = GENERATED_DIR / "result_types"


def _discover(subdir: Path):
    if not subdir.exists():
        return []
    return [f for f in sorted(subdir.rglob("*.py")) if f.name != "__init__.py"]


_result_examples = _discover(RESULT_TYPES_DIR)
if not _result_examples:
    pytest.skip(
        "No generated result-type examples found; run `pixi run generate-examples` first",
        allow_module_level=True,
    )


def _run_example(example_path: Path) -> bn.Bench:
    """Import and run a generated example, returning its Bench (mirrors test_generated_examples)."""
    rel = example_path.relative_to(GENERATED_DIR).with_suffix("")
    module_path = ".".join(("bencher.example.generated", *rel.parts))
    mod = importlib.import_module(module_path)
    fns = [v for k, v in vars(mod).items() if k.startswith("example_") and callable(v)]
    assert fns, f"No example_* function found in {example_path}"

    run_cfg = bn.BenchRunCfg()
    run_cfg.subsampling_divisions = 2
    run_cfg.repeats = 2
    # Disable plotting on the run_cfg so the example's internal plot_sweep call
    # (auto_plot=None) defers to it and takes the collect path — no holoviews/panel
    # objects are built, so the result we pickle is the same clean artifact the real
    # collect/render split produces. Running the example with auto_plot=True instead
    # would cache plot accessors on the dataset that the split path never creates.
    run_cfg.auto_plot = False
    result = fns[0](run_cfg)
    assert result is not None, f"{example_path} returned None"
    assert isinstance(result, bn.Bench), f"{example_path} did not return a Bench"
    assert result.results, f"{example_path} produced no results"
    return result


@pytest.mark.parametrize(
    "example_path",
    _result_examples,
    ids=lambda p: str(p.relative_to(RESULT_TYPES_DIR)),
)
def test_split_render_roundtrip(example_path, tmp_path):
    """Every result type survives save -> load -> render to non-empty HTML."""
    bench = _run_example(example_path)
    res = bench.results[-1]

    path = save_result(res, tmp_path / "result.pkl")
    assert path.exists()

    out = render_report(path, tmp_path / "report")
    assert Path(out).exists()
    assert Path(out).stat().st_size > 0


def _first_example_under(name: str) -> Path | None:
    matches = [p for p in _result_examples if f"/{name}/" in str(p).replace("\\", "/")]
    return matches[0] if matches else None


def test_split_render_subprocess_media(tmp_path):
    """A clean subprocess renders a media-backed result via `python -m bencher.render`.

    The pickle data-sharing is exercised broadly and cheaply by the in-process
    round-trip above (every result type, image and video included). This single
    test covers the one thing in-process cannot: the genuine *process boundary*
    the feature exists for. Media results pickle file *paths*, so a fresh
    interpreter that never ran the sweep must still locate and render those files.
    One image example is enough to prove the production path end to end.
    """
    example_path = _first_example_under("result_image")
    if example_path is None:
        pytest.skip("No generated result_image example available")

    bench = _run_example(example_path)
    res = bench.results[-1]
    pkl = save_result(res, tmp_path / "result.pkl")
    out_dir = tmp_path / "report"

    proc = subprocess.run(
        [sys.executable, "-m", "bencher.render", str(pkl), str(out_dir)],
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0, f"render subprocess failed:\n{proc.stderr}"
    assert any(out_dir.rglob("*.html")), "subprocess produced no HTML report"
