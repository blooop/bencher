import bencher as bn
import unittest
from bencher.utils import (
    get_nearest_coords,
    capitalise_words,
    int_to_col,
    get_nearest_coords1D,
    callable_name,
    lerp,
    listify,
    tabs_in_markdown,
    mult_tuple,
)
from functools import partial
import xarray as xr


class ExampleClass(bn.ParametrizedSweep):
    iv1 = bn.FloatSweep()
    rv1 = bn.ResultVar()


class TestBencherUtils(unittest.TestCase):
    def test_get_inputs(self) -> None:
        ex_instance = ExampleClass()
        inputs = ex_instance.get_inputs_only()

        print(inputs)

        self.assertEqual(len(inputs), 1)
        self.assertEqual(inputs[0].name, "iv1")

    def test_get_results(self) -> None:
        ex_instance = ExampleClass()
        results = ex_instance.get_results_only()

        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].name, "rv1")

    def test_get_inputs_and_results(self) -> None:
        ex_instance = ExampleClass()
        inputs, results = ex_instance.get_input_and_results()

        self.assertEqual(len(inputs), 1)
        self.assertEqual(len(results), 1)
        self.assertEqual(inputs["iv1"].name, "iv1")
        self.assertEqual(results["rv1"].name, "rv1")

    def test_get_results_values_as_dict(self) -> None:
        ex_instance = ExampleClass()

        ex_instance.rv1 = 3

        res = ex_instance.get_results_values_as_dict()

        self.assertEqual(res["rv1"], 3)

        # Tests that a named tuple with fields of different data types is created successfully

    def test_different_datatypes_namedtuple(self):
        result = bn.make_namedtuple("Test", field1=1, field2="value2", field3=True)
        self.assertEqual(result.field1, 1)
        self.assertEqual(result.field2, "value2")
        self.assertEqual(result.field3, True)

        # Tests that the function returns an empty tuple when an empty dictionary is passed as input

    def test_edge_case_empty_dictionary(self) -> None:
        input_dict = {}
        expected_output = ()
        self.assertEqual(bn.hmap_canonical_input(input_dict), expected_output)

    def test_dictionary_order(self) -> None:
        dic1 = {"x": 1, "y": 2}
        dic2 = {"y": 2, "x": 1}

        self.assertEqual(
            bn.hmap_canonical_input(dic1),
            bn.hmap_canonical_input(dic2),
        )

    def test_mult_tuple(self) -> None:
        self.assertTupleEqual(mult_tuple((1, 2, 3), 2), (2, 4, 6))

    # Tests that the function returns the nearest coordinate name value pair for a dataset containing multiple coordinates
    def test_multiple_coordinates(self):
        ds = xr.Dataset({"x": [1, 2, 3], "y": [4, 5, 6]})
        result = get_nearest_coords(ds, x=2.5, y=5.5)
        self.assertEqual(result, {"x": 3, "y": 6})

    def test_capitalise_words(self):
        self.assertEqual("Camel Case", capitalise_words("camel case"))

    def test_int_to_col(self):
        self.assertEqual(int_to_col(0), (0.95, 0.475, 0.475))
        self.assertEqual(int_to_col(0, alpha=1), (0.95, 0.475, 0.475, 1))

    def test_nearest_coords(self):
        self.assertEqual(get_nearest_coords1D(1, [0, 1, 2]), 1)
        self.assertEqual(get_nearest_coords1D(100, [0, 1, 2]), 2)
        self.assertEqual(get_nearest_coords1D("b", ["a", "b", "c"]), "b")

    def test_returns_name_of_original_function_for_partial_function(self):
        # Arrange
        def original_function():
            pass

        partial_function = partial(original_function)

        # Act
        result = callable_name(partial_function)

        # Assert
        self.assertEqual(result, "original_function")

    # The function returns the name of a given callable function.
    def test_returns_name_of_callable_function(self) -> None:
        # Arrange
        def my_function():
            pass

        # Act
        result = callable_name(my_function)

        # Assert
        self.assertEqual(result, "my_function")

    def test_callable_name_incorrect(self) -> None:
        self.assertEqual(callable_name("lol"), "lol")

    def test_lerp(self):
        # Given valid input values, the function should return the expected output.
        result = lerp(5, 0, 10, 0, 100)
        self.assertEqual(result, 50)

        # When the input value is equal to the input_low, the function should return output_low.
        result = lerp(0, 0, 10, 0, 100)
        self.assertEqual(result, 0)

        # When the input value is equal to the input_high, the function should return output_high.
        result = lerp(10, 0, 10, 0, 100)
        self.assertEqual(result, 100)

        # When the input value is None, the function should raise a TypeError.
        with self.assertRaises(TypeError):
            lerp(None, 0, 10, 0, 100)

        # When the input_low is None, the function should raise a TypeError.
        with self.assertRaises(TypeError):
            lerp(5, None, 10, 0, 100)

        # When the input_high is None, the function should raise a TypeError.
        with self.assertRaises(TypeError):
            lerp(5, 0, None, 0, 100)

    def test_listify(self):
        obj = "a"
        self.assertEqual([obj], listify(obj))
        self.assertEqual([obj], listify([obj]))
        self.assertEqual([obj], listify((obj)))
        self.assertEqual(None, listify(None))

    def test_converts_single_tab_to_nbsp(self):
        input_str = "This is\ta test"
        expected_output = "This is&nbsp;&nbsp;a test"
        self.assertEqual(tabs_in_markdown(input_str), expected_output)

    def test_converts_multi_tab_to_nbsp(self):
        input_str = "This is\ta test"
        expected_output = "This is&nbsp;&nbsp;&nbsp;&nbsp;a test"
        self.assertEqual(tabs_in_markdown(input_str, 4), expected_output)

    def test_handles_empty_string(self):
        input_str = ""
        expected_output = ""
        self.assertEqual(tabs_in_markdown(input_str), expected_output)
