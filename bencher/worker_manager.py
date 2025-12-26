"""Worker management for benchmarking.

This module provides the WorkerManager class for handling worker function
configuration and validation in benchmark runs.
"""

import logging
from functools import partial
from typing import Callable, List, Optional

from bencher.variables.parametrised_sweep import ParametrizedSweep

# Customize the formatter
logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")


def kwargs_to_input_cfg(worker_input_cfg: ParametrizedSweep, **kwargs) -> ParametrizedSweep:
    """Create a configured instance of a ParametrizedSweep with the provided keyword arguments.

    Args:
        worker_input_cfg (ParametrizedSweep): The ParametrizedSweep class to instantiate
        **kwargs: Keyword arguments to update the configuration with

    Returns:
        ParametrizedSweep: A configured instance of the worker_input_cfg class
    """
    input_cfg = worker_input_cfg()
    input_cfg.param.update(kwargs)
    return input_cfg


def worker_cfg_wrapper(worker: Callable, worker_input_cfg: ParametrizedSweep, **kwargs) -> dict:
    """Wrap a worker function to accept keyword arguments instead of a config object.

    This wrapper creates an instance of the worker_input_cfg class, updates it with the
    provided keyword arguments, and passes it to the worker function.

    Args:
        worker (Callable): The worker function that expects a config object
        worker_input_cfg (ParametrizedSweep): The class defining the configuration
        **kwargs: Keyword arguments to update the configuration with

    Returns:
        dict: The result of calling the worker function with the configured input
    """
    input_cfg = kwargs_to_input_cfg(worker_input_cfg, **kwargs)
    return worker(input_cfg)


class WorkerManager:
    """Manages worker function configuration and validation for benchmarks.

    This class handles the setup and management of worker functions used in benchmarking,
    including support for both callable functions and ParametrizedSweep instances.

    Attributes:
        worker (Callable): The configured worker function
        worker_class_instance (ParametrizedSweep): The worker class instance if provided
        worker_input_cfg (ParametrizedSweep): The input configuration class
    """

    def __init__(self) -> None:
        """Initialize a new WorkerManager."""
        self.worker: Optional[Callable] = None
        self.worker_class_instance: Optional[ParametrizedSweep] = None
        self.worker_input_cfg: Optional[ParametrizedSweep] = None

    def set_worker(
        self, worker: Callable | ParametrizedSweep, worker_input_cfg: ParametrizedSweep = None
    ) -> None:
        """Set the benchmark worker function and its input configuration.

        This method sets up the worker function to be benchmarked. The worker can be either a
        callable function that takes a ParametrizedSweep instance or a ParametrizedSweep
        instance with a __call__ method. In the latter case, worker_input_cfg is not needed.

        Args:
            worker (Callable | ParametrizedSweep): Either a function that will be benchmarked or a
                ParametrizedSweep instance with a __call__ method. When a ParametrizedSweep is
                provided, its __call__ method becomes the worker function.
            worker_input_cfg (ParametrizedSweep, optional): The class defining the input parameters
                for the worker function. Only needed if worker is a function rather than a
                ParametrizedSweep instance. Defaults to None.

        Raises:
            RuntimeError: If worker is a class type instead of an instance.
        """
        if isinstance(worker, ParametrizedSweep):
            self.worker_class_instance = worker
            self.worker = self.worker_class_instance.__call__
            logging.info("setting worker from bench class.__call__")
        else:
            if isinstance(worker, type):
                raise RuntimeError("This should be a class instance, not a class")
            if worker_input_cfg is None:
                self.worker = worker
            else:
                self.worker = partial(worker_cfg_wrapper, worker, worker_input_cfg)
            logging.info(f"setting worker {worker}")
        self.worker_input_cfg = worker_input_cfg

    def get_result_vars(self, as_str: bool = True) -> List[str | ParametrizedSweep]:
        """Retrieve the result variables from the worker class instance.

        Args:
            as_str (bool): If True, the result variables are returned as strings.
                           If False, they are returned in their original form.
                           Default is True.

        Returns:
            List[str | ParametrizedSweep]: A list of result variables, either as strings
                or in their original form.

        Raises:
            RuntimeError: If the worker class instance is not set.
        """
        if self.worker_class_instance is not None:
            if as_str:
                return [i.name for i in self.worker_class_instance.get_results_only()]
            return self.worker_class_instance.get_results_only()
        raise RuntimeError("Worker class instance not set")

    def get_inputs_only(self) -> List[ParametrizedSweep]:
        """Retrieve the input variables from the worker class instance.

        Returns:
            List[ParametrizedSweep]: A list of input variables.

        Raises:
            RuntimeError: If the worker class instance is not set.
        """
        if self.worker_class_instance is not None:
            return self.worker_class_instance.get_inputs_only()
        raise RuntimeError("Worker class instance not set")

    def get_input_defaults(self) -> List:
        """Retrieve the default input values from the worker class instance.

        Returns:
            List: A list of default input values as (parameter, value) tuples.

        Raises:
            RuntimeError: If the worker class instance is not set.
        """
        if self.worker_class_instance is not None:
            return self.worker_class_instance.get_input_defaults()
        raise RuntimeError("Worker class instance not set")
