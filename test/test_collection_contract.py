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

Disposition (plan 23 §6.2, owner-amended 2026-07-31): a contract violation is
**recorded and warned, never raised through the sweep** — bencher must not crash
mid-run and lose expensive already-collected data. Loudness comes from the
``WorkerContractWarning``, ``n_failed``, the report's failed-samples summary, and
(opt-in) ``fail_on_sample_error`` at the end of the run. ``catch=`` still plays
no part in it (plan 23 decision 2): the violation is recorded with or without
``catch=Exception``, so neither setting nor omitting it restores the old silent
skip — ``TestCatchDoesNotChangeContractHandling`` pins that.
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
    WorkerContractError,
    WorkerContractWarning,
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


class RaisesContractError(bn.ParametrizedSweep):
    """A worker that raises ``WorkerContractError`` *itself*.

    The class is public API (``bn.WorkerContractError``), so a worker or plugin can
    raise it — e.g. to signal a hard configuration error and have ``catch=()``
    abort the run. The harness must therefore not confuse it with its *own*
    diagnosis that a job produced nothing, which is exempt from ``catch=``.
    """

    x = bn.IntSweep(default=0, bounds=(0, 1), samples=2)
    y = bn.ResultFloat()

    def benchmark(self) -> None:
        raise bn.WorkerContractError("raised by the worker, not by the harness")


def _contract_messages(record) -> list[str]:
    """The WorkerContractWarning messages out of a pytest.warns record.

    ``record[0]`` is unreliable: unrelated warnings (deprecations, fork) share
    the capture."""
    return [str(w.message) for w in record if issubclass(w.category, WorkerContractWarning)]


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
    """B2: a wrong-shape vector used to be silently dropped; now it is recorded,
    warned, and left at the sentinel — without aborting the sweep."""

    def tearDown(self) -> None:
        WrongLengthVec.n_elements = 2

    def test_the_control_case_still_stores_every_element(self) -> None:
        """Guards against a check that rejects correct vectors too."""
        WrongLengthVec.n_elements = 2
        res = _run(WrongLengthVec())
        for name in WrongLengthVec.param.v.index_names():
            self.assertIn(name, res.ds)
            self.assertFalse(np.isnan(res.ds[name].values).any(), f"{name} left at the NaN fill")
        self.assertEqual(res.n_failed, 0)

    def test_a_short_vector_warns_and_is_recorded_not_dropped(self) -> None:
        WrongLengthVec.n_elements = 1
        with pytest.warns(WorkerContractWarning) as record:
            res = _run(WrongLengthVec())
        # The sweep completed; the bad samples are counted, not fatal.
        self.assertEqual(res.n_failed, 2)
        msg = _contract_messages(record)[0]
        # The message has to carry all three facts, because the symptom the user
        # would otherwise see is an all-NaN column with nothing pointing at 'v'.
        self.assertIn("'v'", msg)
        self.assertIn("size=2", msg)
        self.assertIn("1 element", msg)
        # The cells stay at the missing sentinel — failed, not fabricated.
        for name in WrongLengthVec.param.v.index_names():
            self.assertTrue(np.isnan(res.ds[name].values).all())

    def test_a_long_vector_is_also_recorded(self) -> None:
        WrongLengthVec.n_elements = 3
        with pytest.warns(WorkerContractWarning) as record:
            res = _run(WrongLengthVec())
        self.assertEqual(res.n_failed, 2)
        self.assertIn("3 element", _contract_messages(record)[0])

    def test_a_non_sequence_is_recorded_naming_the_type(self) -> None:
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

        n_failed_before = res.n_failed
        with pytest.warns(WorkerContractWarning) as record:
            collector.store_results(
                JobFuture(job=job, res={"v": 3.0}),
                res,
                _Worker(),
                bn.BenchRunCfg(),
            )
        self.assertEqual(res.n_failed, n_failed_before + 1)
        msg = _contract_messages(record)[0]
        self.assertIn("'v'", msg)
        self.assertIn("float", msg)
        # The recorded failure is distinguishable from a catch= sample fault.
        self.assertIn("WorkerContractError", res.failed_samples[-1].exception)


# ---------------------------------------------------------------------------
# B3 -- worker returned None
# ---------------------------------------------------------------------------


class TestWorkerReturnedNothing(unittest.TestCase):
    """B3: loud or silent used to be chosen by an unrelated config knob.

    Now it is uniformly loud-but-nonfatal on both execution paths: recorded,
    warned, counted — never a green run with ``n_failed == 0``, and never an
    aborted run that loses the samples already collected."""

    def test_serial_records_and_warns(self) -> None:
        with pytest.warns(WorkerContractWarning) as record:
            res = _run(ReturnsNothing())
        self.assertEqual(res.n_failed, 2)
        self.assertIn("returned None", _contract_messages(record)[0])
        # Nothing fabricated: the cells hold the missing sentinel.
        self.assertTrue(np.isnan(res.ds["y"].values).all())

    def test_multiprocessing_records_and_warns_too(self) -> None:
        """The path that used to complete green with an all-sentinel dataset."""
        with pytest.warns(WorkerContractWarning) as record:
            res = _run(ReturnsNothing(), executor=Executors.MULTIPROCESSING)
        self.assertEqual(res.n_failed, 2)
        self.assertIn("returned None", _contract_messages(record)[0])

    def test_the_message_says_what_to_do(self) -> None:
        # require_worker_result itself still raises (a pure check); the
        # record-and-continue disposition lives in store_results.
        with self.assertRaises(WorkerContractError) as ctx:
            require_worker_result(None, "job-42")
        msg = str(ctx.exception)
        self.assertIn("job-42", msg)
        self.assertIn("super().__call__(**kwargs)", msg)

    def test_contract_error_is_a_type_error(self) -> None:
        """Callers that matched the previous raising behavior still match."""
        self.assertTrue(issubclass(WorkerContractError, TypeError))

    def test_a_real_result_passes_straight_through(self) -> None:
        payload = {"y": 1.0}
        self.assertIs(require_worker_result(payload, "job-1"), payload)

    def test_an_empty_dict_is_not_treated_as_missing(self) -> None:
        """A worker with no result vars returns ``{}``, which is falsy but valid."""
        self.assertEqual(require_worker_result({}, "job-1"), {})


class TestCatchDoesNotChangeContractHandling(unittest.TestCase):
    """Plan 23 decision 2: ``catch=`` tolerates failing *samples*, not a broken harness.

    A contract violation is recorded and warned identically with and without
    ``catch=Exception``. Without this test the fix would look complete while
    ``catch=`` either silently absorbed the violation (the old B2/B3 failure
    mode) or its absence turned the violation back into a mid-run crash.
    """

    def tearDown(self) -> None:
        WrongLengthVec.n_elements = 2

    def test_catch_does_not_swallow_a_none_return(self) -> None:
        with pytest.warns(WorkerContractWarning):
            res = _run(ReturnsNothing(), catch=Exception)
        self.assertEqual(res.n_failed, 2)
        # The narrow subclass by name: this is the harness's own diagnosis, which is
        # what earns the exemption from `catch=`. A worker-raised
        # WorkerContractError would record as a plain sample fault instead --
        # see TestAWorkerRaisedContractErrorIsStillASampleFault.
        self.assertIn("WorkerReturnedNothingError", res.failed_samples[0].exception)

    def test_catch_does_not_swallow_a_wrong_length_vector(self) -> None:
        WrongLengthVec.n_elements = 1
        with pytest.warns(WorkerContractWarning):
            res = _run(WrongLengthVec(), catch=Exception)
        self.assertEqual(res.n_failed, 2)


class TestAWorkerRaisedContractErrorIsStillASampleFault:
    """The converse of the class above, and the reason ``store_results`` catches
    ``WorkerReturnedNothingError`` rather than its public base class.

    ``catch=`` must not decide the fate of the harness's *own* diagnosis that a job
    produced nothing. It must still decide the fate of a ``WorkerContractError`` a
    **worker** raises — that is an ordinary sample fault as far as dispositions go,
    and it aborted with ``catch=()`` before plan 23 P5.

    Pinned on **both** executors because the regression this guards against was
    visible on only one of them: P5 first moved the handler inside the ``try``
    around ``result()``, which caught every ``WorkerContractError`` surfacing from
    it — so a worker-raised one aborted on SERIAL (where it is raised inside
    ``submit()``, outside that ``try``) while being silently tolerated on
    MULTIPROCESSING with ``catch=()``. Loud or silent chosen by an unrelated knob
    is precisely the defect shape B3 exists to kill.
    """

    @pytest.mark.parametrize(
        "executor", [Executors.SERIAL, Executors.MULTIPROCESSING], ids=["serial", "pool"]
    )
    def test_no_catch_aborts_on_either_executor(self, executor) -> None:
        with pytest.raises(WorkerContractError, match="raised by the worker"):
            _run(RaisesContractError(), executor=executor, catch=())

    @pytest.mark.parametrize(
        "executor", [Executors.SERIAL, Executors.MULTIPROCESSING], ids=["serial", "pool"]
    )
    def test_catch_tolerates_it_on_either_executor(self, executor) -> None:
        """With ``catch=`` it is a tolerated sample fault, like any other raise."""
        res = _run(RaisesContractError(), executor=executor, catch=Exception)
        assert res.n_failed == 2
        assert "raised by the worker" in res.failed_samples[0].exception

    def test_the_harness_diagnosis_is_a_narrow_subclass(self) -> None:
        """What makes the two dispositions separable at all."""
        assert issubclass(bn.WorkerReturnedNothingError, bn.WorkerContractError)
        assert not issubclass(bn.WorkerContractError, bn.WorkerReturnedNothingError)


class TestContractViolationSurfaces(unittest.TestCase):
    """The loudness contract: visible in the report, and gateable at run end."""

    def tearDown(self) -> None:
        WrongLengthVec.n_elements = 2

    def test_failed_samples_appear_in_the_report(self) -> None:
        WrongLengthVec.n_elements = 1
        with pytest.warns(WorkerContractWarning):
            res = _run(WrongLengthVec())
        md = res.failed_samples_markdown()
        self.assertIn("Failed samples", md)
        self.assertIn("x=0", md)
        self.assertIn("WorkerContractError", md)
        # And the auto-plot report actually carries the pane.
        panes = res.to_auto_plots()
        names = [getattr(p, "name", "") for p in panes]
        self.assertIn("Failed Samples", names)

    def test_a_clean_run_gets_no_failure_pane(self) -> None:
        res = _run(WrongLengthVec())
        panes = res.to_auto_plots()
        names = [getattr(p, "name", "") for p in panes]
        self.assertNotIn("Failed Samples", names)

    def test_fail_on_sample_error_gates_contract_violations_at_run_end(self) -> None:
        """Opt-in hard failure still exists — after collection, not mid-run."""
        from bencher.bencher import SampleErrorPolicyError

        WrongLengthVec.n_elements = 1
        with pytest.warns(WorkerContractWarning), self.assertRaises(SampleErrorPolicyError):
            _run(WrongLengthVec(), fail_on_sample_error=True)

    def test_a_missing_result_key_is_recorded_not_fatal(self) -> None:
        """A raw-dict worker omitting a declared result var is the same contract
        shape; it used to abort the sweep with a KeyError."""
        res = _run(WrongLengthVec())
        collector = ResultCollector()
        job = Job(job_id="missing-key", function=lambda **_: None, job_args={"x": 0})

        class _Worker:
            function_input: ClassVar[dict] = {"x": 0}
            index_tuple = (0, 0)
            canonical_input = ("x", 0)

        n_failed_before = res.n_failed
        with pytest.warns(WorkerContractWarning) as record:
            collector.store_results(
                JobFuture(job=job, res={"other": 1.0}),
                res,
                _Worker(),
                bn.BenchRunCfg(),
            )
        self.assertEqual(res.n_failed, n_failed_before + 1)
        self.assertIn("'v'", _contract_messages(record)[0])


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
