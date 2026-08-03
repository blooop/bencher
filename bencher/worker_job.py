from __future__ import annotations

from dataclasses import dataclass
from functools import cached_property
from typing import Any

from bencher.utils import hmap_canonical_input

from .utils import hash_sha1


@dataclass
class WorkerJob:
    """Represents a benchmark worker job with input variables and caching information.

    This class encapsulates the information needed to execute a benchmark function,
    including input variables, dimension information, and caching metadata. It handles
    the preparation of function inputs and calculation of hash signatures for caching.

    The derived inputs and hash signatures are ``cached_property``s computed from the
    constructor fields, so a ``WorkerJob`` with *unset* hashes is unrepresentable
    (plan 23 P5, C8). They used to be four ``None``-default fields filled by a
    ``setup_hashes()`` method every constructor site had to remember to call --
    two-phase init, with nothing preventing caching under a ``None`` job key.

    Picklability is preserved and pinned by ``test/test_multiprocessing_executor.py``,
    though **not** because a ``WorkerJob`` crosses a process boundary -- it does not.
    Only ``Job`` (function + ``job_args``) is sent to an executor
    (``bencher.py``'s submit loop); a ``WorkerJob`` is built and consumed entirely in
    the parent process. It survives a round trip anyway: already-computed properties
    travel in ``__dict__``, and ones not yet accessed recompute on demand,
    deterministically, because ``hash_sha1`` is content-based.

    Attributes:
        function_input_vars (list): The values of the input variables to pass to the function
        index_tuple (tuple[int]): The indices of these values in the N-dimensional result array
        dims_name (list[str]): The names of the input dimensions
        constant_inputs (dict | None): Dictionary of any constant input values
        bench_cfg_sample_hash (str): Hash of the benchmark configuration without repeats
        tag (str): Tag for grouping related jobs
    """

    function_input_vars: list[Any]
    index_tuple: tuple[int, ...]
    dims_name: list[str]
    constant_inputs: dict | None
    bench_cfg_sample_hash: str
    tag: str

    @cached_property
    def canonical_input(self) -> tuple[Any, ...]:
        """Canonical representation of the swept inputs, used as a holomap key.

        Computed from the swept dimensions only -- constant inputs are deliberately
        excluded (they are merged into :attr:`function_input`, not here).
        """
        return hmap_canonical_input(dict(zip(self.dims_name, self.function_input_vars)))

    @cached_property
    def function_input(self) -> dict:
        """Complete input as a dictionary with dimension names as keys."""
        function_input = dict(zip(self.dims_name, self.function_input_vars))
        if self.constant_inputs is not None:
            function_input = function_input | self.constant_inputs
        return function_input

    @cached_property
    def fn_inputs_sorted(self) -> list[tuple[str, Any]]:
        """Sorted representation of the function inputs."""
        return sorted(self.function_input.items())

    @cached_property
    def function_input_signature_pure(self) -> str:
        """Hash of the function inputs and tag.

        The signature is the hash of the inputs to the function + meta variables
        such as repeat and time. The hash of the benchmark sweep as a whole
        (without the repeats hash) is kept separately in
        :attr:`bench_cfg_sample_hash` and deliberately not folded in here.
        """
        return hash_sha1((self.fn_inputs_sorted, self.tag))
