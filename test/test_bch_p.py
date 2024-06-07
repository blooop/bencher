# Generated by CodiumAI

import pytest
from bencher import p


class TestP:

    # returns correct dictionary with all parameters provided
    def test_returns_correct_dict_all_params(self):
        result = p(name="param1", values=[1, 2, 3], samples=10, max_level=5)
        assert result == {"name": "param1", "values": [1, 2, 3], "samples": 10, "max_level": 5}

    # returns correct dictionary with only name provided
    def test_returns_correct_dict_name_only(self):
        result = p(name="param1")
        assert result == {"name": "param1", "values": None, "samples": None, "max_level": None}

    # returns correct dictionary with name and values provided
    def test_returns_correct_dict_name_and_values(self):
        result = p(name="param1", values=[1, 2, 3])
        assert result == {"name": "param1", "values": [1, 2, 3], "samples": None, "max_level": None}

    # raises ValueError when max_level is 0
    def test_raises_value_error_max_level_zero(self):
        with pytest.raises(ValueError, match="max_level must be greater than 0"):
            p(name="param1", max_level=0)

    # raises ValueError when max_level is negative
    def test_raises_value_error_max_level_negative(self):
        with pytest.raises(ValueError, match="max_level must be greater than 0"):
            p(name="param1", max_level=-1)

    # raises ValueError when samples is 0
    def test_raises_value_error_samples_zero(self):
        with pytest.raises(ValueError, match="samples must be greater than 0"):
            p(name="param1", samples=0)
