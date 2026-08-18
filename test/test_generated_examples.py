"""Test that all generated meta examples run without crashing."""

import importlib
from pathlib import Path

import pytest

import bencher as bn

GENERATED_DIR = Path("bencher/example/generated")


def _discover_examples():
    """Discover all generated example Python files."""
    if not GENERATED_DIR.exists():
        return []
    return [f for f in sorted(GENERATED_DIR.rglob("*.py")) if f.name != "__init__.py"]


_examples = _discover_examples()
if not _examples:
    pytest.skip(
        "No generated examples found; run `pixi run generate-examples` first",
        allow_module_level=True,
    )


def test_generated_example_filenames_globally_unique():
    """Every generated example basename must be unique across the whole tree.

    The doc builder uses basenames as RST page stems and thumbnail ids, so a
    duplicate basename in a different subdirectory silently shadows a page.
    """
    generated_dir = Path(__file__).parent.parent / "bencher" / "example" / "generated"
    basenames = [p.name for p in generated_dir.rglob("*.py") if p.name != "__init__.py"]
    duplicates = sorted({b for b in basenames if basenames.count(b) > 1})
    assert not duplicates, f"Duplicate generated example filenames: {duplicates}"


@pytest.mark.parametrize(
    "example_path",
    _examples,
    ids=lambda p: str(p.relative_to(GENERATED_DIR)),
)
def test_generated_example(example_path):
    """Run a generated example. Success = no exception."""
    rel = example_path.relative_to(GENERATED_DIR).with_suffix("")
    module_path = ".".join(("bencher.example.generated", *rel.parts))
    mod = importlib.import_module(module_path)

    # Find the example_* function
    example_fns = [v for k, v in vars(mod).items() if k.startswith("example_") and callable(v)]
    assert example_fns, f"No example_* function found in {example_path}"

    run_cfg = bn.BenchRunCfg()
    run_cfg.execution.subsampling_divisions = 2
    run_cfg.execution.repeats = 2
    result = example_fns[0](run_cfg)
    assert result is not None
