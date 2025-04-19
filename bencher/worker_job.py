from typing import List, Tuple, Any
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
        function_input_vars (List): The values of the input variables to pass to the function
        index_tuple (Tuple[int]): The indices of these values in the N-dimensional result array
        dims_name (List[str]): The names of the input dimensions
        constant_inputs (dict): Dictionary of any constant input values
        bench_cfg_sample_hash (str): Hash of the benchmark configuration without repeats
        tag (str): Tag for grouping related jobs
        function_input (dict): Complete input as a dictionary with dimension names as keys
        canonical_input (Tuple[Any]): Canonical representation of inputs for caching
        fn_inputs_sorted (List[Tuple[str, Any]]): Sorted representation of function inputs
        function_input_signature_pure (str): Hash of the function inputs and tag
        function_input_signature_benchmark_context (str): Comprehensive hash including benchmark context
        found_in_cache (bool): Whether this job result was found in cache
        msgs (List[str]): Messages related to this job's execution
    """

    function_input_vars: List[Any]
    index_tuple: Tuple[int, ...]
    dims_name: List[str]
    constant_inputs: dict
    bench_cfg_sample_hash: str
    tag: str

    function_input: dict = None
    canonical_input: Tuple[Any] = None
    fn_inputs_sorted: List[Tuple[str, Any]] = None
    function_input_signature_pure: str = None
    function_input_signature_benchmark_context: str = None
    found_in_cache: bool = False
    msgs: List[str] = field(default_factory=list)

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

        self.function_input_signature_benchmark_context = hash_sha1(
            (self.function_input_signature_pure, self.bench_cfg_sample_hash)
        )
