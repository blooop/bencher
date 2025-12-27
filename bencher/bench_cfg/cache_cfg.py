"""Configuration for benchmark caching behavior."""

from __future__ import annotations

import param


class CacheCfg(param.Parameterized):
    """Caching behavior for benchmark results (benchmark-level and sample-level)."""

    cache_results: bool = param.Boolean(
        False,
        doc="This is a benchmark level cache that stores the results of a fully completed "
        "benchmark. At the end of a benchmark the values are added to the cache but are not "
        "if the benchmark does not complete. If you want to cache values during the benchmark "
        "you need to use the cache_samples option. Beware that depending on how you change "
        "code in the objective function, the cache could provide values that are not correct.",
    )

    clear_cache: bool = param.Boolean(False, doc="Clear the cache of saved input->output mappings.")

    cache_samples: bool = param.Boolean(
        False,
        doc="If true, every time the benchmark function is called, bencher will check if that "
        "value has been calculated before and if so load the from the cache. Note that the "
        "sample level cache is different from the benchmark level cache which only caches the "
        "aggregate of all the results at the end of the benchmark. This cache lets you stop a "
        "benchmark halfway through and continue. However, beware that depending on how you "
        "change code in the objective function, the cache could provide values that are not "
        "correct.",
    )

    only_hash_tag: bool = param.Boolean(
        False,
        doc="By default when checking if a sample has been calculated before it includes the "
        "hash of the greater benchmarking context. This is safer because it means that data "
        "generated from one benchmark will not affect data from another benchmark. However, "
        "if you are careful it can be more flexible to ignore which benchmark generated the "
        "data and only use the tag hash to check if that data has been calculated before. "
        "ie, you can create two benchmarks that sample a subset of the problem during "
        "exploration and give them the same tag, and then afterwards create a larger benchmark "
        "that covers the cases you already explored. If this value is true, the combined "
        "benchmark will use any data from other benchmarks with the same tag.",
    )

    clear_sample_cache: bool = param.Boolean(
        False,
        doc="Clears the per-sample cache. Use this if you get unexpected behavior. The "
        "per_sample cache is tagged by the specific benchmark it was sampled from. So "
        "clearing the cache of one benchmark will not clear the cache of other benchmarks.",
    )

    overwrite_sample_cache: bool = param.Boolean(
        False,
        doc="If True, recalculate the value and overwrite the value stored in the sample cache",
    )

    only_plot: bool = param.Boolean(
        False, doc="Do not attempt to calculate benchmarks if no results are found in the cache"
    )
