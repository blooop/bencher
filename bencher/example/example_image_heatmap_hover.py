"""Example demonstrating composable images with hover heatmap.

This example shows how to:
1. Sample 2 continuous variables and 1 categorical variable
2. Generate images for each combination
3. Compute scalar metrics from images (sum/average)
4. Create a heatmap where hovering shows the composed image stack
"""

import bencher as bch
import numpy as np
import math
from PIL import Image, ImageDraw


def draw_pattern(radius: float, rotation: float, color: str, size: int = 200) -> Image.Image:
    """Draw a pattern with the given parameters.

    Args:
        radius: Pattern size (0.1 to 1.0)
        rotation: Rotation angle in degrees (0 to 360)
        color: Color name (red, green, blue, etc.)
        size: Image size in pixels

    Returns:
        PIL Image with the pattern
    """
    img = Image.new("RGB", (size, size), (255, 255, 255))
    draw = ImageDraw.Draw(img)

    # Color mapping
    color_map = {
        "red": (255, 50, 50),
        "green": (50, 255, 50),
        "blue": (50, 50, 255),
        "yellow": (255, 255, 50),
    }
    fill_color = color_map.get(color, (128, 128, 128))

    # Draw a rotated rectangle pattern
    center = size // 2
    scaled_radius = radius * size * 0.4

    # Calculate rotated rectangle corners
    angle_rad = math.radians(rotation)
    cos_a = math.cos(angle_rad)
    sin_a = math.sin(angle_rad)

    # Rectangle dimensions
    width = scaled_radius * 2
    height = scaled_radius

    # Corner offsets (before rotation)
    corners = [
        (-width / 2, -height / 2),
        (width / 2, -height / 2),
        (width / 2, height / 2),
        (-width / 2, height / 2),
    ]

    # Apply rotation and translation
    rotated_corners = []
    for x, y in corners:
        rx = x * cos_a - y * sin_a + center
        ry = x * sin_a + y * cos_a + center
        rotated_corners.append((rx, ry))

    # Draw the rotated rectangle
    draw.polygon(rotated_corners, fill=fill_color, outline=(0, 0, 0))

    # Draw a circle in the center with size based on radius
    circle_radius = scaled_radius * 0.3
    bbox = [
        center - circle_radius,
        center - circle_radius,
        center + circle_radius,
        center + circle_radius,
    ]
    draw.ellipse(bbox, fill=(0, 0, 0), outline=fill_color)

    return img


def compute_image_metrics(img: Image.Image) -> tuple[float, float]:
    """Compute scalar metrics from an image.

    Args:
        img: PIL Image

    Returns:
        Tuple of (average brightness, color intensity sum)
    """
    # Convert to numpy array
    img_array = np.array(img)

    # Average brightness (mean of all pixel values)
    avg_brightness = np.mean(img_array)

    # Color intensity sum (sum of non-white pixels)
    # White pixels are (255, 255, 255), so we measure deviation from white
    white_deviation = 255 - img_array
    color_intensity = np.sum(white_deviation)

    return avg_brightness, color_intensity


class ImageHeatmapHoverBenchmark(bch.ParametrizedSweep):
    """Benchmark that generates images and displays them in a hover heatmap."""

    # Two continuous variables
    radius = bch.FloatSweep(default=0.5, bounds=[0.2, 1.0], doc="Pattern radius", samples=4)
    rotation = bch.FloatSweep(
        default=0, bounds=[0, 180], doc="Rotation angle", units="deg", samples=4
    )

    # One categorical variable
    color = bch.StringSweep(["red", "green", "blue", "yellow"], doc="Pattern color")

    # Results
    pattern_image = bch.ResultImage(doc="Generated pattern image")
    avg_brightness = bch.ResultVar(units="intensity", doc="Average pixel brightness")
    color_intensity = bch.ResultVar(units="intensity", doc="Total color intensity")

    def __call__(self, **kwargs):
        """Generate pattern and compute metrics."""
        self.update_params_from_kwargs(**kwargs)

        # Generate image
        img = draw_pattern(self.radius, self.rotation, self.color)

        # Save image
        filepath = bch.gen_image_path("pattern")
        img.save(filepath, "PNG")
        self.pattern_image = str(filepath)

        # Compute metrics
        self.avg_brightness, self.color_intensity = compute_image_metrics(img)

        return self.get_results_values_as_dict()


class ComposedImageResult(bch.ParametrizedSweep):
    """Benchmark that composes images across categorical dimension."""

    radius = bch.FloatSweep(default=0.5, bounds=[0.2, 1.0], samples=4)
    rotation = bch.FloatSweep(default=0, bounds=[0, 180], units="deg", samples=4)
    compose_method = bch.EnumSweep(bch.ComposeType, doc="Image composition method")

    composed_image = bch.ResultImage(doc="Composed image from all colors")
    avg_brightness_composed = bch.ResultVar(units="intensity", doc="Average brightness")
    color_intensity_composed = bch.ResultVar(units="intensity", doc="Average color intensity")

    # Store dataset reference
    _source_dataset = None

    def __call__(self, **kwargs):
        self.update_params_from_kwargs(**kwargs)

        # Get dataset from class variable
        if self._source_dataset is None:
            raise RuntimeError("Source dataset not set. Call set_source_dataset() first.")

        ds = self._source_dataset

        # Create composable container for this radius/rotation pair
        container = bch.ComposableContainerImage()

        total_brightness = 0
        total_intensity = 0
        count = 0

        # Collect all color images for this radius/rotation
        for color in ["red", "green", "blue", "yellow"]:
            try:
                img_path = (
                    ds["pattern_image"]
                    .sel(radius=self.radius, rotation=self.rotation, color=color)
                    .values.item()
                )
                container.append(img_path)

                brightness = (
                    ds["avg_brightness"]
                    .sel(radius=self.radius, rotation=self.rotation, color=color)
                    .values.item()
                )
                intensity = (
                    ds["color_intensity"]
                    .sel(radius=self.radius, rotation=self.rotation, color=color)
                    .values.item()
                )

                total_brightness += brightness
                total_intensity += intensity
                count += 1
            except Exception as e:
                print(f"Warning: Could not load image for {color}: {e}")

        # Render composed image
        self.composed_image = container.to_image(
            bch.ImageRenderCfg(
                compose_method=self.compose_method,
                var_name="colors",
                var_value="all",
            )
        )

        # Average the metrics across colors
        self.avg_brightness_composed = total_brightness / count if count > 0 else 0
        self.color_intensity_composed = total_intensity / count if count > 0 else 0

        return self.get_results_values_as_dict()

    @classmethod
    def set_source_dataset(cls, dataset):
        """Set the source dataset for image composition."""
        cls._source_dataset = dataset


def example_image_heatmap_hover(run_cfg: bch.BenchRunCfg | None = None) -> bch.Bench:
    """Create benchmark with composable image heatmap hover functionality.

    This example demonstrates:
    - Sampling 2 continuous variables (radius, rotation) + 1 categorical (color)
    - Generating images for each combination
    - Computing scalar metrics from images
    - Composing images across the categorical dimension
    - Creating a heatmap where hovering shows the composed image stack

    Args:
        run_cfg: Benchmark run configuration

    Returns:
        Configured benchmark
    """
    if run_cfg is None:
        run_cfg = bch.BenchRunCfg()

    run_cfg.repeats = 1  # No need for repeats with deterministic image generation

    bench = ImageHeatmapHoverBenchmark().to_bench(run_cfg)

    # Run the benchmark sweep - this generates all individual images
    bench.plot_sweep(
        title="Image Generation with Composable Hover Heatmap",
        description="""
        This example demonstrates composable images with interactive heatmap visualization.
        Each point on the heatmap represents a (radius, rotation) pair, and when you hover
        over it, you see a composed image containing all color variants stacked together.
        """,
        plot_callbacks=False
    )

    res = bench.get_result()
    ds = res.ds

    # Set the source dataset for the composed image benchmark
    ComposedImageResult.set_source_dataset(ds)

    # Create benchmark for composed images
    composed_bench = ComposedImageResult().to_bench(run_cfg)
    composed_bench.plot_sweep(
        title="Composed Images Heatmap",
        input_vars=[
            ComposedImageResult.param.radius,
            ComposedImageResult.param.rotation,
            ComposedImageResult.param.compose_method,
        ],
        plot_callbacks=False
    )

    composed_res = composed_bench.get_result()

    # Create heatmaps with composed image hover - one for each composition method
    bench.report.append(
        composed_res.to(
            bch.HeatmapResult,
            result_var=ComposedImageResult.param.avg_brightness_composed,
            tap_var=[ComposedImageResult.param.composed_image],
            use_tap=True,
            agg_over_dims=["compose_method"],
        )
    )

    bench.report.append(
        composed_res.to(
            bch.HeatmapResult,
            result_var=ComposedImageResult.param.color_intensity_composed,
            tap_var=[ComposedImageResult.param.composed_image],
            use_tap=True,
            agg_over_dims=["compose_method"],
        )
    )

    return bench


if __name__ == "__main__":
    # Run the composable image heatmap example
    ex_run_cfg = bch.BenchRunCfg()
    bench = example_image_heatmap_hover(ex_run_cfg)
    bench.report.show()
