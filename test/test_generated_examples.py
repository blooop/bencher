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
    run_cfg.level = 2
    run_cfg.repeats = 1
    result = example_fns[0](run_cfg)
    assert result is not None
