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
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Mapping

RESULT_PATH_ENV = "BENCHER_RESULT_PATH"
NO_CACHE_ENV = "BENCHER_NO_CACHE"
NO_SHOW_ENV = "BENCHER_NO_SHOW"

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
