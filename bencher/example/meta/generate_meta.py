from typing import Any

import bencher as bn
from bencher.example.meta.meta_generator_base import MetaGeneratorBase


# Registry of inline class templates keyed by (float_count, cat_count).
# Each entry defines a unique software/data-processing domain class.
INLINE_CLASSES = {
    (0, 0): {
        "class_name": "BaselineCheck",
        "class_doc": "Measures a fixed baseline metric with no swept parameters.",
        "imports": "import bencher as bn",
        "params": {},
        "result_vars": {
            "baseline": 'bn.ResultVar(units="ms", doc="Baseline latency")',
        },
        "call_body": ["self.baseline = 42.0"],
        "noise_body": [
            "self.baseline = 42.0",
            "self.baseline += random.gauss(0, {noise} * 5)",
        ],
    },
    (0, 1): {
        "class_name": "CacheBackend",
        "class_doc": "Compares latency across different cache backends.",
        "imports": "import bencher as bn",
        "params": {
            "backend": 'bn.StringSweep(["redis", "memcached", "local"], doc="Cache backend")',
        },
        "result_vars": {
            "latency": 'bn.ResultVar(units="ms", doc="Cache lookup latency")',
        },
        "call_body": [
            'base = {{"redis": 1.2, "memcached": 1.5, "local": 0.3}}[self.backend]',
            "self.latency = base",
        ],
        "noise_body": [
            'base = {{"redis": 1.2, "memcached": 1.5, "local": 0.3}}[self.backend]',
            "self.latency = base + random.gauss(0, {noise} * base)",
        ],
    },
    (0, 2): {
        "class_name": "NetworkConfig",
        "class_doc": "Measures throughput across protocol and region combinations.",
        "imports": "import bencher as bn",
        "params": {
            "protocol": 'bn.StringSweep(["http", "grpc"], doc="Network protocol")',
            "region": 'bn.StringSweep(["us-east", "eu-west", "ap-south"], doc="Deployment region")',
        },
        "result_vars": {
            "throughput": 'bn.ResultVar(units="req/s", doc="Request throughput")',
        },
        "call_body": [
            'proto_factor = {{"http": 1.0, "grpc": 1.8}}[self.protocol]',
            'region_base = {{"us-east": 500, "eu-west": 420, "ap-south": 350}}[self.region]',
            "self.throughput = region_base * proto_factor",
        ],
        "noise_body": [
            'proto_factor = {{"http": 1.0, "grpc": 1.8}}[self.protocol]',
            'region_base = {{"us-east": 500, "eu-west": 420, "ap-south": 350}}[self.region]',
            "self.throughput = region_base * proto_factor + random.gauss(0, {noise} * 50)",
        ],
    },
    (0, 3): {
        "class_name": "DeploymentConfig",
        "class_doc": "Full config matrix: protocol, region, and log level.",
        "imports": "import bencher as bn",
        "params": {
            "protocol": 'bn.StringSweep(["http", "grpc"], doc="Network protocol")',
            "region": 'bn.StringSweep(["us-east", "eu-west", "ap-south"], doc="Deployment region")',
            "log_level": 'bn.StringSweep(["debug", "info", "warn"], doc="Logging level")',
        },
        "result_vars": {
            "throughput": 'bn.ResultVar(units="req/s", doc="Request throughput")',
        },
        "call_body": [
            'proto_factor = {{"http": 1.0, "grpc": 1.8}}[self.protocol]',
            'region_base = {{"us-east": 500, "eu-west": 420, "ap-south": 350}}[self.region]',
            'log_penalty = {{"debug": 0.7, "info": 1.0, "warn": 1.0}}[self.log_level]',
            "self.throughput = region_base * proto_factor * log_penalty",
        ],
        "noise_body": [
            'proto_factor = {{"http": 1.0, "grpc": 1.8}}[self.protocol]',
            'region_base = {{"us-east": 500, "eu-west": 420, "ap-south": 350}}[self.region]',
            'log_penalty = {{"debug": 0.7, "info": 1.0, "warn": 1.0}}[self.log_level]',
            "self.throughput = region_base * proto_factor * log_penalty + random.gauss(0, {noise} * 50)",
        ],
    },
    (1, 0): {
        "class_name": "SortBenchmark",
        "class_doc": "Measures sort duration across array sizes.",
        "imports": "import math\nimport bencher as bn",
        "params": {
            "array_size": 'bn.FloatSweep(default=100, bounds=[10, 10000], doc="Array length")',
        },
        "result_vars": {
            "time": 'bn.ResultVar(units="ms", doc="Sort duration")',
        },
        "call_body": [
            "self.time = self.array_size * math.log2(self.array_size + 1) * 0.001",
        ],
        "noise_body": [
            "self.time = self.array_size * math.log2(self.array_size + 1) * 0.001",
            "self.time += random.gauss(0, {noise} * self.time)",
        ],
    },
    (1, 1): {
        "class_name": "SortComparison",
        "class_doc": "Compares sort duration across array sizes and algorithms.",
        "imports": "import math\nimport bencher as bn",
        "params": {
            "array_size": 'bn.FloatSweep(default=100, bounds=[10, 10000], doc="Array length")',
            "algorithm": 'bn.StringSweep(["quicksort", "mergesort", "heapsort"], doc="Sort algorithm")',
        },
        "result_vars": {
            "time": 'bn.ResultVar(units="ms", doc="Sort duration")',
        },
        "call_body": [
            'algo_factor = {{"quicksort": 1.0, "mergesort": 1.2, "heapsort": 1.5}}[self.algorithm]',
            "self.time = algo_factor * self.array_size * math.log2(self.array_size + 1) * 0.001",
        ],
        "noise_body": [
            'algo_factor = {{"quicksort": 1.0, "mergesort": 1.2, "heapsort": 1.5}}[self.algorithm]',
            "self.time = algo_factor * self.array_size * math.log2(self.array_size + 1) * 0.001",
            "self.time += random.gauss(0, {noise} * self.time)",
        ],
    },
    (1, 2): {
        "class_name": "SortAnalysis",
        "class_doc": "Sort analysis across size, algorithm, and data distribution.",
        "imports": "import math\nimport bencher as bn",
        "params": {
            "array_size": 'bn.FloatSweep(default=100, bounds=[10, 10000], doc="Array length")',
            "algorithm": 'bn.StringSweep(["quicksort", "mergesort", "heapsort"], doc="Sort algorithm")',
            "distribution": 'bn.StringSweep(["uniform", "sorted", "reversed"], doc="Data distribution")',
        },
        "result_vars": {
            "time": 'bn.ResultVar(units="ms", doc="Sort duration")',
        },
        "call_body": [
            'algo_factor = {{"quicksort": 1.0, "mergesort": 1.2, "heapsort": 1.5}}[self.algorithm]',
            'dist_factor = {{"uniform": 1.0, "sorted": 0.6, "reversed": 1.8}}[self.distribution]',
            "self.time = algo_factor * dist_factor * self.array_size * math.log2(self.array_size + 1) * 0.001",
        ],
        "noise_body": [
            'algo_factor = {{"quicksort": 1.0, "mergesort": 1.2, "heapsort": 1.5}}[self.algorithm]',
            'dist_factor = {{"uniform": 1.0, "sorted": 0.6, "reversed": 1.8}}[self.distribution]',
            "self.time = algo_factor * dist_factor * self.array_size * math.log2(self.array_size + 1) * 0.001",
            "self.time += random.gauss(0, {noise} * self.time)",
        ],
    },
    (1, 3): {
        "class_name": "SortFullMatrix",
        "class_doc": "Full sort matrix: size, algorithm, distribution, and order.",
        "imports": "import math\nimport bencher as bn",
        "params": {
            "array_size": 'bn.FloatSweep(default=100, bounds=[10, 10000], doc="Array length")',
            "algorithm": 'bn.StringSweep(["quicksort", "mergesort", "heapsort"], doc="Sort algorithm")',
            "distribution": 'bn.StringSweep(["uniform", "sorted", "reversed"], doc="Data distribution")',
            "stability": 'bn.StringSweep(["stable", "unstable"], doc="Sort stability")',
        },
        "result_vars": {
            "time": 'bn.ResultVar(units="ms", doc="Sort duration")',
        },
        "call_body": [
            'algo_factor = {{"quicksort": 1.0, "mergesort": 1.2, "heapsort": 1.5}}[self.algorithm]',
            'dist_factor = {{"uniform": 1.0, "sorted": 0.6, "reversed": 1.8}}[self.distribution]',
            'stab_factor = {{"stable": 1.1, "unstable": 1.0}}[self.stability]',
            "self.time = algo_factor * dist_factor * stab_factor * self.array_size * math.log2(self.array_size + 1) * 0.001",
        ],
        "noise_body": [
            'algo_factor = {{"quicksort": 1.0, "mergesort": 1.2, "heapsort": 1.5}}[self.algorithm]',
            'dist_factor = {{"uniform": 1.0, "sorted": 0.6, "reversed": 1.8}}[self.distribution]',
            'stab_factor = {{"stable": 1.1, "unstable": 1.0}}[self.stability]',
            "self.time = algo_factor * dist_factor * stab_factor * self.array_size * math.log2(self.array_size + 1) * 0.001",
            "self.time += random.gauss(0, {noise} * self.time)",
        ],
    },
    (2, 0): {
        "class_name": "CompressionBench",
        "class_doc": "Measures compression ratio across block size and input entropy.",
        "imports": "import math\nimport bencher as bn",
        "params": {
            "block_size": 'bn.FloatSweep(default=4096, bounds=[512, 65536], doc="Block size in bytes")',
            "entropy": 'bn.FloatSweep(default=0.5, bounds=[0.0, 1.0], doc="Input data entropy")',
        },
        "result_vars": {
            "ratio": 'bn.ResultVar(units="x", doc="Compression ratio")',
        },
        "call_body": [
            "self.ratio = (1.0 - 0.7 * self.entropy) * (1.0 + 0.3 * math.log2(self.block_size / 512))",
        ],
        "noise_body": [
            "self.ratio = (1.0 - 0.7 * self.entropy) * (1.0 + 0.3 * math.log2(self.block_size / 512))",
            "self.ratio += random.gauss(0, {noise} * 0.3)",
        ],
    },
    (2, 1): {
        "class_name": "CompressionCodec",
        "class_doc": "Compression ratio across block size, entropy, and codec.",
        "imports": "import math\nimport bencher as bn",
        "params": {
            "block_size": 'bn.FloatSweep(default=4096, bounds=[512, 65536], doc="Block size in bytes")',
            "entropy": 'bn.FloatSweep(default=0.5, bounds=[0.0, 1.0], doc="Input data entropy")',
            "codec": 'bn.StringSweep(["zlib", "lz4", "zstd"], doc="Compression codec")',
        },
        "result_vars": {
            "ratio": 'bn.ResultVar(units="x", doc="Compression ratio")',
        },
        "call_body": [
            'codec_eff = {{"zlib": 1.0, "lz4": 0.7, "zstd": 1.1}}[self.codec]',
            "self.ratio = codec_eff * (1.0 - 0.7 * self.entropy) * (1.0 + 0.3 * math.log2(self.block_size / 512))",
        ],
        "noise_body": [
            'codec_eff = {{"zlib": 1.0, "lz4": 0.7, "zstd": 1.1}}[self.codec]',
            "self.ratio = codec_eff * (1.0 - 0.7 * self.entropy) * (1.0 + 0.3 * math.log2(self.block_size / 512))",
            "self.ratio += random.gauss(0, {noise} * 0.3)",
        ],
    },
    (2, 2): {
        "class_name": "CompressionSuite",
        "class_doc": "Compression suite: block size, entropy, codec, and level.",
        "imports": "import math\nimport bencher as bn",
        "params": {
            "block_size": 'bn.FloatSweep(default=4096, bounds=[512, 65536], doc="Block size in bytes")',
            "entropy": 'bn.FloatSweep(default=0.5, bounds=[0.0, 1.0], doc="Input data entropy")',
            "codec": 'bn.StringSweep(["zlib", "lz4", "zstd"], doc="Compression codec")',
            "effort": 'bn.StringSweep(["fast", "balanced", "max"], doc="Compression effort")',
        },
        "result_vars": {
            "ratio": 'bn.ResultVar(units="x", doc="Compression ratio")',
        },
        "call_body": [
            'codec_eff = {{"zlib": 1.0, "lz4": 0.7, "zstd": 1.1}}[self.codec]',
            'effort_mult = {{"fast": 0.8, "balanced": 1.0, "max": 1.15}}[self.effort]',
            "self.ratio = codec_eff * effort_mult * (1.0 - 0.7 * self.entropy) * (1.0 + 0.3 * math.log2(self.block_size / 512))",
        ],
        "noise_body": [
            'codec_eff = {{"zlib": 1.0, "lz4": 0.7, "zstd": 1.1}}[self.codec]',
            'effort_mult = {{"fast": 0.8, "balanced": 1.0, "max": 1.15}}[self.effort]',
            "self.ratio = codec_eff * effort_mult * (1.0 - 0.7 * self.entropy) * (1.0 + 0.3 * math.log2(self.block_size / 512))",
            "self.ratio += random.gauss(0, {noise} * 0.3)",
        ],
    },
    (3, 0): {
        "class_name": "HashBenchmark",
        "class_doc": "Hash throughput across key size, payload size, and iterations.",
        "imports": "import math\nimport bencher as bn",
        "params": {
            "key_size": 'bn.FloatSweep(default=32, bounds=[8, 256], doc="Key size in bytes")',
            "payload_size": 'bn.FloatSweep(default=1024, bounds=[64, 65536], doc="Payload size in bytes")',
            "iterations": 'bn.FloatSweep(default=100, bounds=[10, 1000], doc="Hash iterations")',
        },
        "result_vars": {
            "throughput": 'bn.ResultVar(units="MB/s", doc="Hash throughput")',
        },
        "call_body": [
            "self.throughput = 500.0 / (1.0 + 0.5 * math.log2(self.key_size / 8)) / (1.0 + 0.3 * math.log2(self.payload_size / 64)) * (self.iterations / 100)",
        ],
        "noise_body": [
            "self.throughput = 500.0 / (1.0 + 0.5 * math.log2(self.key_size / 8)) / (1.0 + 0.3 * math.log2(self.payload_size / 64)) * (self.iterations / 100)",
            "self.throughput += random.gauss(0, {noise} * 30)",
        ],
    },
    (3, 1): {
        "class_name": "HashComparison",
        "class_doc": "Hash throughput across key size, payload, iterations, and algorithm.",
        "imports": "import math\nimport bencher as bn",
        "params": {
            "key_size": 'bn.FloatSweep(default=32, bounds=[8, 256], doc="Key size in bytes")',
            "payload_size": 'bn.FloatSweep(default=1024, bounds=[64, 65536], doc="Payload size in bytes")',
            "iterations": 'bn.FloatSweep(default=100, bounds=[10, 1000], doc="Hash iterations")',
            "algorithm": 'bn.StringSweep(["sha256", "blake2", "md5"], doc="Hash algorithm")',
        },
        "result_vars": {
            "throughput": 'bn.ResultVar(units="MB/s", doc="Hash throughput")',
        },
        "call_body": [
            'algo_speed = {{"sha256": 1.0, "blake2": 1.4, "md5": 1.8}}[self.algorithm]',
            "self.throughput = algo_speed * 500.0 / (1.0 + 0.5 * math.log2(self.key_size / 8)) / (1.0 + 0.3 * math.log2(self.payload_size / 64)) * (self.iterations / 100)",
        ],
        "noise_body": [
            'algo_speed = {{"sha256": 1.0, "blake2": 1.4, "md5": 1.8}}[self.algorithm]',
            "self.throughput = algo_speed * 500.0 / (1.0 + 0.5 * math.log2(self.key_size / 8)) / (1.0 + 0.3 * math.log2(self.payload_size / 64)) * (self.iterations / 100)",
            "self.throughput += random.gauss(0, {noise} * 30)",
        ],
    },
    (3, 2): {
        "class_name": "HashAnalysis",
        "class_doc": "Hash analysis: key size, payload, iterations, algorithm, and mode.",
        "imports": "import math\nimport bencher as bn",
        "params": {
            "key_size": 'bn.FloatSweep(default=32, bounds=[8, 256], doc="Key size in bytes")',
            "payload_size": 'bn.FloatSweep(default=1024, bounds=[64, 65536], doc="Payload size in bytes")',
            "iterations": 'bn.FloatSweep(default=100, bounds=[10, 1000], doc="Hash iterations")',
            "algorithm": 'bn.StringSweep(["sha256", "blake2", "md5"], doc="Hash algorithm")',
            "mode": 'bn.StringSweep(["stream", "block"], doc="Processing mode")',
        },
        "result_vars": {
            "throughput": 'bn.ResultVar(units="MB/s", doc="Hash throughput")',
        },
        "call_body": [
            'algo_speed = {{"sha256": 1.0, "blake2": 1.4, "md5": 1.8}}[self.algorithm]',
            'mode_factor = {{"stream": 1.0, "block": 0.85}}[self.mode]',
            "self.throughput = algo_speed * mode_factor * 500.0 / (1.0 + 0.5 * math.log2(self.key_size / 8)) / (1.0 + 0.3 * math.log2(self.payload_size / 64)) * (self.iterations / 100)",
        ],
        "noise_body": [
            'algo_speed = {{"sha256": 1.0, "blake2": 1.4, "md5": 1.8}}[self.algorithm]',
            'mode_factor = {{"stream": 1.0, "block": 0.85}}[self.mode]',
            "self.throughput = algo_speed * mode_factor * 500.0 / (1.0 + 0.5 * math.log2(self.key_size / 8)) / (1.0 + 0.3 * math.log2(self.payload_size / 64)) * (self.iterations / 100)",
            "self.throughput += random.gauss(0, {noise} * 30)",
        ],
    },
}


def _build_class_code(info, _float_count, _cat_count, noise_val=0.0, time_offset=False):
    """Build the inline class source code from an INLINE_CLASSES entry."""
    cls_lines = [f"class {info['class_name']}(bn.ParametrizedSweep):"]
    cls_lines.append(f'    """{info["class_doc"]}"""')
    cls_lines.append("")

    for pname, pdef in info["params"].items():
        cls_lines.append(f"    {pname} = {pdef}")

    if info["params"] and info["result_vars"]:
        cls_lines.append("")
    for rname, rdef in info["result_vars"].items():
        cls_lines.append(f"    {rname} = {rdef}")

    if time_offset:
        cls_lines.append("")
        cls_lines.append("    _time_offset = 0.0")

    cls_lines.append("")
    cls_lines.append("    def __call__(self, **kwargs: Any) -> Any:")
    cls_lines.append("        self.update_params_from_kwargs(**kwargs)")

    if noise_val > 0 and "noise_body" in info:
        for line in info["noise_body"]:
            cls_lines.append(f"        {line.format(noise=noise_val)}")
    else:
        for line in info["call_body"]:
            cls_lines.append(f"        {line.format(noise=0)}")

    if time_offset:
        result_name = list(info["result_vars"].keys())[0]
        cls_lines.append(f"        self.{result_name} += self._time_offset * 10")

    cls_lines.append("        return super().__call__()")
    return "\n".join(cls_lines)


def _get_input_var_names(info, float_count, cat_count):
    """Get input variable names for the given combination."""
    params = list(info["params"].keys())
    float_vars = [p for p in params if "FloatSweep" in info["params"][p]]
    cat_vars = [p for p in params if "FloatSweep" not in info["params"][p]]
    return float_vars[:float_count] + cat_vars[:cat_count]


def _get_sweep_description(float_count, cat_count, variant):
    """Return educational description and post_description for a sweep example.

    These descriptions preserve the pedagogical content from the original
    hand-written examples (example_floats.py, example_categorical.py, etc.)
    so that the auto-generated gallery remains a useful learning resource.
    """
    dim_label = f"{float_count} float + {cat_count} categorical"

    descs = {
        "no_repeats": (
            f"A {dim_label} parameter sweep with a single sample per combination. "
            "Bencher calculates the Cartesian product of all input variables and "
            "evaluates the benchmark function at each point. With no repeats, each "
            "combination appears exactly once -- useful for deterministic functions "
            "or quick exploration before committing to longer runs.",
            "Each tab shows a different view of the same data: interactive plots, "
            "tabular summaries, and raw data. Use the tabs to explore the sweep "
            "results from different angles.",
        ),
        "with_repeats": (
            f"A {dim_label} parameter sweep with multiple repeats per combination. "
            "Repeating measurements reveals the noise structure of your benchmark. "
            "If your function is deterministic, all repeats will be identical; if it "
            "has stochastic components, repeats let you estimate confidence intervals "
            "and distinguish signal from noise. The benchmark function must be pure -- "
            "if past calls affect future calls through side effects, the statistics "
            "will be invalid.",
            "Swarm/violin plots show the distribution of repeated measurements. "
            "If repeat has high variance, it suggests either measurement noise or "
            "unintended side effects in the benchmark function.",
        ),
        "over_time": (
            f"A {dim_label} parameter sweep tracked over time. Setting over_time=True "
            "records multiple time snapshots that can be scrubbed via a slider. Each "
            "call to plot_sweep with a new time_src appends a snapshot to the history. "
            "This is designed for nightly benchmarks or CI pipelines where you want to "
            "track how metrics evolve across commits, releases, or environmental changes. "
            "Use clear_history=True on the first snapshot to reset, and clear_cache=True "
            "to force re-evaluation.",
            "The time slider lets you scrub through snapshots. The 'All Time Points "
            "(aggregated)' tab pools all snapshots into one view, smoothing out "
            "per-snapshot noise to reveal long-term trends.",
        ),
        "over_time_repeats": (
            f"A {dim_label} parameter sweep with both repeats and over_time tracking. "
            "This combination is the most informative: repeats reveal per-measurement "
            "noise at each time point, while over_time captures long-term drift. If "
            "your nightly benchmark shows increasing variance, repeats help distinguish "
            "whether the algorithm became noisier or the environment became less stable.",
            "Compare the per-snapshot distributions (via the slider) with the aggregated "
            "view. Growing spread over time suggests a real change, not just noise.",
        ),
    }

    desc, post_desc = descs.get(variant, ("", ""))

    # Add dimensionality-specific guidance
    if float_count == 0 and cat_count == 0:
        desc += (
            " With no input variables, this is a 0D sweep that measures a single baseline metric."
        )
    elif float_count == 0:
        desc += " Categorical-only sweeps produce bar/swarm plots comparing discrete settings."
    elif float_count == 1 and cat_count == 0:
        desc += " A 1D float sweep produces a line plot -- the simplest way to characterise a continuous input."
    elif float_count == 1 and cat_count >= 1:
        desc += (
            " Adding categorical variables to a float sweep creates faceted line plots -- "
            "one curve per category, making it easy to compare how each setting "
            "modifies the continuous relationship."
        )
    elif float_count == 2:
        desc += (
            " A 2D float sweep produces a heatmap. Additional categorical variables "
            "create faceted heatmaps, one per category combination."
        )
    elif float_count == 3:
        desc += (
            " A 3D float sweep produces a volumetric representation. "
            "This is useful for visualising scalar fields in 3D parameter spaces."
        )

    return desc, post_desc


class BenchMetaGen(bn.ParametrizedSweep):
    """This class uses bencher to display the multidimensional types bencher can represent"""

    float_vars_count = bn.IntSweep(
        default=0, bounds=(0, 3), doc="The number of floating point variables that are swept"
    )
    categorical_vars_count = bn.IntSweep(
        default=0, bounds=(0, 3), doc="The number of categorical variables that are swept"
    )

    sample_with_repeats = bn.IntSweep(default=1, bounds=(1, 100))
    sample_over_time = bn.BoolSweep(default=False)
    level = bn.IntSweep(default=2, units="level", bounds=(2, 5))

    plots = bn.ResultReference(units="int")

    def __call__(self, **kwargs: Any) -> Any:
        self.update_params_from_kwargs(**kwargs)

        key = (self.float_vars_count, self.categorical_vars_count)
        if key not in INLINE_CLASSES:
            return super().__call__()

        info = INLINE_CLASSES[key]
        input_var_names = _get_input_var_names(
            info, self.float_vars_count, self.categorical_vars_count
        )

        if self.sample_over_time and self.sample_with_repeats > 1:
            variant = "over_time_repeats"
        elif self.sample_over_time:
            variant = "over_time"
        elif self.sample_with_repeats > 1:
            variant = "with_repeats"
        else:
            variant = "no_repeats"

        # Include all dimensions in filename so every generated file is globally unique
        base_title = f"{self.float_vars_count}_float_{self.categorical_vars_count}_cat"
        title = (
            f"{self.float_vars_count} Float, {self.categorical_vars_count} Categorical"
            f" ({variant.replace('_', ' ')})"
        )
        filename = f"sweep_{base_title}_{variant}"
        function_name = f"example_sweep_{base_title}_{variant}"

        result_var_names = list(info["result_vars"].keys())

        gen = MetaGeneratorBase()

        # Extract extra imports (everything except "import bencher as bn")
        extra_imports = [
            line for line in info["imports"].split("\n") if line and line != "import bencher as bn"
        ]

        description, post_description = _get_sweep_description(
            self.float_vars_count, self.categorical_vars_count, variant
        )

        if self.sample_over_time:
            noise_val = max(0.1, 0.15 if self.sample_with_repeats > 1 else 0.0)
            class_code = _build_class_code(
                info,
                self.float_vars_count,
                self.categorical_vars_count,
                noise_val,
                time_offset=True,
            )

            defaults_kw = ""
            if self.sample_with_repeats > 1:
                defaults_kw = f", repeats={self.sample_with_repeats}"

            body = (
                f"run_cfg = bn.BenchRunCfg.with_defaults(run_cfg{defaults_kw})\n"
                "run_cfg.over_time = True\n"
                f"benchable = {info['class_name']}()\n"
                f"bench = benchable.to_bench(run_cfg)\n"
                f"_base_time = datetime(2000, 1, 1)\n"
                f"for i, offset in enumerate([0.0, 0.5, 1.0]):\n"
                f"    benchable._time_offset = offset\n"
                f"    run_cfg.clear_cache = True\n"
                f"    run_cfg.clear_history = i == 0\n"
                f"    res = bench.plot_sweep(\n"
                f'        "over_time",\n'
                f"        input_vars={input_var_names!r},\n"
                f"        result_vars={result_var_names!r},\n"
                f"        description={description!r},\n"
                f"        post_description={post_description!r},\n"
                f"        run_cfg=run_cfg,\n"
                f"        time_src=_base_time + timedelta(seconds=i),\n"
                f"    )\n"
            )
            noise_imports = "import random\n" if noise_val > 0 else ""
            imports = f"{noise_imports}{info['imports']}\nfrom datetime import datetime, timedelta"
            gen.generate_example(
                title=title,
                output_dir=f"{self.float_vars_count}_float/{variant}",
                filename=filename,
                function_name=function_name,
                imports=imports,
                body=body,
                class_code=class_code,
                run_kwargs={"level": 4},
            )
        else:
            noise_val = 0.15 if self.sample_with_repeats > 1 else 0.0
            class_code = _build_class_code(
                info, self.float_vars_count, self.categorical_vars_count, noise_val
            )

            run_kwargs = {"level": 4}
            if self.sample_with_repeats > 1:
                run_kwargs["repeats"] = self.sample_with_repeats

            sweep_extra_imports = list(extra_imports)
            if noise_val > 0:
                sweep_extra_imports.insert(0, "import random")

            gen.generate_sweep_example(
                title=title,
                output_dir=f"{self.float_vars_count}_float/{variant}",
                filename=filename,
                function_name=function_name,
                benchable_class=info["class_name"],
                benchable_module=None,
                input_vars=repr(input_var_names),
                result_vars=repr(result_var_names),
                class_code=class_code,
                extra_imports=sweep_extra_imports or None,
                description=description,
                post_description=post_description,
                run_kwargs=run_kwargs,
            )

        return super().__call__()


def example_meta(run_cfg: bn.BenchRunCfg | None = None) -> bn.Bench:
    bench = BenchMetaGen().to_bench(run_cfg)

    sweep_desc = (
        """Plot gallery showing all combinations of float and categorical input variables"""
    )

    few_cats = bn.sweep("categorical_vars_count", [0, 1, 2])

    bench.plot_sweep(
        title="Single Sample (0-1 float vars)",
        description=sweep_desc,
        input_vars=[bn.sweep("float_vars_count", [0, 1]), "categorical_vars_count"],
        const_vars=dict(sample_with_repeats=1, sample_over_time=False),
    )
    bench.plot_sweep(
        title="Single Sample (2-3 float vars)",
        description=sweep_desc,
        input_vars=[bn.sweep("float_vars_count", [2, 3]), few_cats],
        const_vars=dict(sample_with_repeats=1, sample_over_time=False),
    )
    bench.plot_sweep(
        title="Repeated Samples (10x)",
        description=sweep_desc,
        input_vars=[bn.sweep("float_vars_count", [0, 1]), "categorical_vars_count"],
        const_vars=dict(sample_with_repeats=10, sample_over_time=False),
    )
    bench.plot_sweep(
        title="Repeated Samples (3x)",
        description=sweep_desc,
        input_vars=[bn.sweep("float_vars_count", [2, 3]), few_cats],
        const_vars=dict(sample_with_repeats=3, sample_over_time=False),
    )
    bench.plot_sweep(
        title="Over Time 0-1 float (3 Snapshots)",
        description=sweep_desc,
        input_vars=[bn.sweep("float_vars_count", [0, 1]), "categorical_vars_count"],
        const_vars=dict(sample_with_repeats=1, sample_over_time=True),
    )
    bench.plot_sweep(
        title="Over Time 2-3 float (3 Snapshots)",
        description=sweep_desc,
        input_vars=[bn.sweep("float_vars_count", [2, 3]), few_cats],
        const_vars=dict(sample_with_repeats=1, sample_over_time=True),
    )
    bench.plot_sweep(
        title="Over Time + Repeats 0-1 float (3 Snapshots, 3x repeats)",
        description=sweep_desc,
        input_vars=[bn.sweep("float_vars_count", [0, 1]), "categorical_vars_count"],
        const_vars=dict(sample_with_repeats=3, sample_over_time=True),
    )

    return bench


if __name__ == "__main__":
    bn.run(example_meta)
