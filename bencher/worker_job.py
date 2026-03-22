from __future__ import annotations

from typing import Any
from dataclasses import dataclass, field
from .utils import hash_sha1
from bencher.utils import hmap_canonical_input


@dataclass
class WorkerJob:
    """Represents a benchmark worker job with input variables and caching information.

    This class encapsulates the information needed to execute a benchmark function,
    including input variables, dimension information, and caching metadata. It handles
    the preparation of function inputs and calculation of hash signatures for caching.

    Attributes:
        function_input_vars (list): The values of the input variables to pass to the function
        index_tuple (tuple[int]): The indices of these values in the N-dimensional result array
        dims_name (list[str]): The names of the input dimensions
        constant_inputs (dict): Dictionary of any constant input values
        bench_cfg_sample_hash (str): Hash of the benchmark configuration without repeats
        tag (str): Tag for grouping related jobs
        function_input (dict): Complete input as a dictionary with dimension names as keys
        canonical_input (tuple[Any]): Canonical representation of inputs for caching
        fn_inputs_sorted (list[tuple[str, Any]]): Sorted representation of function inputs
        function_input_signature_pure (str): Hash of the function inputs and tag
        found_in_cache (bool): Whether this job result was found in cache
        msgs (list[str]): Messages related to this job's execution
    """

    function_input_vars: list[Any]
    index_tuple: tuple[int, ...]
    dims_name: list[str]
    constant_inputs: dict
    bench_cfg_sample_hash: str
    tag: str

    function_input: dict | None = None
    canonical_input: tuple[Any] | None = None
    fn_inputs_sorted: list[tuple[str, Any]] | None = None
    function_input_signature_pure: str | None = None
    found_in_cache: bool = False
    msgs: list[str] = field(default_factory=list)

    def setup_hashes(self) -> None:
        """Set up the function inputs and calculate hash signatures for caching.

        This method prepares the function inputs by combining function input variables
        with dimensions and constant inputs. It also calculates hash signatures used
        for caching results and tracking job execution.
        """
        self.function_input = dict(zip(self.dims_name, self.function_input_vars))

        self.canonical_input = hmap_canonical_input(self.function_input)

        if self.constant_inputs is not None:
            self.function_input = self.function_input | self.constant_inputs

        # store a tuple of the inputs as keys for a holomap
        # the signature is the hash of the inputs to to the function + meta variables such as repeat and time + the hash of the benchmark sweep as a whole (without the repeats hash)
        self.fn_inputs_sorted = sorted(self.function_input.items())
        self.function_input_signature_pure = hash_sha1((self.fn_inputs_sorted, self.tag))
