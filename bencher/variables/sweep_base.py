from __future__ import annotations
from typing import List, Any, Tuple
from copy import deepcopy

import numpy as np
import param
from param import Parameterized
import holoviews as hv
import panel as pn
from bencher.utils import hash_sha1

# slots that are shared across all Sweep classes
# param and slots don't work easily with multiple inheritance so define here
shared_slots = ["units", "samples"]


def describe_variable(v: Parameterized, include_samples: bool, value: Any | None = None) -> List[str]:
    """Generate a string description of a variable

    Args:
        v (param.Parameterized): parameter to describe
        debug (bool): Generate a reduced number of samples from the variable
        include_samples (bool): Include a description of the samples

    Returns:
        str: String description of the variable
    """
    indent = "    "
    sampling_str = []
    sampling_str.append(f"{v.name}:")
    if include_samples:
        # sampling_str.append(f"{indent}{v.sampling_str(debug)}")
        sampling_str.append(f"{indent}number of samples: {len(v.values())}")
        sampling_str.append(f"{indent}sample values: {[str(v) for v in v.values()]}")

    if value is not None:
        sampling_str.append(f"{indent}value: {value}")
    if hasattr(v, "units"):
        if v.units != "ul" and len(v.units) > 0:
            sampling_str.append(f"{indent}units: [{v.units}]")
    if v.doc is not None:
        sampling_str.append(f"{indent}docs: {v.doc}")
    for i in range(len(sampling_str)):
        sampling_str[i] = f"{indent}{sampling_str[i]}"
    return sampling_str


class SweepBase(param.Parameter):
    # def __init__(self, **params):
    # super().__init__(**params)
    # self.units = ""
    # slots = ["units", "samples"]
    # __slots__ = shared_slots

    def values(
        self,
    ) -> List[Any]:
        """All sweep classes must implement this method. This generates sample values from based on the parameters bounds and sample number.

        Returns:
            List[Any]: A list of samples from the variable
        """
        raise NotImplementedError

    def hash_persistent(self) -> str:
        """A hash function that avoids the PYTHONHASHSEED 'feature' which returns a different hash value each time the program is run"""
        return hash_sha1((self.units, self.samples))  # pylint: disable=no-member

    def sampling_str(self) -> str:
        """Generate a string representation of the of the sampling procedure"""

        samples = self.values()
        object_str = ",".join([str(i) for i in samples])
        return f"Taking {len(samples)} samples from {self.name} with values: [{object_str}]"

    def as_slider(self) -> pn.widgets.slider.DiscreteSlider:
        """given a sweep variable (self), return the range of values as a panel slider

        Args:
            debug (bool, optional): pass to the sweepvar to produce a full set of variables, or when debug=True, a reduces number of sweep vars. Defaults to False.

        Returns:
            pn.widgets.slider.DiscreteSlider: A panel slider with the values() of the sweep variable
        """
        return pn.widgets.slider.DiscreteSlider(name=self.name, options=list(self.values()))

    def as_dim(self, compute_values=False) -> hv.Dimension:
        """Takes a sweep variable and turns it into a holoview dimension

        Returns:
            hv.Dimension:
        """
        name_tuple = (self.name, self.name)

        params = {}
        if hasattr(self, "bounds") and self.bounds is not None:
            if compute_values:
                params["values"] = self.values()
                # params["range"] = tuple(self.bounds)
            else:
                params["range"] = tuple(self.bounds)
                params["default"] = self.default

        else:
            params["values"] = self.values()
            params["default"] = self.default

        if hasattr(self, "step"):
            params["step"] = getattr(self, "step")

        # TODO investigate why this stopped working after a holoviews update
        # if hasattr(self, "units"):
        # params["unit"] = getattr(self, "units")

        return hv.Dimension(name_tuple, **params)

    def indices_to_samples(self, desires_num_samples, sample_values):
        indices = [
            int(i) for i in np.linspace(0, len(sample_values) - 1, desires_num_samples, dtype=int)
        ]

        if len(indices) > len(sample_values):
            return sample_values

        return [sample_values[i] for i in indices]

    def with_samples(self, samples: int) -> SweepBase:
        output = deepcopy(self)
        # TODO set up class properly. Slightly complicated due to slots
        output.samples = samples  # pylint: disable = attribute-defined-outside-init
        if hasattr(output, "step"):
            # hack TODO fix this
            output.step = None  # pylint: disable = attribute-defined-outside-init
        return output

    def with_sample_values(self, sample_values: list) -> SweepBase:
        output = deepcopy(self)
        # TODO set up class properly. Slightly complicated due to slots
        try:
            output.sample_values = sample_values  # pylint: disable = attribute-defined-outside-init
        except AttributeError:
            output.objects = sample_values  # pylint: disable = attribute-defined-outside-init
        output.samples = len(sample_values)  # pylint: disable = attribute-defined-outside-init
        return output

    def with_const(self, const_value: Any) -> Tuple[SweepBase, Any]:
        """Create a new instance of SweepBase with a constant value.

        Args:
            const_value (Any): The constant value to be associated with the new instance.

        Returns:
            Tuple[SweepBase, Any]: A tuple containing the new instance of SweepBase and the constant value.
        """
        return (deepcopy(self), const_value)

    def with_level(self, level: int = 1, max_level: int = 12) -> SweepBase:
        assert level >= 1
        # TODO work out if the order can be returned in level order always
        samples = [0, 1, 2, 3, 5, 9, 17, 33, 65, 129, 257, 513, 1025, 2049]
        out = self.with_sample_values(self.with_samples(samples[min(max_level, level)]).values())
        return out
