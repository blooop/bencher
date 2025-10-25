from functools import partial
from typing import List, Tuple, Any
from param import Parameter, Parameterized
import holoviews as hv
import panel as pn
from copy import deepcopy

from bencher.utils import make_namedtuple, hash_sha1
from bencher.variables.results import ALL_RESULT_TYPES, ResultHmap


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
    def get_input_and_results(cls, include_name: bool = False) -> Tuple[dict, dict]:
        """Get dictionaries of input parameters and result parameters

        Args:
            cls: A parametrised class
            include_name (bool): Include the name parameter that all parametrised classes have. Default False

        Returns:
            Tuple[dict, dict]: a tuple containing the inputs and result parameters as dictionaries
        """
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
        return make_namedtuple("inputresult", inputs=inputs, results=results)

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
    def get_inputs_only(cls) -> List[Parameter]:
        """Return a list of input parameters

        Returns:
            List[param.Parameter]: A list of input parameters
        """
        return list(cls.get_input_and_results().inputs.values())

    @staticmethod
    def filter_fn(item, p_name):
        return item.name != p_name

    @classmethod
    def get_input_defaults(
        cls,
        override_defaults: List = None,
    ) -> List[Tuple[Parameter, Any]]:
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
    def get_results_only(cls) -> List[Parameter]:
        """Return a list of result parameters

        Returns:
            List[param.Parameter]: A list of result parameters
        """
        return list(cls.get_input_and_results().results.values())

    @classmethod
    def get_inputs_as_dims(
        self, compute_values=False, remove_dims: str | List[str] = None
    ) -> List[hv.Dimension]:
        inputs = self.get_inputs_only()

        if remove_dims is not None:
            if isinstance(remove_dims, str):
                remove_dims = [remove_dims]
            filtered_inputs = [i for i in inputs if i.name not in remove_dims]
            inputs = filtered_inputs

        return [iv.as_dim(compute_values) for iv in inputs]

    def to_dynamic_map(
        self, callback=None, name=None, remove_dims: str | List[str] = None, result_var: str = None
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

    def to_gui(self, result_var: str = None, **kwargs):  # pragma: no cover
        main = pn.Row(
            self.to_dynamic_map(result_var=result_var, **kwargs),
        )
        main.show()

    def to_holomap(self, callback, remove_dims: str | List[str] = None) -> hv.DynamicMap:
        return hv.HoloMap(
            hv.DynamicMap(
                callback=callback,
                kdims=self.get_inputs_as_dims(compute_values=True, remove_dims=remove_dims),
            )
        )

    def __call__(self, **kwargs) -> dict:
        """This is the function that is called to record data samples in the benchmarking function.  It should be overridden with your custom logic and then call the parent method  "return super().__call__(**kwargs)"

        Returns:
            dict: a dictionary with all the result variables in the ParametrisedSweep class as named key value pairs.
        """
        return self.get_results_values_as_dict()

    def plot_hmap(self, **kwargs):
        return self.__call__(**kwargs)["hmap"]

    # TODO Add type hints here and fix the circular imports
    def to_bench(self, run_cfg=None, report=None, name: str = None):
        from bencher import Bench

        assert isinstance(self, ParametrizedSweep)

        if name is None:
            name = self.name[:-5]  # param adds 5 digit number to the end, so remove it

        return Bench(name, self, run_cfg=run_cfg, report=report)

    def to_bench_runner(self, run_cfg=None, name: str = None):
        # Create a BenchRunner instance from this ParametrizedSweep.
        # Enables fluent chaining like:
        # MyConfig().to_bench_runner().add_run(func).run(level=2, max_level=4)
        from bencher.bench_runner import BenchRunner

        if run_cfg is None:
            from bencher.bench_cfg import BenchRunCfg  # pylint: disable=import-outside-toplevel,reimported,redefined-outer-name

            run_cfg = BenchRunCfg()

        if name is None:
            # Create BenchRunner with auto-generated name
            return BenchRunner(self, run_cfg=run_cfg)
        # Create BenchRunner with specified name
        return BenchRunner(name, self, run_cfg=run_cfg)
