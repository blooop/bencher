
import xarray as xr
import holoviews as hv
from collections import OrderedDict
from sortedcontainers import SortedDict
from typing import List, Iterable, Callable, Any
import itertools
from more_itertools import chunked
import numpy as np

def values_from_dim(dim: hv.Dimension, samples):
    return np.linspace(dim.range[0], dim.range[1], samples)


class DimensionGrid:
    """
    A class for creating a grid of dimensions and their corresponding coordinate values."""

    def __init__(self, dims: List[hv.Dimension], samples: int | Iterable[int]) -> None:
        self.dims = dims
        if not isinstance(samples, Iterable):
            samples = [samples] * len(dims)
        self.values = [values_from_dim(d, s) for d, s in zip(self.dims, samples)]
        self.coord_len = [len(v) for v in self.values]
        self.dim_names = [d.name for d in dims]
        self.coords = OrderedDict([(d.name, v) for d, v in zip(dims, self.values)])

    def inputs_iterable(self):
        """
        Generates inputs as an iterable by taking the Cartesian product of the coordinate values for each dimension.

        Returns:
            Iterable: An iterable containing the inputs.
        """
        return itertools.product(*self.values)

    def inputs_dict(self) -> list[SortedDict]:
        """
        Generates inputs as a list of dictionaries, where each dictionary represents a combination of dimension names and their corresponding coordinate values.

        Returns:
            list[SortedDict]: A list of dictionaries representing the inputs.
        """
        return [SortedDict(zip(self.dim_names, i)) for i in self.inputs_iterable()]

    def to_datarray(self, data: List[Any], name: str) -> xr.DataArray:
        """
        Converts the data to a xr.DataArray with the dimensions and coordinates of the grid. It also sets attributes for each dimension, such as units, long name, and description.

        Args:
            data (List[Any]): The data to be converted.
            name (str): The name of the data.

        Returns:
            xr.DataArray: The converted data as a xr.DataArray.
        """
        da = xr.DataArray(data=data, dims=self.dim_names, coords=self.coords, name=name)
        for d in self.dims:
            attrs = da[d.name].attrs
            attrs["units"] = d.unit
            attrs["longname"] = d.name
            attrs["description"] = d.label
        return da

    def to_hv_dataset(self, data: List[Any], name: str) -> hv.Dataset:
        """
        Converts the data to a hv.Dataset with the dimensions and coordinates of the grid.

        Args:
            data (List[Any]): The data to be converted.
            name (str): The name of the data.

        Returns:
            hv.Dataset: The converted data as a hv.Dataset.
        """
        return hv.Dataset(self.to_datarray(data, name))

    def apply_fn(self, build_tensor_cb: Callable, process_tensor_cb: Callable, chunk_size=None):
        """
        Applies a function to the inputs generated by the grid in chunks. It calls the build_tensor_cb function to build tensors from the inputs and the process_tensor_cb function to process the tensors. The results are combined and reshaped based on the coordinate lengths of the grid.

        Args:
            build_tensor_cb (Callable): The function to build tensors from the inputs.
            process_tensor_cb (Callable): The function to process the tensors.
            chunk_size (int, optional): The size of each chunk. Defaults to None.

        Returns:
            np.ndarray: The combined and reshaped results.
        """
        inputs = self.inputs_iterable()
        outputs = []
        chunk_num=1
        for chunk in chunked(inputs, chunk_size):
            input_dict = []
            for i in chunk:
                inp = dict(zip(self.dim_names, i))
                input_dict.append(build_tensor_cb(**inp))
            print(f"chunk {chunk_num} size: {len(input_dict)}")
            chunk_num+=1
            res =  process_tensor_cb(input_dict)
            if hasattr(res,"cpu"):
                res = process_tensor_cb(input_dict).cpu().numpy()
            outputs.append(res)
        combined = np.vstack(outputs)
        return combined.reshape(self.coord_len)
