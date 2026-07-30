"""Inspectable, pinnable benchmark identity.

``BenchCfg.hash_persistent`` is the single source of truth for a benchmark's cache
and over_time history keys, but it lives on a config object that ``plot_sweep``
assembles part-way through its own body, so the only way to learn a declaration's
keys used to be to run the benchmark. Downstream projects that want to protect a
long-lived trend from an accidental reset therefore transcribe the hashing rule
into an assertion about "the fields that make up the key" -- an assertion that
keeps passing after the rule changes.

:func:`sweep_identity` closes that gap without adding a second implementation of
the rule: it drives the real :meth:`bencher.bencher.Bench.plot_sweep` in dry-run
mode, applies the same ``run_cfg`` -> ``BenchCfg`` merge that
:meth:`bencher.bencher.Bench.run_sweep` applies, and calls the same
``hash_persistent``. Anything that changes the keys changes them here too, by
construction.
"""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, field
from typing import Any

import param

from bencher.bench_cfg import BenchCfg, BenchRunCfg
from bencher.history import config_summary, diff_summaries

# Fields folded into hash_persistent, and the ones deliberately left out.  Stated
# here for explain(), which is the whole point of the plan: when a key moves, a
# user needs to be told what could have moved it without reading the hashing code.
IDENTITY_FIELDS = (
    "CACHE_VERSION",
    "bench_name",
    "over_time",
    "repeats",
    "tag",
    "input_vars (in list order)",
    "result_vars (as an unordered set; cache_key only)",
    "const_vars (as an unordered set)",
)

EXCLUDED_FIELDS = (
    "title",
    "description / post_description",
    "aggregate / agg_fn",
    "sample_order",
    "plot_callbacks / auto_plot",
)


@dataclass(frozen=True)
class SweepIdentity:
    """The keys a sweep declaration resolves to, as a value.

    Immutable, picklable, ``json.dumps(asdict(...))``-able, and usable as a dict
    key: every compared field is a string, an int or a bool.

    ``summary`` is excluded from equality and hashing (``compare=False``). It is
    derived explanatory data -- the same payload the reset warning is built from
    -- not part of the identity, and a dict field would otherwise make the
    dataclass unhashable.
    """

    cache_key: str
    history_key: str
    sample_key: str
    bench_name: str
    tag: str
    repeats: int
    over_time: bool
    summary: dict = field(default_factory=dict, compare=False, repr=False)

    def explain(self) -> str:
        """Human-readable rendering of the keys and what did or did not contribute.

        A pinned key is a *within-version* guard against accidental drift, not a
        cross-version guarantee: ``CACHE_VERSION`` is folded in deliberately, so a
        version bump legitimately moves every key.
        """
        lines = [
            f"bench_name: {self.bench_name}",
            f"tag:        {self.tag!r}",
            f"repeats:    {self.repeats}",
            f"over_time:  {self.over_time}",
            "",
            f"cache_key   (result cache):    {self.cache_key}",
            f"history_key (over_time trend): {self.history_key}",
            f"sample_key  (sample cache):    {self.sample_key}",
            "",
            "contributing fields:",
        ]
        lines += [f"  - {f}" for f in IDENTITY_FIELDS]
        lines.append("excluded on purpose (changing these never moves a key):")
        lines += [f"  - {f}" for f in EXCLUDED_FIELDS]
        if self.summary:
            lines.append("")
            lines.append("resolved declaration:")
            for kind in ("inputs", "consts", "results"):
                for row in self.summary.get(kind, []):
                    lines.append(f"  {kind[:-1]:6} {row}")
        return "\n".join(lines)


def diff_identities(
    old: SweepIdentity | dict | None, new: SweepIdentity | dict | None
) -> list[str]:
    """Lines describing how *new*'s declaration differs from *old*'s.

    Accepts either :class:`SweepIdentity` values or the raw ``config_summary``
    dicts stored in the last-seen index, so the same helper serves a live
    comparison and a comparison against history.
    """
    return diff_summaries(
        old.summary if isinstance(old, SweepIdentity) else old,
        new.summary if isinstance(new, SweepIdentity) else new,
    )


def _attach_worker(bench: Any, worker: Any) -> None:
    """Make *worker* available for by-name variable resolution, without calling it.

    A **class** is accepted and never instantiated. Everything the declaration path
    needs from a worker is class-level -- ``param.objects()`` plus the
    ``get_inputs_only`` / ``get_input_defaults`` / ``get_results_only``
    classmethods -- and a worker whose ``__init__`` demands live resources (an
    open device, a running simulator, an attached robot) cannot be constructed
    just to be asked what its parameters are. Requiring an instance would put
    identity out of reach of exactly the expensive benchmarks that most need to
    check it before running.

    ``Bench.set_worker`` rejects a class on purpose, because a class cannot be
    *called*; identity never calls one, so it is attached directly instead.
    """
    if worker is None:
        return
    bench.worker_class_instance = worker
    bench._worker_mgr.worker_class_instance = worker  # noqa: SLF001


def sweep_identity(
    *,
    worker: Any = None,
    bench_name: str | None = None,
    input_vars: list | dict | None = None,
    result_vars: list | None = None,
    const_vars: list | dict | None = None,
    tag: str = "",
    title: str | None = None,
    description: str | None = None,
    post_description: str | None = None,
    run_cfg: BenchRunCfg | None = None,
    repeats: int | None = None,
    over_time: bool | None = None,
) -> SweepIdentity:
    """The keys *this declaration* would produce, without running the benchmark.

    Accepts the declarative arguments of :meth:`bencher.bencher.Bench.plot_sweep`
    with the same spellings, so ``sweep_identity(worker=W, **kwargs)`` and
    ``bench.plot_sweep(**kwargs)`` describe the same sweep.

    ``run_cfg`` is **not** optional in the way it looks. ``subsampling_divisions``
    (default 0 on a bare :class:`BenchRunCfg`, but commonly set) and
    ``samples_per_var`` reshape every input variable before it is hashed, and
    ``run_tag`` is prefixed to ``tag``; a run driven with a different one has a
    different identity. Pass the same ``run_cfg`` the real run uses, or pass
    ``repeats`` / ``over_time`` for the common case where those are the only
    run-side fields that matter.

    Args:
        worker: The ``ParametrizedSweep`` subclass **or** instance the variables are
            declared on. Required whenever any variable is given as a string or a
            :func:`bencher.sweep` spec dict, because resolution needs the declaring
            class. Also supplies the default ``bench_name``. A class is never
            instantiated -- see :func:`_attach_worker` -- so a worker whose
            construction needs live resources can still be asked for its identity.
        bench_name: Overrides the name, which is otherwise the worker's class name
            -- matching :func:`bencher.factories.create_bench`. ``bench_name`` is
            hashed, so this is the field a rename moves.
        repeats: Convenience override of ``run_cfg.repeats``.
        over_time: Convenience override of ``run_cfg.over_time``.

    Returns:
        SweepIdentity: The three keys plus the resolved declaration summary.

    Raises:
        TypeError: If neither *worker* nor *bench_name* is given, or if a
            by-name variable is used with no worker (raised by the existing
            resolution guard, which lists the available parameters).
    """
    from bencher.bencher import Bench

    if bench_name is None:
        if worker is None:
            raise TypeError(
                "sweep_identity() needs a bench_name or a worker to take one from: "
                "bench_name is hashed, so it cannot be defaulted arbitrarily."
            )
        # Matches create_bench, which takes the name from the worker's class.
        bench_name = worker.__name__ if isinstance(worker, type) else type(worker).__name__

    cfg = BenchRunCfg() if run_cfg is None else deepcopy(run_cfg)
    if repeats is not None:
        cfg.repeats = repeats
    if over_time is not None:
        cfg.over_time = over_time
    # Stop plot_sweep before it executes a single sample or opens a cache; none of
    # these three fields is hashed, so forcing them cannot change the answer.
    cfg.dry_run = True
    cfg.auto_plot = False

    bench = Bench(bench_name, None)
    _attach_worker(bench, worker)
    try:
        res = bench.plot_sweep(
            title=title,
            input_vars=input_vars,
            result_vars=result_vars,
            const_vars=const_vars,
            description=description,
            post_description=post_description,
            tag=tag,
            run_cfg=cfg,
            plot_callbacks=False,
        )
        return identity_of(res.bench_cfg, cfg)
    finally:
        bench.close()


def identity_of(bench_cfg: BenchCfg, run_cfg: BenchRunCfg | None = None) -> SweepIdentity:
    """The identity of a config that already exists.

    *run_cfg* replays the ``run_cfg`` -> ``BenchCfg`` merge that
    :meth:`bencher.bencher.Bench.run_sweep` performs before hashing, and is
    required for a config that has not been through a run -- ``repeats`` and
    ``over_time`` live on the run config and reach ``BenchCfg`` only through that
    merge.
    """
    from bencher.bencher import Bench

    if run_cfg is not None:
        values, _missing, _constant = Bench.filter_overridable_params(bench_cfg, run_cfg)
        with param.parameterized.discard_events(bench_cfg):
            bench_cfg.param.update(values)

    return SweepIdentity(
        cache_key=bench_cfg.hash_persistent(True),
        history_key=bench_cfg.hash_persistent(True, include_result_vars=False),
        sample_key=bench_cfg.hash_persistent(False),
        bench_name=str(bench_cfg.bench_name),
        tag=str(bench_cfg.tag),
        repeats=int(bench_cfg.repeats),
        over_time=bool(bench_cfg.over_time),
        summary=config_summary(bench_cfg),
    )


__all__ = [
    "EXCLUDED_FIELDS",
    "IDENTITY_FIELDS",
    "SweepIdentity",
    "config_summary",
    "diff_identities",
    "identity_of",
    "sweep_identity",
]
