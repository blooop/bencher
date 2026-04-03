"""Tests that FloatSweep always returns floats and IntSweep always returns ints,
regardless of the Python types passed for bounds or sample_values."""

import numpy as np

from bencher.variables.inputs import FloatSweep, IntSweep


class TestFloatSweepTypeCoercion:
    def test_int_bounds_linspace_returns_float(self):
        vals = FloatSweep(bounds=[0, 5], samples=6).values()
        assert all(isinstance(v, (float, np.floating)) for v in vals)

    def test_int_bounds_arange_returns_float(self):
        vals = FloatSweep(bounds=[0, 5], step=1).values()
        assert all(isinstance(v, (float, np.floating)) for v in vals)

    def test_mixed_bounds_coerced_to_float(self):
        fs = FloatSweep(bounds=[0, 5.0])
        assert all(isinstance(b, float) for b in fs.softbounds)

    def test_all_int_bounds_coerced_to_float(self):
        fs = FloatSweep(bounds=[0, 5])
        assert all(isinstance(b, float) for b in fs.softbounds)

    def test_int_sample_values_returned_as_float(self):
        vals = FloatSweep(sample_values=[0, 1, 2]).values()
        assert all(isinstance(v, float) for v in vals)

    def test_with_bounds_int_args_stored_as_float(self):
        fs = FloatSweep(bounds=[0.0, 5.0], samples=3).with_bounds(0, 10, 3)
        assert all(isinstance(b, float) for b in fs.softbounds)
        assert all(isinstance(v, (float, np.floating)) for v in fs.values())

    def test_default_from_int_sample_values_is_float(self):
        fs = FloatSweep(sample_values=[0, 1, 2])
        assert isinstance(fs.default, float)


class TestIntSweepTypeCoercion:
    def test_float_bounds_do_not_crash(self):
        vals = IntSweep(bounds=[0.0, 5.0]).values()
        assert all(isinstance(v, (int, np.integer)) for v in vals)

    def test_float_sample_values_coerced_to_int(self):
        vals = IntSweep(sample_values=[1.0, 2.0, 3.0]).values()
        assert all(isinstance(v, (int, np.integer)) for v in vals)
        assert vals == [1, 2, 3]

    def test_with_bounds_float_args_stored_as_int(self):
        ints = IntSweep(bounds=[0, 5]).with_bounds(0.0, 10.0)
        assert all(isinstance(b, int) for b in ints.softbounds)

    def test_samples_count_is_int_with_float_bounds(self):
        ints = IntSweep(bounds=[0.0, 5.0])
        assert isinstance(ints.samples, int)
