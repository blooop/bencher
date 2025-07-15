from diskcache import Cache

from bencher.variables.parametrised_sweep import ParametrizedSweep
from bencher.utils import hash_sha1
import logging


class CachedParams(ParametrizedSweep):
    def __init__(self, clear_cache=True, cache_name="fcache", **params):
        super().__init__(**params)

        self.cache = Cache(f"cachedir/{cache_name}/sample_cache")
        logging.info(f"cache dir{self.cache.directory}")
        print(f"cache dir{self.cache.directory}")

        if clear_cache:
            self.cache.clear()

    def kwargs_to_hash_key(self, **kwargs):
        return tuple(sorted(kwargs.items(), key=lambda item: str(item[0])))

    def in_cache(self, **kwargs):
        self.update_params_from_kwargs(**kwargs)
        # print(self.get_inputs_as_dict())
        inputs_key = self.kwargs_to_hash_key(**self.get_inputs_as_dict())
        key = hash_sha1(inputs_key)
        print(f"key:{key},value: {inputs_key}")
        value = None
        if key in self.cache:
            value = self.cache[key]
        return key, value

    def cache_wrap(self, func, **kwargs):
        key, value = self.in_cache(**kwargs)
        if value is None:
            value = func(**kwargs)
            self.cache[key] = value
        return value

    # def cache_mem(self, function):
    #     def cache_wrap1(self, func, **kwargs):
    #         key, value = self.in_cache(**kwargs)
    #         if value is None:
    #             value = function(**kwargs)
    #             self.cache[key] = value
    #         return value

    #     return cache_wrap1
