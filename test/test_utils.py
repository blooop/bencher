import ast
import inspect
import textwrap
import unittest
from functools import partial

import pytest
import xarray as xr

import bencher as bn
from bencher.utils import (
    callable_name,
    capitalise_words,
    get_nearest_coords,
    get_nearest_coords1D,
    int_to_col,
    lerp,
    listify,
    mult_tuple,
    publish_file,
    tabs_in_markdown,
)


class ExampleClass(bn.ParametrizedSweep):
    iv1 = bn.FloatSweep()
    rv1 = bn.ResultFloat()


class TestBencherUtils(unittest.TestCase):
    def test_get_inputs(self) -> None:
        ex_instance = ExampleClass()
        inputs = ex_instance.get_inputs_only()

        assert len(inputs) == 1
        assert inputs[0].name == "iv1"

    def test_get_results(self) -> None:
        ex_instance = ExampleClass()
        results = ex_instance.get_results_only()

        assert len(results) == 1
        assert results[0].name == "rv1"

    def test_get_inputs_and_results(self) -> None:
        ex_instance = ExampleClass()
        inputs, results = ex_instance.get_input_and_results()

        assert len(inputs) == 1
        assert len(results) == 1
        assert inputs["iv1"].name == "iv1"
        assert results["rv1"].name == "rv1"

    def test_get_results_values_as_dict(self) -> None:
        ex_instance = ExampleClass()

        ex_instance.rv1 = 3

        res = ex_instance.get_results_values_as_dict()

        assert res["rv1"] == 3

        # Tests that a named tuple with fields of different data types is created successfully

    def test_different_datatypes_namedtuple(self):
        result = bn.make_namedtuple("Test", field1=1, field2="value2", field3=True)
        assert result.field1 == 1
        assert result.field2 == "value2"
        assert result.field3 is True

        # Tests that the function returns an empty tuple when an empty dictionary is passed as input

    def test_edge_case_empty_dictionary(self) -> None:
        input_dict = {}
        expected_output = ()
        assert bn.hmap_canonical_input(input_dict) == expected_output

    def test_dictionary_order(self) -> None:
        dic1 = {"x": 1, "y": 2}
        dic2 = {"y": 2, "x": 1}

        assert bn.hmap_canonical_input(dic1) == bn.hmap_canonical_input(dic2)

    def test_mult_tuple(self) -> None:
        assert mult_tuple((1, 2, 3), 2) == (2, 4, 6)

    # Tests that the function returns the nearest coordinate name value pair for a dataset containing multiple coordinates
    def test_multiple_coordinates(self):
        ds = xr.Dataset({"x": [1, 2, 3], "y": [4, 5, 6]})
        result = get_nearest_coords(ds, x=2.5, y=5.5)
        assert result == {"x": 3, "y": 6}

    def test_capitalise_words(self):
        assert capitalise_words("camel case") == "Camel Case"

    def test_int_to_col(self):
        assert int_to_col(0) == (0.95, 0.475, 0.475)
        assert int_to_col(0, alpha=1) == (0.95, 0.475, 0.475, 1)

    def test_nearest_coords(self):
        assert get_nearest_coords1D(1, [0, 1, 2]) == 1
        assert get_nearest_coords1D(100, [0, 1, 2]) == 2
        assert get_nearest_coords1D("b", ["a", "b", "c"]) == "b"

    def test_returns_name_of_original_function_for_partial_function(self):
        # Arrange
        def original_function():
            pass

        partial_function = partial(original_function)

        # Act
        result = callable_name(partial_function)

        # Assert
        assert result == "original_function"

    # The function returns the name of a given callable function.
    def test_returns_name_of_callable_function(self) -> None:
        # Arrange
        def my_function():
            pass

        # Act
        result = callable_name(my_function)

        # Assert
        assert result == "my_function"

    def test_callable_name_incorrect(self) -> None:
        assert callable_name("lol") == "lol"

    def test_lerp(self):
        # Given valid input values, the function should return the expected output.
        result = lerp(5, 0, 10, 0, 100)
        assert result == 50

        # When the input value is equal to the input_low, the function should return output_low.
        result = lerp(0, 0, 10, 0, 100)
        assert result == 0

        # When the input value is equal to the input_high, the function should return output_high.
        result = lerp(10, 0, 10, 0, 100)
        assert result == 100

        # When the input value is None, the function should raise a TypeError.
        with pytest.raises(TypeError):
            lerp(None, 0, 10, 0, 100)

        # When the input_low is None, the function should raise a TypeError.
        with pytest.raises(TypeError):
            lerp(5, None, 10, 0, 100)

        # When the input_high is None, the function should raise a TypeError.
        with pytest.raises(TypeError):
            lerp(5, 0, None, 0, 100)

    def test_listify(self):
        obj = "a"
        assert [obj] == listify(obj)
        assert [obj] == listify([obj])
        assert [obj] == listify(obj)
        assert listify(None) is None

    def test_converts_single_tab_to_nbsp(self):
        input_str = "This is\ta test"
        expected_output = "This is&nbsp;&nbsp;a test"
        assert tabs_in_markdown(input_str) == expected_output

    def test_converts_multi_tab_to_nbsp(self):
        input_str = "This is\ta test"
        expected_output = "This is&nbsp;&nbsp;&nbsp;&nbsp;a test"
        assert tabs_in_markdown(input_str, 4) == expected_output

    def test_handles_empty_string(self):
        input_str = ""
        expected_output = ""
        assert tabs_in_markdown(input_str) == expected_output


class TestPublishFileContract(unittest.TestCase):
    """publish_file's declared return type must match what it actually returns.

    It was annotated ``-> str`` and documented to return the published file's
    URL, but the body ends at the ``git push`` and returns ``None`` (plan 23 B4).
    Asserted via the signature rather than by calling it, so no git remote is
    touched. ``from __future__ import annotations`` in ``bencher/utils.py`` makes
    annotations strings, hence the comparison against ``"None"``.
    """

    def test_return_annotation_is_none(self):
        annotation = inspect.signature(publish_file).return_annotation
        assert annotation in (None, "None"), f"publish_file claims -> {annotation}"

    def test_body_has_no_return_value(self):
        # No `return <expr>` anywhere: nothing for a caller to consume.
        tree = ast.parse(textwrap.dedent(inspect.getsource(publish_file)))
        returns = [n for n in ast.walk(tree) if isinstance(n, ast.Return) and n.value is not None]
        assert returns == []
