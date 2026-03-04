"""Test that all generated meta examples run without crashing."""

import importlib.util
import sys
from pathlib import Path

import pytest

import bencher as bch


GENERATED_DIR = Path("bencher/example/meta/generated")


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
    rel = example_path.relative_to(GENERATED_DIR)
    module_name = f"test_generated.{rel.with_suffix('').as_posix().replace('/', '.')}"
    spec = importlib.util.spec_from_file_location(module_name, example_path)
    assert spec is not None and spec.loader is not None, f"Could not load {example_path}"
    mod = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = mod
    spec.loader.exec_module(mod)

    # Find the example_* function
    example_fns = [v for k, v in vars(mod).items() if k.startswith("example_") and callable(v)]
    assert example_fns, f"No example_* function found in {example_path}"

    run_cfg = bch.BenchRunCfg()
    run_cfg.level = 2
    run_cfg.repeats = 1
    result = example_fns[0](run_cfg)
    assert result is not None
