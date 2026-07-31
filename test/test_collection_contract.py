"""Plan 23 P2 — the collection path must not accept a broken worker silently.

Two shipped bugs and one latent smell, all the same shape: a branch that stored
nothing and had no ``else``, so a harness-contract error looked exactly like a
sweep that had not been run yet.

- **B2** a ``ResultVec`` of the wrong length was dropped, leaving the NaN fill.
- **B3** a worker that returned ``None`` tripped a bare ``assert`` on the serial
  path and *nothing at all* on MULTIPROCESSING/SCOOP, where the sweep finished
  green with an all-sentinel dataset and ``n_failed == 0``.
- **C13** ``executor`` is compared with both ``==`` and ``is``, and
  ``param.Selector`` accepts a raw string for it, so the two styles can disagree.

These are contract errors, not sample faults, so none of them is routed through
``catch=`` (plan 23 decision 2) -- ``TestCatchDoesNotAbsorbContractErrors`` pins
that, since ``catch=Exception`` is the natural thing for a user to reach for and
would otherwise turn every one of these back into a silent skip.
"""

from __future__ import annotations

import unittest
from typing import ClassVar

import numpy as np
import pytest

import bencher as bn
from bencher.job import (
    Executors,
    FutureCache,
    Job,
    JobFuture,
    normalize_executor,
    require_worker_result,
)
from bencher.result_collector import ResultCollector

# ---------------------------------------------------------------------------
# Workers. Module level: MULTIPROCESSING pickles them.
# ---------------------------------------------------------------------------


class WrongLengthVec(bn.ParametrizedSweep):
    """Sets a ``ResultVec(size=2)`` to ``n_elements`` elements.

    ``param.List`` enforces *that* the value is a list but not how long it is, so
    a length mismatch reaches the collector -- which is why B2 was reachable at
    all from ordinary benchmark code.
    """

    x = bn.IntSweep(default=0, bounds=(0, 1), samples=2)
    v = bn.ResultVec(size=2)

    n_elements: ClassVar[int] = 2

    def benchmark(self) -> None:
        self.v = [float(self.x)] * type(self).n_elements


class ReturnsNothing(bn.ParametrizedSweep):
    """A worker with the most common harness-contract mistake: no return value.

    Written on the legacy ``__call__`` path because that is the only way to get
    here -- ``benchmark()`` cannot cause it, since ``ParametrizedSweep.__call__``
    returns ``get_results_values_as_dict()`` for you.
    """

    x = bn.IntSweep(default=0, bounds=(0, 1), samples=2)
    y = bn.ResultFloat()

    # The override really is invalid -- that is the bug under test -- and the
    # annotation says so honestly rather than hiding it behind a bare `def`. Worth
    # noting what this proves: for a worker whose return type is *annotated*, P1's
    # Tier-A `invalid-method-override` already catches this statically. The runtime
    # check exists for the untyped case, which is the common one.
    def __call__(self, **kwargs) -> None:  # ty: ignore[invalid-method-override]
        self.update_params_from_kwargs(**kwargs)
        self.y = float(self.x)
        # Deliberately no `return self.get_results_values_as_dict()`.


def _run(worker, *, executor=Executors.SERIAL, **run_kwargs):
    cfg = bn.BenchRunCfg(executor=executor, **run_kwargs)
    cfg.auto_plot = False
    cfg.cache_results = False
    cfg.cache_samples = False
    bench = worker.to_bench(cfg)
    try:
        return bench.plot_sweep(input_vars=["x"], plot_callbacks=False)
    finally:
        bench.close()


# ---------------------------------------------------------------------------
# B2 -- wrong-length ResultVec
# ---------------------------------------------------------------------------


class TestResultVecLength(unittest.TestCase):
    """B2: the ladder's other arms raise; this one used to just not store."""

    def tearDown(self) -> None:
        WrongLengthVec.n_elements = 2

    def test_the_control_case_still_stores_every_element(self) -> None:
        """Guards against a check that rejects correct vectors too."""
        WrongLengthVec.n_elements = 2
        res = _run(WrongLengthVec())
        for name in WrongLengthVec.param.v.index_names():
            self.assertIn(name, res.ds)
            self.assertFalse(np.isnan(res.ds[name].values).any(), f"{name} left at the NaN fill")

    def test_a_short_vector_raises_instead_of_being_dropped(self) -> None:
        WrongLengthVec.n_elements = 1
        with self.assertRaises(TypeError) as ctx:
            _run(WrongLengthVec())
        msg = str(ctx.exception)
        # The message has to carry all three facts, because the symptom the user
        # would otherwise see is an all-NaN column with nothing pointing at 'v'.
        self.assertIn("'v'", msg)
        self.assertIn("size=2", msg)
        self.assertIn("1 element", msg)

    def test_a_long_vector_also_raises(self) -> None:
        WrongLengthVec.n_elements = 3
        with self.assertRaises(TypeError) as ctx:
            _run(WrongLengthVec())
        self.assertIn("3 element", str(ctx.exception))

    def test_a_non_sequence_raises_naming_the_type(self) -> None:
        """Only reachable from a worker that returns a raw dict.

        Assignment through ``self.v`` cannot get here -- ``param.List`` rejects a
        float first -- so this goes through ``store_results`` directly, which is
        also the shape a plain-function worker produces.
        """
        res = _run(WrongLengthVec())
        collector = ResultCollector()
        job = Job(job_id="vec-job", function=lambda **_: None, job_args={"x": 0})

        class _Worker:
            function_input: ClassVar[dict] = {"x": 0}
            index_tuple = (0, 0)
            canonical_input = ("x", 0)

        with self.assertRaises(TypeError) as ctx:
            collector.store_results(
                JobFuture(job=job, res={"v": 3.0}),
                res,
                _Worker(),
                bn.BenchRunCfg(),
            )
        msg = str(ctx.exception)
        self.assertIn("'v'", msg)
        self.assertIn("float", msg)


# ---------------------------------------------------------------------------
# B3 -- worker returned None
# ---------------------------------------------------------------------------


class TestWorkerReturnedNothing(unittest.TestCase):
    """B3: loud or silent used to be chosen by an unrelated config knob."""

    def test_serial_raises(self) -> None:
        with self.assertRaises(TypeError) as ctx:
            _run(ReturnsNothing())
        self.assertIn("returned None", str(ctx.exception))

    def test_multiprocessing_raises_too(self) -> None:
        """The path that used to complete green with an all-sentinel dataset."""
        with self.assertRaises(TypeError) as ctx:
            _run(ReturnsNothing(), executor=Executors.MULTIPROCESSING)
        self.assertIn("returned None", str(ctx.exception))

    def test_the_message_says_what_to_do(self) -> None:
        with self.assertRaises(TypeError) as ctx:
            require_worker_result(None, "job-42")
        msg = str(ctx.exception)
        self.assertIn("job-42", msg)
        self.assertIn("super().__call__(**kwargs)", msg)

    def test_a_real_result_passes_straight_through(self) -> None:
        payload = {"y": 1.0}
        self.assertIs(require_worker_result(payload, "job-1"), payload)

    def test_an_empty_dict_is_not_treated_as_missing(self) -> None:
        """A worker with no result vars returns ``{}``, which is falsy but valid."""
        self.assertEqual(require_worker_result({}, "job-1"), {})


class TestCatchDoesNotAbsorbContractErrors(unittest.TestCase):
    """Plan 23 decision 2: ``catch=`` tolerates failing *samples*, not a broken harness.

    Both checks are raised outside ``store_results``'s ``except catch`` block on
    purpose. Without this test the fix would look complete while
    ``catch=Exception`` -- the obvious thing to reach for -- silently restored the
    old behaviour, which is the exact failure mode B2 and B3 are about.
    """

    def tearDown(self) -> None:
        WrongLengthVec.n_elements = 2

    def test_catch_does_not_swallow_a_none_return(self) -> None:
        with self.assertRaises(TypeError):
            _run(ReturnsNothing(), catch=Exception)

    def test_catch_does_not_swallow_a_wrong_length_vector(self) -> None:
        WrongLengthVec.n_elements = 1
        with self.assertRaises(TypeError):
            _run(WrongLengthVec(), catch=Exception)


# ---------------------------------------------------------------------------
# C13 -- executor normalization
# ---------------------------------------------------------------------------


class TestExecutorNormalization:
    """C13, and the precondition plan 24 A2 requires for matching on ``executor``.

    No pre-fix regression test is possible here: the four comparison sites happen
    to agree today, because ``Executors.factory`` also used ``==``. What is
    testable -- and what actually protects the ``assert_never`` in ``factory`` --
    is that normalization makes the agreement structural.
    """

    def test_a_raw_string_is_where_the_two_styles_disagree(self) -> None:
        """The reason normalization exists, pinned as an executable fact.

        Also a tripwire for the stdlib-``StrEnum`` migration (plan 23 handover
        §5.4): ``enum.StrEnum`` + ``auto()`` lowercases, so ``"SERIAL"`` would
        stop comparing equal at all and this assertion would fail loudly rather
        than the vocabulary changing under callers in silence.
        """
        raw = "SERIAL"
        assert raw == Executors.SERIAL  # every `==`/`!=` site sees serial
        assert raw is not Executors.SERIAL  # every `is`/`is not` site does not

    @pytest.mark.parametrize("member", list(Executors))
    def test_normalizing_a_member_is_the_identity(self, member: Executors) -> None:
        assert normalize_executor(member) is member

    @pytest.mark.parametrize("member", list(Executors))
    def test_a_raw_value_normalizes_to_its_member(self, member: Executors) -> None:
        assert normalize_executor(member.value) is member

    @pytest.mark.parametrize("member", list(Executors))
    def test_every_comparison_style_agrees_after_normalizing(self, member: Executors) -> None:
        """The property the four sites (`==`, `!=`, `is`, `is not`) rely on."""
        normalized = normalize_executor(member.value)
        assert (normalized == Executors.SERIAL) == (normalized is Executors.SERIAL)
        assert (normalized != Executors.SERIAL) == (normalized is not Executors.SERIAL)

    @pytest.mark.parametrize("bad", ["serial", "threads", "", "Serial"])
    def test_an_unknown_value_raises_at_the_parse(self, bad: str) -> None:
        """Plan 24 A3: at normalization, never at a match site."""
        with pytest.raises(ValueError, match="executor must be one of"):
            normalize_executor(bad)

    def test_factory_rejects_an_unknown_value_before_matching(self) -> None:
        """``factory``'s ``assert_never`` must be unreachable from bad input.

        If the parse were removed the match would fall through to
        ``assert_never`` and raise ``AssertionError: Expected code to be
        unreachable``, which points the reader at a missing enum member rather
        than at their own typo (plan 24 A1).
        """
        with pytest.raises(ValueError, match="executor must be one of"):
            Executors.factory("threads")

    def test_factory_resolves_a_raw_string_to_the_serial_path(self) -> None:
        assert Executors.factory("SERIAL") is None
        assert Executors.factory(Executors.SERIAL) is None

    def test_future_cache_stores_a_member_not_a_string(self) -> None:
        """``submit()`` discriminates with ``is not``, so the field must be a member."""
        cache = FutureCache(executor="SERIAL", cache_samples=False)
        try:
            assert cache.executor_type is Executors.SERIAL
        finally:
            cache.close()

    @staticmethod
    def _cfg() -> bn.BenchRunCfg:
        cfg = bn.BenchRunCfg(executor="SERIAL")
        # The premise of C13: param.Selector accepts the bare string, because
        # Executors is a StrEnum and `"SERIAL" in list(Executors)` is therefore True.
        assert cfg.executor is not Executors.SERIAL, "precondition: param stored a raw str"
        cfg.auto_plot = False
        cfg.cache_results = False
        cfg.cache_samples = False
        return cfg

    def test_the_config_the_sweep_actually_runs_on_holds_a_member(self) -> None:
        """``to_bench`` deepcopies, so the normalized field is the one on the copy.

        Asserted via ``last_run_cfg`` rather than the caller's object: the copy is
        what reaches every comparison site, and leaving the caller's config
        untouched is the intended behaviour, not a gap.
        """
        cfg = self._cfg()
        bench = WrongLengthVec().to_bench(cfg)
        try:
            bench.plot_sweep(input_vars=["x"], plot_callbacks=False)
            assert bench.last_run_cfg.executor is Executors.SERIAL
            assert cfg.executor == "SERIAL", "the caller's own config is not mutated"
        finally:
            bench.close()

    def test_a_config_passed_to_plot_sweep_is_normalized_in_place(self) -> None:
        """The direct path does not copy, so the caller sees the member."""
        cfg = self._cfg()
        bench = bn.Bench("c13_direct", WrongLengthVec())
        try:
            bench.plot_sweep(input_vars=["x"], run_cfg=cfg, plot_callbacks=False)
            assert cfg.executor is Executors.SERIAL
        finally:
            bench.close()
