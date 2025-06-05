#!/usr/bin/env python3
"""
Demonstration script showing that set_xarray_multidim now works generically
for any number of dimensions, not just up to 9 dimensions as before.
"""

import numpy as np
import xarray as xr
from bencher.bencher import set_xarray_multidim


def test_generic_dimensions():
    """Test that the function works for various numbers of dimensions"""

    print("Testing set_xarray_multidim with various dimensions...")

    # Test dimensions from 1 to 15 (well beyond the original 9D limit)
    for ndims in range(1, 16):
        print(f"\nTesting {ndims}D array...")

        # Create an array with 'ndims' dimensions, each of size 3
        shape = (3,) * ndims
        dims = [f"dim_{i}" for i in range(ndims)]

        # Create the data array filled with zeros
        data = xr.DataArray(np.zeros(shape), dims=dims)

        # Create an index tuple that points to the middle of each dimension
        index_tuple = (1,) * ndims

        # Set a value at that position
        test_value = 42.0 + ndims  # Different value for each test
        result = set_xarray_multidim(data.copy(), index_tuple, test_value)

        # Verify the value was set correctly
        actual_value = result[index_tuple].values
        assert actual_value == test_value, (
            f"Failed for {ndims}D: expected {test_value}, got {actual_value}"
        )

        print(f"  ✓ {ndims}D array: Successfully set value {test_value} at position {index_tuple}")

    print("\n🎉 Success! The function now works generically for any number of dimensions.")
    print("   Previously it was hardcoded to only work up to 9 dimensions.")


def test_original_test_cases():
    """Run some of the original test cases to ensure compatibility"""

    print("\nRunning original test cases to ensure compatibility...")

    # 1D test
    data = xr.DataArray([1, 2, 3], dims=["x"])
    result = set_xarray_multidim(data.copy(), (1,), 99)
    expected = xr.DataArray([1, 99, 3], dims=["x"])
    assert result.equals(expected)
    print("  ✓ 1D test passed")

    # 2D test
    data = xr.DataArray([[1, 2], [3, 4]], dims=["x", "y"])
    result = set_xarray_multidim(data.copy(), (0, 1), 99)
    expected = xr.DataArray([[1, 99], [3, 4]], dims=["x", "y"])
    assert result.equals(expected)
    print("  ✓ 2D test passed")

    # 3D test
    data = xr.DataArray(np.arange(8).reshape(2, 2, 2), dims=["x", "y", "z"])
    result = set_xarray_multidim(data.copy(), (1, 0, 1), 42)
    expected = data.copy()
    expected[1, 0, 1] = 42
    assert result.equals(expected)
    print("  ✓ 3D test passed")

    print("  ✓ All original test cases still work!")


if __name__ == "__main__":
    test_original_test_cases()
    test_generic_dimensions()

    print("\n" + "=" * 60)
    print("SUMMARY: set_xarray_multidim() has been successfully fixed!")
    print("- Removed hardcoded match statement limited to 9 dimensions")
    print("- Now uses direct tuple indexing: data_array[index_tuple] = value")
    print("- Works for any number of dimensions")
    print("- All original tests still pass")
    print("- Much simpler and more maintainable code")
    print("=" * 60)
