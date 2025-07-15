from dataclasses import dataclass
from typing import List
import pytest
from bencher.results.laxtex_result import (
    latex_text,
    format_values_list,
    create_matrix_array,
    input_var_to_latex,
    result_var_to_latex,
    to_latex,
)


@dataclass
class MockVar:
    name: str
    _values: List

    def values(self):
        return self._values


@dataclass
class MockBenchConfig:
    all_vars: List[MockVar]
    result_vars: List[MockVar]


def test_latex_text():
    assert latex_text("test") == r"\text{test} \\"
    assert latex_text("test_var") == r"\text{test var} \\"
    assert latex_text("multiple_under_scores") == r"\text{multiple under scores} \\"


def test_format_values_list():
    short_list = [1, 2, 3]
    long_list = [1, 2, 3, 4, 5, 6, 7]

    assert format_values_list(short_list) == short_list
    assert format_values_list(long_list) == [1, 2, 1, 6, 7]


def test_create_matrix_array():
    short_list = [1, 2, 3]
    long_list = [1, 2, 3, 4, 5, 6, 7]

    assert create_matrix_array(short_list) == r"1\\ 2\\ 3"
    assert create_matrix_array(long_list) == r"1\\ 2\\ ⋮\\ 6\\ 7"


def test_input_var_to_latex():
    var = MockVar(name="test_var", _values=[1, 2, 3])
    result = input_var_to_latex(var)

    assert r"\text{test var}" in result
    assert r"3\times1" in result
    assert r"1\\ 2\\ 3" in result


def test_result_var_to_latex():
    input_var = MockVar(name="input", _values=[1, 2, 3])
    result_var = MockVar(name="result", _values=[])
    bench_cfg = MockBenchConfig(all_vars=[input_var], result_vars=[result_var])

    result = result_var_to_latex(bench_cfg)
    assert r"3" in result
    assert r"\text{result}" in result


def test_to_latex_empty():
    bench_cfg = MockBenchConfig(all_vars=[], result_vars=[])
    assert to_latex(bench_cfg) is None


def test_to_latex():
    input_var = MockVar(name="input", _values=[1, 2, 3])
    result_var = MockVar(name="result", _values=[])
    bench_cfg = MockBenchConfig(all_vars=[input_var], result_vars=[result_var])

    result = to_latex(bench_cfg)
    assert result is not None
    assert r"\text{input}" in result.object
    assert r"\text{result}" in result.object


@pytest.mark.parametrize(
    "name,values,expected_size",
    [
        ("short", [1, 2, 3], "3"),
        ("long", list(range(10)), "10"),
        ("empty", [], "0"),
    ],
)
def test_input_var_sizes(name, values, expected_size):
    var = MockVar(name=name, _values=values)
    result = input_var_to_latex(var)
    assert f"{expected_size}\\times1" in result
