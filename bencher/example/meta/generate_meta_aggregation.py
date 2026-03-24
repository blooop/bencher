"""Meta-generator for aggregation examples.

Produces examples that demonstrate the ``aggregate`` parameter of ``plot_sweep``
in its various forms (list of dim names, True, int) and with different ``agg_fn``
options. Each example reuses a class definition from the main sweep registry.
"""

from bencher.example.meta.meta_generator_base import MetaGeneratorBase
from bencher.example.meta.generate_meta import INLINE_CLASSES, _build_class_code


def example_meta_aggregation():
    """Generate aggregation example files."""
    gen = MetaGeneratorBase()

    # ---- 1) aggregate=["codec"]: 2 float + 1 cat → heatmap (codec averaged out) ----
    info = INLINE_CLASSES[(2, 1)]
    class_code = _build_class_code(info, 2, 1, noise_val=0.15)
    gen.generate_sweep_example(
        title="Aggregate by Name (list)",
        output_dir="aggregation",
        filename="agg_list_1_cat",
        function_name="example_agg_list_1_cat",
        benchable_class=info["class_name"],
        benchable_module=None,
        input_vars="['block_size', 'entropy', 'codec']",
        result_vars="['ratio']",
        class_code=class_code,
        extra_imports=["import random", "import math"],
        description=(
            "Aggregate a specific dimension by name using aggregate=[\"codec\"]. "
            "The codec categorical is averaged out, leaving a 2D heatmap of "
            "block_size vs entropy. This is the most explicit form — you list "
            "exactly which dimensions to collapse."
        ),
        post_description=(
            "The aggregated view shows a heatmap because two float dimensions "
            "remain after collapsing codec. The non-aggregated view below "
            "shows the full faceted heatmaps (one per codec)."
        ),
        aggregate=["codec"],
        run_kwargs={"level": 4, "repeats": 3},
    )

    # ---- 2) aggregate=True: 1 float + 1 cat → all dims collapsed → bar ----
    info = INLINE_CLASSES[(1, 1)]
    class_code = _build_class_code(info, 1, 1, noise_val=0.15)
    gen.generate_sweep_example(
        title="Aggregate All (True)",
        output_dir="aggregation",
        filename="agg_all",
        function_name="example_agg_all",
        benchable_class=info["class_name"],
        benchable_module=None,
        input_vars="['array_size', 'algorithm']",
        result_vars="['time']",
        class_code=class_code,
        extra_imports=["import random", "import math"],
        description=(
            "Setting aggregate=True collapses every input dimension, giving a "
            "single scalar summary. Useful when you want one headline number "
            "from a multi-dimensional sweep."
        ),
        post_description=(
            "The aggregated view collapses all inputs into a single mean ± std. "
            "The non-aggregated view below shows the full detail."
        ),
        aggregate=True,
        run_kwargs={"level": 4, "repeats": 3},
    )

    # ---- 3) aggregate=1: 1 float + 2 cat → last cat collapsed → line + 1 cat ----
    info = INLINE_CLASSES[(1, 2)]
    class_code = _build_class_code(info, 1, 2, noise_val=0.15)
    gen.generate_sweep_example(
        title="Aggregate Last N (int)",
        output_dir="aggregation",
        filename="agg_int",
        function_name="example_agg_int",
        benchable_class=info["class_name"],
        benchable_module=None,
        input_vars="['array_size', 'algorithm', 'distribution']",
        result_vars="['time']",
        class_code=class_code,
        extra_imports=["import random", "import math"],
        description=(
            "Setting aggregate=1 collapses the last 1 input dimension "
            "(distribution). The remaining dimensions (array_size, algorithm) "
            "produce a line plot faceted by algorithm."
        ),
        post_description=(
            "The aggregated view averages over the distribution dimension. "
            "Use aggregate=N to collapse the last N dimensions in the input "
            "variable list."
        ),
        aggregate=1,
        run_kwargs={"level": 4, "repeats": 3},
    )

    # ---- 4) aggregate + agg_fn="max": 2 float + 1 cat → heatmap of max ----
    info = INLINE_CLASSES[(2, 1)]
    class_code = _build_class_code(info, 2, 1, noise_val=0.15)
    gen.generate_sweep_example(
        title="Aggregate with Max",
        output_dir="aggregation",
        filename="agg_fn_max",
        function_name="example_agg_fn_max",
        benchable_class=info["class_name"],
        benchable_module=None,
        input_vars="['block_size', 'entropy', 'codec']",
        result_vars="['ratio']",
        class_code=class_code,
        extra_imports=["import random", "import math"],
        description=(
            "Combine aggregate=[\"codec\"] with agg_fn=\"max\" to show the "
            "best-case (maximum) compression ratio across codecs for each "
            "(block_size, entropy) combination."
        ),
        post_description=(
            "Unlike the default mean aggregation, agg_fn=\"max\" picks the "
            "best codec at every point. Other options: \"min\", \"sum\", "
            "\"median\"."
        ),
        aggregate=["codec"],
        agg_fn="max",
        run_kwargs={"level": 4, "repeats": 3},
    )
