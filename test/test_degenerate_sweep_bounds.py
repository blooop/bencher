"""A bounded sweep may collapse to a single point.

A caller whose range is computed at run time should not have to switch to
``sample_values`` when the range degenerates: that changes the sweep's identity
tuple and moves the benchmark to a different cache and history series.  Relaxing
the guard is not enough on its own -- ``linspace(x, x, N)`` returns N copies and
``arange(x, x, step)`` returns nothing -- so ``values()`` short-circuits.
"""

import numpy as np
import pytest

import bencher as bn


class Cfg(bn.ParametrizedSweep):
    f = bn.FloatSweep(default=0.5, bounds=[0.0, 1.0])
    i = bn.IntSweep(default=2, bounds=[1, 8])
    y = bn.ResultFloat()

    def __call__(self, **kwargs):
        self.update_params_from_kwargs(**kwargs)
        self.y = float(self.f) + float(self.i)
        return self.get_results_values_as_dict()


class StepCfg(bn.ParametrizedSweep):
    f = bn.FloatSweep(default=0.5, bounds=[0.0, 1.0], step=0.25)
    y = bn.ResultFloat()

    def __call__(self, **kwargs):
        self.update_params_from_kwargs(**kwargs)
        self.y = float(self.f)
        return self.get_results_values_as_dict()


@pytest.mark.parametrize("divisions", [1, 2, 3, 4, 5, 6])
def test_float_zero_width_is_one_sample_at_every_resolution(divisions):
    """subsampling cannot subdivide a zero-width interval."""
    sweep = Cfg.param.f.with_bounds(0.3, 0.3)
    sweep = sweep.with_subsampling_divisions(divisions, divisions)
    assert list(sweep.values()) == [pytest.approx(0.3)]


@pytest.mark.parametrize("divisions", [1, 3, 5])
def test_int_zero_width_is_one_sample(divisions):
    sweep = Cfg.param.i.with_bounds(4, 4)
    sweep = sweep.with_subsampling_divisions(divisions, divisions)
    assert list(sweep.values()) == [4]


def test_step_based_zero_width_is_one_sample_not_empty():
    """arange(x, x, step) is empty; the short-circuit must precede it."""
    sweep = StepCfg.param.f.with_bounds(0.5, 0.5)
    assert list(sweep.values()) == [pytest.approx(0.5)]


def test_inverted_bounds_still_raise():
    with pytest.raises(ValueError, match="must not exceed"):
        Cfg.param.f.with_bounds(0.9, 0.1)


def test_explicit_multiple_samples_on_a_point_raises():
    with pytest.raises(ValueError, match="zero-width"):
        Cfg.param.f.with_bounds(0.3, 0.3, samples=5)


def test_samples_one_on_a_point_is_allowed():
    assert list(Cfg.param.f.with_bounds(0.3, 0.3, samples=1).values()) == [pytest.approx(0.3)]


def test_sweep_helper_accepts_a_collapsed_range():
    """The deferred string form is the one a computed range flows through.

    Bencher squeezes a single-valued input var out of the dataset dimensions, so
    the result is zero-dimensional -- exactly what the pre-existing
    ``values=[x]`` workaround produces. What matters is that the point was
    sampled at the collapsed value.
    """
    res = (
        Cfg()
        .to_bench()
        .plot_sweep(
            input_vars=[bn.sweep("f", bounds=(0.3, 0.3))],
            result_vars=["y"],
            auto_plot=False,
        )
    )
    ds = res.to_dataset()
    assert "f" not in ds.sizes
    # y = f + i, with i at its default of 2.
    assert float(ds["y"].values) == pytest.approx(0.3 + 2)


def test_collapsed_bounds_and_explicit_value_agree_on_shape():
    """The new path must behave as the workaround it replaces, shape-wise."""
    shapes = []
    for iv in (bn.sweep("f", bounds=(0.3, 0.3)), bn.sweep("f", [0.3])):
        ds = (
            Cfg()
            .to_bench()
            .plot_sweep(input_vars=[iv], result_vars=["y"], auto_plot=False)
            .to_dataset()
        )
        shapes.append((dict(ds.sizes), float(ds["y"].values)))
    assert shapes[0] == shapes[1]


def test_sweep_helper_rejects_inverted_bounds_at_construction():
    """Not at resolution time, which for a deferred spec is mid-run."""
    with pytest.raises(ValueError, match="low must not exceed high"):
        bn.sweep("f", bounds=(0.9, 0.1))


def test_mixed_degenerate_and_normal_inputs_give_the_expected_shape():
    res = (
        Cfg()
        .to_bench()
        .plot_sweep(
            input_vars=[bn.sweep("f", bounds=(0.3, 0.3)), bn.sweep("i", bounds=(1, 4))],
            result_vars=["y"],
            auto_plot=False,
        )
    )
    ds = res.to_dataset()
    # The collapsed axis is squeezed away; the swept one survives.
    assert "f" not in ds.sizes
    assert ds.sizes["i"] > 1
    assert not np.isnan(ds["y"].values).any()


def test_collapsed_bounds_and_sample_values_are_different_identities():
    """A documented contract, so a later 'simplification' cannot merge the two.

    ``bounds=(x, x)`` and ``values=[x]`` sample the same point but are different
    declarations; the identity tuple folds bounds and sample_values separately.
    """
    by_bounds = Cfg.param.f.with_bounds(0.3, 0.3)
    by_values = Cfg.param.f.with_sample_values([0.3])
    assert list(by_bounds.values()) == list(by_values.values())
    assert by_bounds.hash_persistent() != by_values.hash_persistent()


def test_existing_ranges_are_unaffected():
    """No currently-valid bounds input may change identity or sample count."""
    normal = Cfg.param.f.with_bounds(0.0, 1.0)
    assert len(list(normal.values())) > 1
    assert normal.hash_persistent() == Cfg.param.f.with_bounds(0.0, 1.0).hash_persistent()
