"""Meta-generator for aggregation examples.

Produces examples that demonstrate the ``aggregate`` parameter of ``plot_sweep``
in its various forms (list of dim names, True, int) and with different ``agg_fn``
options. All examples use gradient-based classes so each categorical combination
produces a visually distinct surface pattern.
"""

from bencher.example.meta.meta_generator_base import MetaGeneratorBase

# --- Shared inline class definitions (gradient-based) ---

_GRADIENT_2F_1C = '''\
class GradientDirection(bn.ParametrizedSweep):
    """2D gradient surface controlled by direction."""

    x = bn.FloatSweep(default=0, bounds=[0, 1], doc="X position")
    y = bn.FloatSweep(default=0, bounds=[0, 1], doc="Y position")
    direction = bn.StringSweep(["diagonal", "horizontal", "vertical"], doc="Gradient direction")

    out = bn.ResultFloat(units="v", doc="Surface value")

    def benchmark(self):
        if self.direction == "diagonal":
            self.out = self.x + self.y
        elif self.direction == "horizontal":
            self.out = self.x
        else:
            self.out = self.y'''

_GRADIENT_1F_1C = '''\
class GradientScale(bn.ParametrizedSweep):
    """1D gradient with categorical scale control."""

    x = bn.FloatSweep(default=0, bounds=[0, 1], doc="X position")
    scale = bn.StringSweep(["linear", "quadratic", "sqrt"], doc="Gradient scale")

    out = bn.ResultFloat(units="v", doc="Surface value")

    def benchmark(self):
        if self.scale == "linear":
            self.out = self.x
        elif self.scale == "quadratic":
            self.out = self.x**2
        else:
            self.out = self.x**0.5'''

_GRADIENT_1F_2C = '''\
class GradientDirectionScale(bn.ParametrizedSweep):
    """1D gradient with categorical direction and scale controls."""

    x = bn.FloatSweep(default=0, bounds=[0, 1], doc="X position")
    direction = bn.StringSweep(["positive", "negative", "symmetric"], doc="Gradient direction")
    scale = bn.StringSweep(["linear", "quadratic", "sqrt"], doc="Gradient scale")

    out = bn.ResultFloat(units="v", doc="Surface value")

    def benchmark(self):
        if self.direction == "positive":
            base = self.x
        elif self.direction == "negative":
            base = 1.0 - self.x
        else:
            base = abs(2.0 * self.x - 1.0)
        if self.scale == "linear":
            self.out = base
        elif self.scale == "quadratic":
            self.out = base**2
        else:
            self.out = base**0.5'''

_GRADIENT_2F_2C = '''\
class GradientSurface(bn.ParametrizedSweep):
    """2D gradient surface with categorical direction and scale controls."""

    x = bn.FloatSweep(default=0, bounds=[0, 1], doc="X position")
    y = bn.FloatSweep(default=0, bounds=[0, 1], doc="Y position")
    direction = bn.StringSweep(["diagonal", "horizontal", "vertical"], doc="Gradient direction")
    scale = bn.StringSweep(["linear", "quadratic", "sqrt"], doc="Gradient scale")

    out = bn.ResultFloat(units="v", doc="Surface value")

    def benchmark(self):
        if self.direction == "diagonal":
            base = self.x + self.y
        elif self.direction == "horizontal":
            base = self.x
        else:
            base = self.y
        if self.scale == "linear":
            self.out = base
        elif self.scale == "quadratic":
            self.out = base**2
        else:
            self.out = base**0.5'''


def example_meta_aggregation():
    """Generate aggregation example files."""
    gen = MetaGeneratorBase()

    # ---- 1) aggregate=["direction"]: 2 float + 1 cat → heatmap (direction averaged out) ----
    gen.generate_sweep_example(
        title="Aggregate by Name (list)",
        output_dir="aggregation",
        filename="agg_list_1_cat",
        function_name="example_agg_list_1_cat",
        benchable_class="GradientDirection",
        benchable_module=None,
        input_vars="['x', 'y', 'direction']",
        result_vars="['out']",
        class_code=_GRADIENT_2F_1C,
        extra_imports=[],
        description=(
            'Aggregate a specific dimension by name using aggregate=["direction"]. '
            "The direction categorical is averaged out, leaving a 2D heatmap of "
            "x vs y. This is the most explicit form — you list exactly which "
            "dimensions to collapse."
        ),
        post_description=(
            "The aggregated view shows a heatmap because two float dimensions "
            "remain after collapsing direction. The non-aggregated view below "
            "shows the full faceted heatmaps (one per direction)."
        ),
        aggregate=["direction"],
        run_kwargs={"level": 4},
    )

    # ---- 2) aggregate=True: 1 float + 1 cat → collapse to 1-D (keep first) ----
    gen.generate_sweep_example(
        title="Aggregate to 1-D (True)",
        output_dir="aggregation",
        filename="agg_all",
        function_name="example_agg_all",
        benchable_class="GradientScale",
        benchable_module=None,
        input_vars="['x', 'scale']",
        result_vars="['out']",
        class_code=_GRADIENT_1F_1C,
        extra_imports=[],
        description=(
            "Setting aggregate=True collapses all but the first input dimension, "
            "reducing the sweep to a 1-D plot. Useful when you want a simple "
            "curve from a multi-dimensional sweep."
        ),
        post_description=(
            "The aggregated view collapses all inputs except the first into a "
            "single mean ± std curve. The non-aggregated view below shows the "
            "full detail."
        ),
        aggregate=True,
        run_kwargs={"level": 4},
    )

    # ---- 3) aggregate=1: 1 float + 2 cat → last cat collapsed → line + 1 cat ----
    gen.generate_sweep_example(
        title="Aggregate Last N (int)",
        output_dir="aggregation",
        filename="agg_int",
        function_name="example_agg_int",
        benchable_class="GradientDirectionScale",
        benchable_module=None,
        input_vars="['x', 'direction', 'scale']",
        result_vars="['out']",
        class_code=_GRADIENT_1F_2C,
        extra_imports=[],
        description=(
            "Setting aggregate=1 collapses the last 1 input dimension "
            "(scale). The remaining dimensions (x, direction) "
            "produce a line plot faceted by direction."
        ),
        post_description=(
            "The aggregated view averages over the scale dimension. "
            "Use aggregate=N to collapse the last N dimensions in the input "
            "variable list."
        ),
        aggregate=1,
        run_kwargs={"level": 4},
    )

    # ---- 4) aggregate 2 cats: 2 float + 2 cat → heatmap (both cats averaged out) ----
    gen.generate_sweep_example(
        title="Aggregate 2 Categoricals (list)",
        output_dir="aggregation",
        filename="agg_list_2_cat",
        function_name="example_agg_list_2_cat",
        benchable_class="GradientSurface",
        benchable_module=None,
        input_vars="['x', 'y', 'direction', 'scale']",
        result_vars="['out']",
        class_code=_GRADIENT_2F_2C,
        extra_imports=[],
        description=(
            "Aggregate two categorical dimensions by name using "
            'aggregate=["direction", "scale"]. Both categoricals are averaged '
            "out, leaving a 2D heatmap of x vs y with mean and std computed "
            "across all direction/scale combinations."
        ),
        post_description=(
            "The aggregated view shows a single heatmap because two float "
            "dimensions remain after collapsing both categoricals. The "
            "non-aggregated view below shows the full faceted heatmaps "
            "(one per direction × scale) — each with a visually distinct "
            "gradient pattern."
        ),
        aggregate=["direction", "scale"],
        run_kwargs={"level": 4},
    )

    # ---- 5) aggregate + agg_fn="max": 2 float + 1 cat → heatmap of max ----
    gen.generate_sweep_example(
        title="Aggregate with Max",
        output_dir="aggregation",
        filename="agg_fn_max",
        function_name="example_agg_fn_max",
        benchable_class="GradientDirection",
        benchable_module=None,
        input_vars="['x', 'y', 'direction']",
        result_vars="['out']",
        class_code=_GRADIENT_2F_1C,
        extra_imports=[],
        description=(
            'Combine aggregate=["direction"] with agg_fn="max" to show the '
            "maximum surface value across directions for each "
            "(x, y) combination."
        ),
        post_description=(
            'Unlike the default mean aggregation, agg_fn="max" picks the '
            'highest direction at every point. Other options: "min", "sum", '
            '"median".'
        ),
        aggregate=["direction"],
        agg_fn="max",
        run_kwargs={"level": 4},
    )
