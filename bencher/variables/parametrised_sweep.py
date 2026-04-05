from __future__ import annotations

import warnings
from functools import partial
from typing import Any
from param import Parameter, Parameterized
import holoviews as hv
import panel as pn
from copy import deepcopy

from collections import namedtuple

from bencher.utils import hash_sha1
from bencher.variables.results import ALL_RESULT_TYPES, ResultHmap
from bencher.factories import create_bench, create_bench_runner

_InputResult = namedtuple("inputresult", ["inputs", "results"])
_input_result_cache: dict[tuple, _InputResult] = {}


class ParametrizedSweep(Parameterized):
    """Parent class for all Sweep types that need a custom hash"""

    @staticmethod
    def param_hash(param_type: Parameterized, hash_value: bool = True) -> int:
        """A custom hash function for parametrised types with options for hashing the value of the type and hashing metadata

        Args:
            param_type (Parameterized): A parameter
            hash_value (bool, optional): use the value as part of the hash. Defaults to True.
            # hash_meta (bool, optional): use metadata as part of the hash. Defaults to False.

        Returns:
            int: a hash
        """

        curhash = 0
        if hash_value:
            for k, v in param_type.param.values().items():
                if k != "name":
                    curhash = hash_sha1((curhash, hash_sha1(v)))

        # if hash_meta:
        #     for k, v in param_type.param.objects().items():
        #         if k != "name":
        #             print(f"key:{k}, hash:{hash_sha1(k)}")
        #             print(f"value:{v}, hash:{hash_sha1(v)}")
        #             curhash = hash_sha1((curhash, hash_sha1(k), hash_sha1(v)))
        return curhash

    def hash_persistent(self) -> str:
        """A hash function that avoids the PYTHONHASHSEED 'feature' which returns a different hash value each time the program is run"""
        return ParametrizedSweep.param_hash(self, True)

    def update_params_from_kwargs(self, **kwargs) -> None:
        """Given a dictionary of kwargs, set the parameters of the passed class 'self' to the values in the dictionary."""
        used_params = {}
        for key in self.param.objects().keys():
            if key in kwargs:
                if key != "name":
                    used_params[key] = kwargs[key]

        self.param.update(**used_params)

    @classmethod
    def get_input_and_results(cls, include_name: bool = False) -> tuple[dict, dict]:
        """Get dictionaries of input parameters and result parameters

        Args:
            cls: A parametrised class
            include_name (bool): Include the name parameter that all parametrised classes have. Default False

        Returns:
            tuple[dict, dict]: A tuple containing the inputs and result parameters as dictionaries
        """
        key = (cls, include_name)
        cached = _input_result_cache.get(key)
        if cached is not None:
            return _InputResult(inputs=dict(cached.inputs), results=dict(cached.results))

        inputs = {}
        results = {}
        for k, v in cls.param.objects().items():
            if isinstance(
                v,
                ALL_RESULT_TYPES,
            ):
                results[k] = v
            else:
                inputs[k] = v

        if not include_name:
            inputs.pop("name")
        result = _InputResult(inputs=inputs, results=results)
        _input_result_cache[key] = result
        return result

    def get_inputs_as_dict(self) -> dict:
        """Get the key:value pairs for all the input variables"""
        inp = self.get_input_and_results().inputs
        vals = self.param.values()
        return {i: vals[i] for i, v in inp.items()}

    def get_results_values_as_dict(self, holomap=None) -> dict:
        """Get a dictionary of result variables with the name and the current value"""
        values = self.param.values()
        output = {key: values[key] for key in self.get_input_and_results().results}
        if holomap is not None:
            output |= {"hmap": holomap}
        return output

    @classmethod
    def get_inputs_only(cls) -> list[Parameter]:
        """Return a list of input parameters

        Returns:
            list[param.Parameter]: A list of input parameters
        """
        return list(cls.get_input_and_results().inputs.values())

    @staticmethod
    def filter_fn(item, p_name):
        return item.name != p_name

    @classmethod
    def get_input_defaults(
        cls,
        override_defaults: list | None = None,
    ) -> list[tuple[Parameter, Any]]:
        inp = cls.get_inputs_only()
        if override_defaults is None:
            override_defaults = []
        assert isinstance(override_defaults, list)

        for p in override_defaults:
            inp = filter(partial(ParametrizedSweep.filter_fn, p_name=p[0].name), inp)

        return override_defaults + [[i, i.default] for i in inp]

    @classmethod
    def get_input_defaults_override(cls, **kwargs) -> dict[str, Any]:
        inp = cls.get_inputs_only()
        defaults = {}
        for i in inp:
            defaults[i.name] = deepcopy(i.default)

        for k, v in kwargs.items():
            defaults[k] = v

        return defaults

    @classmethod
    def get_results_only(cls) -> list[Parameter]:
        """Return a list of result parameters

        Returns:
            list[param.Parameter]: A list of result parameters
        """
        return list(cls.get_input_and_results().results.values())

    @classmethod
    def get_inputs_as_dims(
        self, compute_values=False, remove_dims: str | list[str] | None = None
    ) -> list[hv.Dimension]:
        inputs = self.get_inputs_only()

        if remove_dims is not None:
            if isinstance(remove_dims, str):
                remove_dims = [remove_dims]
            filtered_inputs = [i for i in inputs if i.name not in remove_dims]
            inputs = filtered_inputs

        return [iv.as_dim(compute_values) for iv in inputs]

    def to_dynamic_map(
        self,
        callback=None,
        name=None,
        remove_dims: str | list[str] | None = None,
        result_var: str | None = None,
    ) -> hv.DynamicMap:
        if callback is None:
            callback = self.__call__

        if result_var is None:
            result_vars = self.get_input_and_results().results
            for k, rv in result_vars.items():
                if isinstance(rv, ResultHmap):
                    result_var = k

        def callback_wrapper(**kwargs):
            return callback(**kwargs)[result_var]

        return hv.DynamicMap(
            callback=callback_wrapper,
            kdims=self.get_inputs_as_dims(compute_values=False, remove_dims=remove_dims),
            name=name,
        ).opts(shared_axes=False, framewise=True, width=1000, height=1000)

    def to_gui(self, result_var: str | None = None, **kwargs):  # pragma: no cover
        main = pn.Row(
            self.to_dynamic_map(result_var=result_var, **kwargs),
        )
        main.show()

    def to_holomap(self, callback, remove_dims: str | list[str] | None = None) -> hv.DynamicMap:
        return hv.HoloMap(
            hv.DynamicMap(
                callback=callback,
                kdims=self.get_inputs_as_dims(compute_values=True, remove_dims=remove_dims),
            )
        )

    def __call__(self, **kwargs) -> dict:
        """Dispatch to benchmark() if overridden, otherwise use legacy path.

        Returns:
            dict: a dictionary with all the result variables as named key value pairs.
        """
        if type(self).benchmark is not ParametrizedSweep.benchmark:
            # New-style: subclass overrides benchmark()
            self.update_params_from_kwargs(**kwargs)
            self.benchmark()
            return self.get_results_values_as_dict()
        # Legacy path: subclass overrides __call__() and handles
        # update_params_from_kwargs + super().__call__() itself.
        if type(self).__call__ is ParametrizedSweep.__call__:
            msg = (
                f"{type(self).__name__} does not override benchmark(). "
                "Results will contain only default values. "
                "Define a benchmark() method on your class."
            )
            warnings.warn(msg, UserWarning, stacklevel=2)
        return self.get_results_values_as_dict()

    def benchmark(self):
        """Override this with your benchmark logic.

        When called, all sweep parameters (self.x, etc.) are already set.
        Set result variables (self.result, etc.) directly on self.
        No need to call update_params_from_kwargs or super().__call__().
        """

    def plot_hmap(self, **kwargs):
        return self.__call__(**kwargs)["hmap"]

    def to_bench(self, run_cfg=None, report=None, name=None):
        """Create a Bench instance from this ParametrizedSweep."""
        return create_bench(self, run_cfg=run_cfg, report=report, name=name)

    def to_optimize(self, n_trials=100, run_cfg=None, **kwargs):
        """Create a Bench and run optimization in one call.

        Args:
            n_trials: Number of optuna trials.
            run_cfg: Optional BenchRunCfg.
            **kwargs: Forwarded to ``Bench.optimize()``.

        Returns:
            OptimizeResult wrapping the completed study.
        """
        bench = self.to_bench(run_cfg=run_cfg)
        return bench.optimize(n_trials=n_trials, run_cfg=run_cfg, **kwargs)

    def to_bench_runner(self, run_cfg=None, name=None):
        """Create a BenchRunner instance from this ParametrizedSweep.

        Enables fluent chaining like:
            MyConfig().to_bench_runner().add(func).run(level=2, max_level=4)
        """
        return create_bench_runner(self, run_cfg=run_cfg, name=name)
