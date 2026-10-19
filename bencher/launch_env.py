"""Environment a launcher sets around a benchmark process it does not control.

``bencher ab`` runs an arbitrary bench command twice and needs two things from
each run without editing the bench: the result, written where it can find it,
and samples measured by *this* code rather than read back from a cache filled by
another revision (the caches are keyed by inputs, not code).

* :data:`RESULT_PATH_ENV` -- ``BENCHER_RESULT_PATH=/path/result.pkl`` saves every
  collected sweep's result there with :func:`bencher.save_result`. A command that
  runs several sweeps leaves the last one.
* :data:`NO_CACHE_ENV` -- ``BENCHER_NO_CACHE=1`` turns off the benchmark-result
  and per-sample caches for every sweep, whatever the bench's own run config asks.
* :data:`NO_SHOW_ENV` -- ``BENCHER_NO_SHOW=1`` makes ``bn.run`` and
  ``BenchRunner`` show nothing. ``bn.run``'s default starts a live report server,
  which keeps a non-interactive process alive at exit; a launcher waiting for
  the command would wait forever.
* :data:`FORBIDDEN_ROOT_ENV` and :data:`BASE_TREE_ENV` -- ``bencher ab`` sets
  these on the base run only, to the candidate's repository and to the base
  worktree. Before a result is saved, :func:`check_no_forbidden_code` raises if any
  loaded module's file is under the forbidden root, unless it is under the base
  worktree, in a ``site-packages`` directory, or part of the running interpreter's
  installation. No result is saved, so the base run fails instead of measuring
  the candidate's code.
"""

from __future__ import annotations

import os
import sys
import sysconfig
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Mapping
    from types import ModuleType

RESULT_PATH_ENV = "BENCHER_RESULT_PATH"
NO_CACHE_ENV = "BENCHER_NO_CACHE"
NO_SHOW_ENV = "BENCHER_NO_SHOW"
FORBIDDEN_ROOT_ENV = "BENCHER_AB_FORBIDDEN_ROOT"
BASE_TREE_ENV = "BENCHER_AB_BASE_TREE"

_TRUE = frozenset({"1", "true", "yes", "on"})


def result_path_from_env(env: Mapping[str, str] | None = None) -> Path | None:
    """Where a launcher asked for the result, or None when it did not."""
    value = (os.environ if env is None else env).get(RESULT_PATH_ENV, "").strip()
    return Path(value) if value else None


def _flag(name: str, env: Mapping[str, str] | None) -> bool:
    return (os.environ if env is None else env).get(name, "").strip().lower() in _TRUE


def caches_disabled_by_env(env: Mapping[str, str] | None = None) -> bool:
    """True when a launcher asked for fresh samples on every sweep."""
    return _flag(NO_CACHE_ENV, env)


def show_disabled_by_env(env: Mapping[str, str] | None = None) -> bool:
    """True when a launcher asked for no report to be shown."""
    return _flag(NO_SHOW_ENV, env)


class ForbiddenCodeError(RuntimeError):
    """A run that must not use the candidate's code loaded a module from it."""


def _interpreter_roots() -> set[Path]:
    paths = {sys.prefix, sys.exec_prefix, sys.base_prefix, sys.base_exec_prefix}
    paths.update(sysconfig.get_paths().values())
    return {Path(path).resolve() for path in paths}


def check_no_forbidden_code(
    env: Mapping[str, str] | None = None,
    modules: Mapping[str, ModuleType | None] | None = None,
) -> None:
    """Raise ForbiddenCodeError naming each loaded module whose file is under the forbidden root."""
    env = os.environ if env is None else env
    root = env.get(FORBIDDEN_ROOT_ENV, "").strip()
    if not root:
        return
    forbidden = Path(root).resolve()
    allowed = _interpreter_roots()
    if tree := env.get(BASE_TREE_ENV, "").strip():
        allowed.add(Path(tree).resolve())
    loaded = []
    for name, module in list((sys.modules if modules is None else modules).items()):
        file = getattr(module, "__file__", None)
        if not isinstance(file, str):
            continue
        path = Path(file).resolve()
        if (
            path.is_relative_to(forbidden)
            and "site-packages" not in path.parts
            and not any(path.is_relative_to(allowed_root) for allowed_root in allowed)
        ):
            loaded.append(f"  {name} from {path}")
    if loaded:
        raise ForbiddenCodeError(
            f"modules were loaded from the candidate's tree {forbidden}, so the base run "
            "would measure the candidate's code and no result is saved:\n" + "\n".join(loaded)
        )
