import warnings

import pytest
from bencher import p, sweep


class TestSweep:
    def test_values_with_samples_raises(self):
        with pytest.raises(ValueError, match="Cannot combine"):
            sweep(name="param1", values=[1, 2, 3], samples=10)

    def test_values_with_bounds_raises(self):
        with pytest.raises(ValueError, match="Cannot combine"):
            sweep(name="param1", values=[1, 2, 3], bounds=(0, 10))

    def test_returns_correct_dict_name_only(self):
        result = sweep(name="param1")
        assert result == {
            "name": "param1",
            "values": None,
            "samples": None,
            "max_level": None,
            "bounds": None,
        }

    def test_returns_correct_dict_name_and_values(self):
        result = sweep(name="param1", values=[1, 2, 3])
        assert result == {
            "name": "param1",
            "values": [1, 2, 3],
            "samples": None,
            "max_level": None,
            "bounds": None,
        }

    def test_returns_correct_dict_with_bounds(self):
        result = sweep(name="param1", bounds=(0, 10))
        assert result == {
            "name": "param1",
            "values": None,
            "samples": None,
            "max_level": None,
            "bounds": (0, 10),
        }

    def test_returns_correct_dict_with_bounds_and_samples(self):
        result = sweep(name="param1", bounds=(0, 10), samples=5)
        assert result == {
            "name": "param1",
            "values": None,
            "samples": 5,
            "max_level": None,
            "bounds": (0, 10),
        }

    def test_raises_value_error_max_level_zero(self):
        with pytest.raises(ValueError, match="max_level must be greater than 0"):
            sweep(name="param1", max_level=0)

    def test_raises_value_error_max_level_negative(self):
        with pytest.raises(ValueError, match="max_level must be greater than 0"):
            sweep(name="param1", max_level=-1)

    def test_raises_value_error_samples_zero(self):
        with pytest.raises(ValueError, match="samples must be greater than 0"):
            sweep(name="param1", samples=0)


class TestPDeprecation:
    def test_p_emits_deprecation_warning(self):
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            result = p(name="param1", values=[1, 2])
            assert len(w) == 1
            assert issubclass(w[0].category, DeprecationWarning)
            assert "bn.sweep()" in str(w[0].message)
        assert result["name"] == "param1"
        assert result["values"] == [1, 2]

    def test_p_returns_same_as_sweep(self):
        with warnings.catch_warnings(record=True):
            warnings.simplefilter("always")
            p_result = p(name="x", bounds=(0, 1), samples=5)
        sweep_result = sweep(name="x", bounds=(0, 1), samples=5)
        assert p_result == sweep_result
