# Plan 01 — Release & CI Safety

**Goal:** Prevent broken packages from shipping to PyPI, add a coverage floor, and close
small CI hygiene gaps. All changes are config-only and low risk.

**Branch name:** `ci/release-safety`

---

## Task 1: Gate auto-publish on CI success (HIGHEST PRIORITY)

**Problem:** `.github/workflows/publish.yml` triggers on every push to `main` and publishes
to PyPI whenever the version in `pyproject.toml` is higher than the one on PyPI — even if
the CI workflow fails. A broken release can ship.

**Important:** `needs:` cannot reference jobs in a *different* workflow file, so do NOT
just add `needs: [ci]` to publish.yml. Use a `workflow_run` trigger instead.

**Steps:**

1. Open `.github/workflows/ci.yml` and note the workflow `name:` field (it is `CI`)
   and the job ids (`ci` and `ci-split`).
2. Replace the contents of `.github/workflows/publish.yml` `on:` and job `if:` sections
   so the file becomes:

   ```yaml
   name: Auto-publish

   on:
     workflow_run:
       workflows: ["CI"]
       types: [completed]
       branches: [main]
     workflow_dispatch:

   jobs:
     # Auto-publish when version is increased, but only after CI succeeds on main
     publish-job:
       if: >-
         github.event_name == 'workflow_dispatch' ||
         (github.event.workflow_run.conclusion == 'success' &&
          github.event.workflow_run.head_branch == 'main')
       runs-on: ubuntu-latest
       permissions:
         contents: write
       steps:
       - uses: etils-actions/pypi-auto-publish@v1
         with:
           pypi-token: ${{ secrets.PYPI_API_TOKEN }}
           gh-token: ${{ secrets.GITHUB_TOKEN }}
           parse-changelog: true
   ```

3. Verify the YAML parses: `pixi run python -c "import yaml,sys; yaml.safe_load(open('.github/workflows/publish.yml'))"`
   (if pyyaml is unavailable in the env, use `python -c` via pixi with `ruamel` or just
   visually compare indentation against ci.yml).

**Verification after merge:** push a trivial commit to main (no version bump) and confirm
in the GitHub Actions tab that "Auto-publish" only starts after "CI" completes.

**Caveat to report to the owner:** with `workflow_run`, GitHub runs the publish workflow
definition from the default branch, and the publish now happens a few minutes later than
before. This is expected.

## Task 2: Add a coverage floor

**Problem:** coverage is ~90% but nothing fails if it drops.

**Steps:**

1. In `pyproject.toml`, find the `[tool.coverage.report]` section (around line 205).
2. Add `fail_under = 85` as the first key in that section (before `exclude_also`).
3. Run `pixi run coverage && pixi run coverage-report` and confirm it passes.
   If the actual coverage is below 85, set `fail_under` to (current floor − 2) instead,
   and note that in the commit message.

## Task 3: Make Codecov upload non-blocking

1. In `.github/workflows/ci.yml`, find the `codecov/codecov-action` step.
2. Ensure it has `fail_ci_if_error: false` under `with:`. If the key is absent, add it.

## Task 4: Gitignore the `autofig/` test artifact

**Problem:** `test/test_bencher.py` creates an `autofig/` directory at the repo root;
it is not in `.gitignore`.

1. Add a line `autofig/` to `.gitignore` (near the other artifact entries like `cachedir`).
2. Verify: `pixi run pytest test/test_bencher.py -q` then `git status --short` — `autofig/`
   must not appear.

## Task 5: Enforce generated-example filename uniqueness

**Problem:** CLAUDE.md requires every file under `bencher/example/generated/` to have a
globally unique basename, but nothing enforces it.

1. Open `test/test_generated_examples.py` and add this test function at module level:

   ```python
   def test_generated_example_filenames_globally_unique():
       """Every generated example basename must be unique across the whole tree.

       The doc builder uses basenames as RST page stems and thumbnail ids, so a
       duplicate basename in a different subdirectory silently shadows a page.
       """
       from pathlib import Path

       generated_dir = Path(__file__).parent.parent / "bencher" / "example" / "generated"
       basenames = [
           p.name for p in generated_dir.rglob("*.py") if p.name != "__init__.py"
       ]
       duplicates = sorted({b for b in basenames if basenames.count(b) > 1})
       assert not duplicates, f"Duplicate generated example filenames: {duplicates}"
   ```

2. Run `pixi run pytest test/test_generated_examples.py -q` — the new test must pass.
   If it fails with real duplicates, list them in your report; do NOT rename files
   without checking `bencher/example/meta/generate_examples.py` first.

## Final verification

```bash
pixi run ci
```

Must pass. Then commit with message
`ci: gate PyPI publish on CI, add coverage floor, enforce example name uniqueness`
and open a PR against `main`.
