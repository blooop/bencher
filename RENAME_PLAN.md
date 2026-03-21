# Plan: Rename `bencher` to `holobench` and `bch` to `hb`

## Context

The PyPI package is already published as `holobench` (`pip install holobench`), but the Python package directory is still `bencher/` and all code uses `import bencher as bch`. This creates a confusing disconnect where users install one name but import another. This rename aligns the code with the published package name.

## Key Decisions Needed

1. **Backwards-compat shim?** — Should we create a thin `bencher/__init__.py` that re-exports from `holobench` with a deprecation warning? Or clean break?
2. **GitHub repo name** — The repo is `blooop/bencher`. GitHub supports renaming with automatic redirects. This is a manual step in GitHub Settings, not a code change. URLs in pyproject.toml/README should be updated if/when the repo is renamed.
3. **ReadTheDocs** — `bencher.readthedocs.io` can be changed via RTD admin panel. External step.
4. **CHANGELOG history** — Historical references to `bch.run()` etc. should NOT be updated (they're accurate records of the API at that time). A new entry documents the rename.
5. **Class names stay** — `Bench`, `BenchRunner`, `BenchCfg`, `BenchResult` etc. are domain terms (benchmark) and stay unchanged.
6. **Cached data** — Cache dir is hardcoded `"cachedir/"`, not derived from package name. No breakage.

## Implementation Phases

### Phase 1: Directory rename (isolated commit for git rename detection)
- `git mv bencher/ holobench/`
- `git mv resource/bencher resource/holobench`
- Single commit, no content changes — maximizes `git log --follow` accuracy

### Phase 2: Update all `from bencher.` internal imports
Files in `holobench/` (core modules):
- `holobench/__init__.py` (~60 absolute imports from `bencher.*`)
- `holobench/bencher.py`, `bench_runner.py`, `bench_cfg.py`, `bench_report.py`, `run.py`, etc.
- All `from bencher.X import Y` → `from holobench.X import Y`

String literals with module paths (runtime breakage if missed):
- `holobench/class_enum.py:115` — `"bencher.class_enum"` (used by `importlib.import_module()`)
- `holobench/example/meta/generate_meta_plot_types.py` — `"bencher.example.meta.*"`
- `holobench/example/meta/generate_meta_statistics.py` — `"bencher.example.meta.*"`
- `holobench/example/meta/generate_meta_performance.py` — `importlib.resources.files("bencher.example")`
- `holobench/example/meta/generate_examples.py` — `Path("bencher/example/generated")` and `"bencher.example.generated"`

### Phase 3: Update `import bencher as bch` → `import holobench as hb` and `bch.` → `hb.`
- ~293 files (examples + tests) with `import bencher as bch`
- ~2,446 occurrences of `bch.` attribute access
- Bulk `sed` replacements:
  - `s/import bencher as bch/import holobench as hb/g`
  - `s/\bbch\./hb./g`
- **Gotcha**: `bch_fn` in `bench_runner.py` (4 occurrences) — uses underscore not dot, so `bch.` → `hb.` regex is safe. But if we also want to rename `bch_fn` → `hb_fn`, do it manually.

### Phase 4: Update meta generators (template strings that emit code)
- `holobench/example/meta/meta_generator_base.py:115` — `"import bencher as bch"` → `"import holobench as hb"`
- `holobench/example/meta/meta_generator_base.py` — all template `bch.` → `hb.`
- `holobench/example/meta/generate_meta.py` — INLINE_CLASSES dict has ~20 entries with `"imports": "import bencher as bch"` and `bch.*` in string templates
- `holobench/example/meta/generate_examples.py:28` — AST check `node.func.value.id == "bch"` → `"hb"`
- All other `generate_meta_*.py` files with embedded code strings

### Phase 5: Update build/config files
| File | Changes |
|------|---------|
| `pyproject.toml:89` | `include = ["bencher", ...]` → `["holobench", ...]` |
| `pyproject.toml:126-127` | `bencher/example/` paths → `holobench/example/` |
| `pyproject.toml:163,165` | `bencher/example/meta/` paths → `holobench/example/meta/` |
| `pyproject.toml:172-173` | demo paths |
| `pyproject.toml:179` | pylint ignore-paths |
| `pyproject.toml:29-31` | URLs (update if/when GitHub repo renamed) |
| `setup.py:4` | `package_name = "bencher"` → `"holobench"` |
| `setup.cfg` | `lib/bencher` → `lib/holobench` |
| `MANIFEST.in` | `bencher/` → `holobench/` |
| `docs/conf.py:15` | project name |
| `docs/conf.py:44` | `autoapi_dirs = ["../bencher"]` → `["../holobench"]` |
| `.readthedocs.yaml` | command paths |
| `CLAUDE.md` | All path refs and import examples |
| `AGENTS.md` | All bencher refs |
| `README.md` | Descriptions, badge URLs, example code |
| `docs/intro.md` | Import examples and references |

### Phase 6: Regenerate generated files
- Delete `holobench/example/generated/` contents (except `__init__.py`)
- Run `pixi run generate-examples` — templates now emit `import holobench as hb`

### Phase 7: Backwards-compat shim (CONFIRMED: yes)
Create minimal `bencher/__init__.py` at repo root:
```python
import warnings
warnings.warn(
    "The 'bencher' package has been renamed to 'holobench'. "
    "Please update: import holobench as hb",
    DeprecationWarning, stacklevel=2,
)
from holobench import *
```
Add `"bencher"` to hatch build include list: `include = ["holobench", "bencher", "CHANGELOG.md"]`. Remove after 2-3 releases.

### Phase 8: Rebuild and validate
1. `pixi install` to regenerate pixi.lock
2. `pixi run ci` — full pipeline (format, lint, test, coverage)
3. Fix any issues

## Gotchas and Failure Modes

| Risk | Detail | Mitigation |
|------|--------|------------|
| **Runtime string literals** | `importlib.import_module("bencher.class_enum")` and similar won't be caught by import-time tests | Grep for `"bencher.` and `'bencher.` in string literals; test `ExampleEnum.to_class()` |
| **Meta generator templates** | Code emitted as strings won't be caught by AST tools | Manual review of all `generate_meta*.py` and `meta_generator_base.py` |
| **AST check in generate_examples.py** | Checks `node.func.value.id == "bch"` — if any file still uses `bch`, it silently skips | Update check to `"hb"`, verify all generated files use new alias |
| **Partial word match** | `sed` replacing "bencher" could hit unexpected substrings | Verified: "bencher" doesn't appear as a substring of any other word in this codebase |
| **`bch_fn` variable** | 4 uses in bench_runner.py — not a module alias, keep as-is | Dot-based regex (`bch.` → `hb.`) is safe; `bch_fn` stays unchanged (user decision) |
| **Circular imports from shim** | If `bencher/__init__.py` does `from holobench import *` while any module still references `bencher` | Ensure ALL internal refs use `holobench` before adding shim |
| **pixi.lock** | Will be stale after pyproject.toml changes | Regenerate with `pixi install` |
| **git rename detection** | If content changes are mixed with directory rename, git may see delete+add instead of rename | Isolate directory rename in its own commit |
| **Existing user code** | Anyone with `import bencher as bch` in their projects | Backwards-compat shim (Phase 7) or document breaking change |
| **`test_bch_p.py`** | Test file named with "bch" | Rename to `test_hb_p.py` (user confirmed) |
| **`example_all.py` string `"bencher_examples"`** | User-facing label, not import path | Rename to `"holobench_examples"` for consistency |

## Verification
1. `pixi run ci` passes (format, lint, test, coverage)
2. `pixi run generate-docs` succeeds
3. `grep -r "from bencher\." holobench/` returns zero results
4. `grep -r "import bencher" holobench/ test/` returns zero results (or only the shim)
5. `grep -r '"bencher\.' holobench/` returns zero results (string literals)
6. `python -c "import holobench as hb; print(hb.__version__)"` works
