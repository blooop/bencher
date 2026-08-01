# Plan 03 — Repo Hygiene

**Goal:** Remove stale planning documents and dead build files from the repo root so a
newcomer sees only current, accurate files.

**Branch name:** `chore/repo-hygiene`

All files mentioned below are git-tracked, so removals/moves go through `git mv` / `git rm`.

---

## Status: EXECUTED (branch `plan/repo-hygiene-03`)

All four tasks are done. Where the plan's evidence had gone stale, the executed version
differs — recorded here rather than silently:

- **Task 1 header notes.** Two of the four prescribed notes were wrong and were rewritten.
  `RENAME_PLAN.md` is *not* "both plans shelved": Plan A (`bch` → `bn`) **shipped** (the
  tree has zero `import bencher as bch` and ~375 `import bencher as bn`); only Plan B (the
  `bencher` → `holobench` package rename) is deferred. `PERFORMANCE_PLAN.md`'s note must
  not point at "PR #830 for the active direction": #830 is closed and its fast static save
  path was **explicitly rejected** by the owner on 2026-07-01 (A1 addendum, decision 1), so
  the note points at that addendum instead. The v1.71-era dating checked out
  (`PERFORMANCE_PLAN.md` was added at v1.71.0, and the report was generated on 2026-03-23
  against bencher 1.72.2), as did `PLAN.md`'s `## Status: IMPLEMENTED` (#864 shipped
  `ParametrizedSweep.benchmark()`).
- **`SAVE_PERFORMANCE_REPORT.md` is still regenerated at the repo root** by
  `scripts/benchmark_save.py:main` (`pixi run benchmark-save`), which the plan did not
  account for — archiving the file alone would let the next run re-litter the root. The
  script's output path is left alone (it is the script's deliverable) and the root path is
  now gitignored, so the archived copy is never overwritten and fresh runs stay untracked.
- **Task 2 also had to touch `pyproject.toml`.** Since this plan was written, plan 23 P1
  added a `[[tool.ty.overrides]]` block listing `setup.py` to silence `unresolved-import`
  for its vestigial `setuptools` import. That include entry went with the file.
  `test/test_ty_gate.py`'s meta-tests (which parse these override blocks) still pass: they
  assert no *first-party `bencher/`* pattern silences a Tier-A rule and that the strict
  block is non-empty, neither of which this entry participated in.
- **`PROMPT.md` was kept**, because `ralph.yml:9` (`prompt_file: "PROMPT.md"`) and
  `.claude/README.md` both reference it. Per the plan's own conditional, its unfilled
  template body was replaced with the single customize-me line.
- **Task 4 was already satisfied** — there is no `autofig/` directory in the tree, and
  `.gitignore` has ignored `autofig/` since well before plan 01.
- **`resource/` is confirmed dead but deliberately kept** (`OWNER DECISION`, as the plan
  requires). `resource/bencher` is a zero-byte ROS ament index marker whose only reference
  in the entire repo was the deleted `setup.py`. One correction to the plan's framing: it
  is **not** absent from the distribution — `[tool.hatch.build] include = ["bencher", ...]`
  is a gitignore-style pattern that matches any path named `bencher` at any depth, so the
  published wheel installs `resource/bencher` alongside the package. Deleting it is a
  one-line follow-up if the owner confirms no ROS consumer needs it.
- **The removal is provably distribution-neutral.** There is no `build` pixi task, so
  verification was done by building a wheel from `git archive HEAD` (pre-change) and from
  the working tree (post-change): both contain the same 400 files. None of the three deleted
  files ever matched an `include` pattern, so neither the wheel nor the sdist changes.

---

## Task 1: Archive stale planning documents

Create `plans/archive/` and move these root-level files into it. Each was a working
document for past or deferred work; none describes current behavior accurately.

| File | Why it moves | Header note to ADD at the top of the file after moving |
|------|--------------|--------------------------------------------------------|
| `PLAN.md` | Marked "Status: IMPLEMENTED" — the `benchmark()` method shipped | `> ARCHIVED: implemented in v1.10x. Kept for historical reference.` |
| `RENAME_PLAN.md` | Both plans explicitly shelved/deferred | `> ARCHIVED: deferred indefinitely. The PyPI name remains 'holobench' (import name 'bencher') — this is intentional.` |
| `PERFORMANCE_PLAN.md` | 802 lines of aspirations from the v1.71 era, partially superseded | `> ARCHIVED: snapshot from the v1.71 save-performance investigation. Partially addressed since; see PR #830 for the active direction.` |
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
name (`bencher` instead of `holobench`) and lists a `package.xml` in `data_files`
that does not exist in the repo.

1. `git rm setup.py setup.cfg MANIFEST.in`
2. Verify the package still builds and imports:

   ```bash
   pixi run python -m pip install -e . --no-deps --quiet
   pixi run python -c "import bencher; print('import OK')"
   ```

3. Check nothing references the removed files:
   `grep -rn "setup.py\|setup.cfg\|MANIFEST.in" pyproject.toml .github/ scripts/ docs/ 2>/dev/null`
   — fix or report any hit. (Hits inside `pixi.lock` or archived plans can be ignored.)
4. `package.xml` does not exist (setup.py references it anyway — further evidence it
  is dead). Check whether `resource/` is only referenced by the deleted `setup.py` —
  if so, list it in your report as a removal candidate but do NOT delete it in this
  plan (ROS consumers might still need it; `OWNER DECISION`).

## Task 3: Document the remaining unexplained root files

Add a short "Repository layout" section to `AGENTS.md` (`CLAUDE.md` is a symlink to
it, so both names pick it up) explaining:

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
