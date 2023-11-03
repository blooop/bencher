
# Generated by CodiumAI
import holoviews as hv
from bencher.dimension_grid import DimensionGrid
import numpy as np
from collections import OrderedDict


import unittest

class TestDimensionGrid(unittest.TestCase):

    # can create a DimensionGrid instance with a list of hv.Dimension objects and a number of samples
    def test_create_instance_with_number_of_samples_with_assert_array_equal(self):
        dims = [hv.Dimension('x', range=(0, 1)), hv.Dimension('y', range=(0, 1))]
        samples = 10
        grid = DimensionGrid(dims, samples)
        np.testing.assert_array_equal(grid.dims, dims)
        np.testing.assert_array_equal(grid.values, [np.linspace(0, 1, samples), np.linspace(0, 1, samples)])
        np.testing.assert_array_equal(grid.coord_len, [samples, samples])
        self.assertEqual(grid.dim_names, ['x', 'y'])
        for key in grid.coords:
            np.testing.assert_array_equal(grid.coords[key], np.linspace(0, 1, samples))

    # can create a DimensionGrid instance with a list of hv.Dimension objects and a list of sample sizes
    def test_create_instance_with_list_of_sample_sizes(self):
        dims = [hv.Dimension('x', range=(0, 1)), hv.Dimension('y', range=(0, 1))]
        samples = [10, 5]
        grid = DimensionGrid(dims, samples)
        self.assertEqual(grid.dims, dims)
        self.assertTrue(np.array_equal(grid.values[0], np.linspace(0, 1, samples[0])))
        self.assertTrue(np.array_equal(grid.values[1], np.linspace(0, 1, samples[1])))
        self.assertEqual(grid.coord_len, samples)
        self.assertEqual(grid.dim_names, ['x', 'y'])
        for i in range(len(grid.coords)):
            self.assertTrue(np.array_equal(list(grid.coords.values())[i], np.linspace(0, 1, samples[i])))

    # can generate inputs as an iterable using the inputs_iterable method
    def test_generate_inputs_iterable(self):
        dims = [hv.Dimension('x', range=(0, 1)), hv.Dimension('y', range=(0, 1))]
        samples = [2, 2]
        grid = DimensionGrid(dims, samples)
        inputs = grid.inputs_iterable()
        expected_inputs = [(0.0, 0.0), (0.0, 1.0), (1.0, 0.0), (1.0, 1.0)]
        self.assertEqual(list(inputs), expected_inputs)

    # can create a DimensionGrid instance with an empty list of hv.Dimension objects
    def test_create_instance_with_empty_list_of_dimensions(self):
        dims = []
        samples = 10
        grid = DimensionGrid(dims, samples)
        self.assertEqual(grid.dims, dims)
        self.assertEqual(grid.values, [])
        self.assertEqual(grid.coord_len, [])
        self.assertEqual(grid.dim_names, [])
        self.assertEqual(grid.coords, OrderedDict())

    # can create a DimensionGrid instance with a list of hv.Dimension objects and a list of sample sizes that does not match the number of dimensions
    def test_create_instance_with_mismatched_sample_sizes(self):
        dims = [hv.Dimension('x', range=(0, 1)), hv.Dimension('y', range=(0, 1))]
        samples = [10]
        DimensionGrid(dims, samples)

    # can apply a function to the inputs generated by the grid with a chunk size that is larger than the number of inputs, after fixing the AttributeError
    def test_apply_function_with_large_chunk_size_fixed_fixed(self):
        dims = [hv.Dimension('x', range=(0, 1)), hv.Dimension('y', range=(0, 1)), hv.Dimension('z', range=(0, 1))]
        samples = [2,3,5]
        grid = DimensionGrid(dims, samples)
        def build_tensor_cb(x, y,z):
            return np.array([x, y,z])
        def process_tensor_cb(tensors):
            return np.square(tensors)
        
        chunk_sizes = list(range(2,31))
        chunk_sizes.append(None)

        results =[]     
        for i in chunk_sizes:       
            results.append(grid.apply_fn(build_tensor_cb, process_tensor_cb, i))

        compare = results[-1]
        for r in results:
            self.assertEqual(r,compare)
        # from more_itertools import pairwise
        # for res_pair in pairwise(results,2)
        # expected_result = np.array([[0.0, 1.0, 1.0, 2.0]])
        # self.assertEqual(result, expected_result)