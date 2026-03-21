"""Meta-generator: Performance self-introspection examples.

Generates examples that benchmark bencher's own overhead, enabling
performance tracking across commits via the documentation gallery.
"""

from typing import Any

import bencher as bch
from bencher.example.meta.meta_generator_base import MetaGeneratorBase

OUTPUT_DIR = "performance"

PERFORMANCE_EXAMPLES = [
    "self_benchmark",
]


class MetaPerformance(MetaGeneratorBase):
    """Generate Python examples for bencher self-introspection."""

    example = bch.StringSweep(PERFORMANCE_EXAMPLES, doc="Which performance example to generate")

    def __call__(self, **kwargs: Any) -> Any:
        self.update_params_from_kwargs(**kwargs)

        if self.example == "self_benchmark":
            self._generate_self_benchmark()

        return super().__call__()

    def _generate_self_benchmark(self):
        """Generate the self-benchmark example by importing from the canonical module."""
        self.generate_sweep_example(
            title="Bencher self-introspection: overhead vs problem size",
            output_dir=OUTPUT_DIR,
            filename="self_benchmark",
            function_name="example_self_benchmark",
            benchable_class="BencherSelfBenchmark",
            benchable_module="bencher.example.example_self_benchmark",
            input_vars='["num_samples"]',
            result_vars='["total_ms", "dataset_setup_ms", '
            '"job_submit_and_execute_ms", "result_collection_ms"]',
            extra_imports=[
                "from bencher.example.example_self_benchmark import TrivialWorkload  # noqa: F401"
            ],
        )


def example_meta_performance():
    """Generate all performance self-introspection examples."""
    gen = MetaPerformance()
    for example in PERFORMANCE_EXAMPLES:
        gen(example=example)
