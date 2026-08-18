from __future__ import annotations

import param


class CacheCfg(param.Parameterized):
    """Configuration for caching behaviour at both benchmark and sample level.

    See ``docs/caching.md`` for how these parameters interact, and which of
    them have real readers (``only_hash_tag`` does not).
    """

    results: bool = param.Boolean(
        False,
        doc="This is a benchmark level cache that stores the results of a fully completed benchmark. At the end of a benchmark the values are added to the cache but are not if the benchmark does not complete.  If you want to cache values during the benchmark you need to use the cache.samples option. Beware that depending on how you change code in the objective function, the cache could provide values that are not correct.",
    )

    samples: bool = param.Boolean(
        False,
        doc="If true, every time the benchmark function is called, bencher will check if that value has been calculated before and if so load the from the cache.  Note that the sample level cache is different from the benchmark level cache which only caches the aggregate of all the results at the end of the benchmark. This cache lets you stop a benchmark halfway through and continue. However, beware that depending on how you change code in the objective function, the cache could provide values that are not correct.",
    )

    clear: bool = param.Boolean(False, doc=" Clear the cache of saved input->output mappings.")

    clear_samples: bool = param.Boolean(
        False,
        doc="Clears the per-sample cache.  Use this if you get unexpected behavior.  The per_sample cache is tagged by the specific benchmark it was sampled from. So clearing the cache of one benchmark will not clear the cache of other benchmarks.",
    )

    overwrite_samples: bool = param.Boolean(
        False,
        doc="If True, recalculate the value and overwrite the value stored in the sample cache",
    )

    only_hash_tag: bool = param.Boolean(
        False,
        doc="DEAD FLAG -- nothing reads this, and setting it changes nothing. The "
        "per-sample cache key is unconditionally hash_sha1((sorted function inputs, "
        "tag)) (see WorkerJob.function_input_signature_pure), so tag-only matching is "
        "always on and cannot be turned off. Benchmarks sharing a tag therefore share "
        "cached samples; use distinct run_tag values to isolate them. This flag "
        "previously documented an opt-in to that behaviour, implying a safer "
        "context-hashing default that does not exist -- see docs/caching.md. Tracked "
        "as W6 in plans/architecture/A4-caching-architecture.md and scheduled for "
        "removal in A5 phase 0.",
    )

    size_mb: int = param.Integer(
        default=None,
        allow_None=True,
        bounds=(1, None),
        doc="Maximum size of the disk cache in megabytes (MB). If None, uses the default (100 GB).",
    )
