# Plan 03 — Repo Hygiene

**Goal:** Remove stale planning documents and dead build files from the repo root so a
newcomer sees only current, accurate files.

**Branch name:** `chore/repo-hygiene`

All files mentioned below are git-tracked, so removals/moves go through `git mv` / `git rm`.

---

## Task 1: Archive stale planning documents

Create `plans/archive/` and move these root-level files into it. Each was a working
document for past or deferred work; none describes current behavior accurately.

| File | Why it moves | Header note to ADD at the top of the file after moving |
|------|--------------|--------------------------------------------------------|
| `PLAN.md` | Marked "Status: IMPLEMENTED" — the `benchmark()` method shipped | `> ARCHIVED: implemented in v1.10x. Kept for historical reference.` |
| `RENAME_PLAN.md` | Both plans explicitly shelved/deferred | `> ARCHIVED: deferred indefinitely. The PyPI name remains 'holobench' (import name 'bencher') — this is intentional.` |
| `PERFORMANCE_PLAN.md` | ~1300 lines of aspirations from the v1.71 era, partially superseded | `> ARCHIVED: snapshot from the v1.71 save-performance investigation. Partially addressed since; see PR #830 for the active direction.` |
| `SAVE_PERFORMANCE_REPORT.md` | Auto-generated benchmark output from 2026-03-23 | `> ARCHIVED: point-in-time output of scripts/benchmark_save.py (2026-03-23). Regenerate rather than read.` |

Commands (repeat per file):

```bash
git mv PLAN.md plans/archive/PLAN.md
# then Edit the file to add the header note as the first line
```

`PROMPT.md` is a 21-line unfilled template ("CUSTOMIZE: Replace this section...").
Check first whether anything references it: `grep -rn "PROMPT.md" --include="*.yml" --include="*.yaml" --include="*.toml" --include="*.py" .github/ ralph.yml pyproject.toml scripts/ 2>/dev/null`.
- If `ralph.yml` references it, leave it but replace the placeholder content with one
  line: `# Ralph orchestrator prompt — customize per task.`
- If nothing references it, `git rm PROMPT.md`.

## Task 2: Delete dead legacy build files

`setup.py`, `setup.cfg`, and `MANIFEST.in` are leftovers from a ROS-era layout. The
build is hatchling via `pyproject.toml`; `setup.py` even declares the wrong package
name (`bencher` instead of `holobench`).

1. `git rm setup.py setup.cfg MANIFEST.in`
2. Verify the package still builds and imports:

   ```bash
   pixi run python -m pip install -e . --no-deps --quiet
   pixi run python -c "import bencher; print('import OK')"
   ```

3. Check nothing references the removed files:
   `grep -rn "setup.py\|setup.cfg\|MANIFEST.in" pyproject.toml .github/ scripts/ docs/ 2>/dev/null`
   — fix or report any hit. (Hits inside `pixi.lock` or archived plans can be ignored.)
4. Check whether `resource/` and `package.xml` exist and are only referenced by the
  deleted `setup.py` — if so, list them in your report as candidates for removal but
  do NOT delete them in this plan (ROS consumers might still need them; `OWNER DECISION`).

## Task 3: Document the remaining unexplained root files

Add a short "Repository layout" section to `CLAUDE.md` (and the `AGENTS.md` symlink picks
it up automatically) explaining:

- `ralph.yml` — config for the Ralph agent orchestrator (used with `pixi run agent-iterate` flows).
- `rockerc.yaml` — rocker/docker dev-container configuration.
- `plans/` — current improvement plans; `plans/archive/` — historical ones.

Keep it to ~6 lines.

## Task 4: Remove the empty `autofig/` directory

`rmdir autofig` (it is untracked test output; plan 01 adds it to `.gitignore`).
If `rmdir` fails because it is non-empty, use `rm -rf autofig` — it only ever contains
test-generated figures.

## Final verification

```bash
pixi run ci
git status --short   # should show only intended moves/deletes
```

Commit as `chore: archive stale plan docs, remove legacy setuptools files` and open a PR.
