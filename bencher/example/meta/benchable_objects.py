"""Benchable classes demonstrating each result type.

Each class is a minimal ``ParametrizedSweep`` that exercises one result type.
They are used by the meta generators to produce notebook code and can also be
imported directly in notebooks.
"""

import math
import random

import numpy as np
from PIL import Image, ImageDraw

import bencher as bch


class BenchableBoolResult(bch.ParametrizedSweep):
    """Demonstrates ResultBool — a boolean pass/fail metric."""

    threshold = bch.FloatSweep(default=0.5, bounds=[0.1, 0.9], doc="Decision threshold")
    difficulty = bch.FloatSweep(default=0.5, bounds=[0.0, 1.0], doc="Problem difficulty")

    pass_rate = bch.ResultBool(doc="Whether the score exceeded the threshold")

    noise_scale = bch.FloatSweep(default=0.0, bounds=[0.0, 1.0], doc="Noise scale")

    def __call__(self, **kwargs):
        self.update_params_from_kwargs(**kwargs)
        score = math.sin(math.pi * self.threshold) * (1.0 - 0.5 * self.difficulty)
        if self.noise_scale > 0:
            score += random.gauss(0, self.noise_scale)
        self.pass_rate = score > 0.5
        return super().__call__()


class BenchableVecResult(bch.ParametrizedSweep):
    """Demonstrates ResultVec — a fixed-size vector output."""

    x = bch.FloatSweep(default=0.5, bounds=[0.0, 1.0], doc="X coordinate")
    y = bch.FloatSweep(default=0.5, bounds=[0.0, 1.0], doc="Y coordinate")

    position = bch.ResultVec(3, "m", doc="3D position vector")

    noise_scale = bch.FloatSweep(default=0.0, bounds=[0.0, 1.0], doc="Noise scale")

    def __call__(self, **kwargs):
        self.update_params_from_kwargs(**kwargs)
        vals = [
            math.sin(math.pi * self.x),
            math.cos(math.pi * self.y),
            math.sin(math.pi * (self.x + self.y)),
        ]
        if self.noise_scale > 0:
            vals = [v + random.gauss(0, self.noise_scale) for v in vals]
        self.position = vals
        return super().__call__()


class BenchableStringResult(bch.ParametrizedSweep):
    """Demonstrates ResultString — a markdown string output."""

    label = bch.StringSweep(["alpha", "beta", "gamma"], doc="Label category")
    value = bch.FloatSweep(default=0.5, bounds=[0.0, 1.0], doc="Numeric value")

    report = bch.ResultString(doc="Formatted report string")

    def __call__(self, **kwargs):
        self.update_params_from_kwargs(**kwargs)
        text = (
            f"Label: {self.label}\n\tValue: {self.value:.3f}\n\tScore: {math.sin(self.value):.3f}"
        )
        self.report = bch.tabs_in_markdown(text)
        return super().__call__()


class BenchablePathResult(bch.ParametrizedSweep):
    """Demonstrates ResultPath — a file download output."""

    content = bch.StringSweep(["report_a", "report_b", "report_c"], doc="Report content variant")

    file_result = bch.ResultPath(doc="Generated report file")

    def __call__(self, **kwargs):
        self.update_params_from_kwargs(**kwargs)
        filename = bch.gen_path(self.content, suffix=".txt")
        with open(filename, "w", encoding="utf-8") as f:
            f.write(f"content: {self.content}\ntimestamp: deterministic")
        self.file_result = filename
        return super().__call__()


class BenchableDataSetResult(bch.ParametrizedSweep):
    """Demonstrates ResultDataSet — an xarray dataset output."""

    value = bch.FloatSweep(default=5.0, bounds=[0, 10], doc="Base value")
    scale = bch.FloatSweep(default=1.0, bounds=[0.5, 2.0], doc="Scale factor")

    result_ds = bch.ResultDataSet(doc="Generated dataset")

    def __call__(self, **kwargs):
        import xarray as xr

        self.update_params_from_kwargs(**kwargs)
        vector = [self.scale * (v + self.value) for v in range(1, 5)]
        data_array = xr.DataArray(vector, dims=["index"], coords={"index": np.arange(len(vector))})
        result_df = xr.Dataset({"result_ds": data_array})
        self.result_ds = bch.ResultDataSet(result_df.to_pandas())
        return super().__call__()


class BenchableMultiObjective(bch.ParametrizedSweep):
    """Demonstrates multi-objective optimization with competing objectives."""

    x = bch.FloatSweep(default=0.5, bounds=[0.0, 1.0], doc="Design parameter X")
    y = bch.FloatSweep(default=0.5, bounds=[0.0, 1.0], doc="Design parameter Y")

    performance = bch.ResultVar("score", bch.OptDir.maximize, doc="Performance (maximize)")
    cost = bch.ResultVar("$", bch.OptDir.minimize, doc="Cost (minimize)")

    noise_scale = bch.FloatSweep(default=0.0, bounds=[0.0, 1.0], doc="Noise scale")

    def __call__(self, **kwargs):
        self.update_params_from_kwargs(**kwargs)
        self.performance = math.sin(math.pi * self.x) * math.cos(0.5 * math.pi * self.y) + 0.5
        self.cost = 0.3 + 0.7 * self.x + 0.5 * self.y**2
        if self.noise_scale > 0:
            self.performance += random.gauss(0, self.noise_scale)
            self.cost += random.gauss(0, self.noise_scale * 0.5)
        return super().__call__()


class BenchableIntFloat(bch.ParametrizedSweep):
    """Demonstrates integer vs float sweep comparison."""

    int_input = bch.IntSweep(default=5, bounds=[0, 10], doc="Discrete integer input")
    float_input = bch.FloatSweep(default=5.0, bounds=[0.0, 10.0], doc="Continuous float input")

    output = bch.ResultVar("ul", doc="Computed output")

    def __call__(self, **kwargs):
        self.update_params_from_kwargs(**kwargs)
        self.output = math.sin(self.int_input * 0.3) + math.cos(self.float_input * 0.2)
        return super().__call__()


def _polygon_points(radius, sides, start_angle=0.0):
    """Compute polygon vertices on a unit circle."""
    points = []
    for ang in np.linspace(0, 360, sides + 1):
        angle = math.radians(start_angle + ang)
        points.append([math.sin(angle) * radius, math.cos(angle) * radius])
    return points


def _draw_polygon_image(points, color, linewidth, size=200):
    """Draw a polygon onto a transparent RGBA image and return the PIL Image."""
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    scaled = [((p[0] + 1) * size / 2, (1 - p[1]) * size / 2) for p in points]
    draw.line(scaled, fill=color, width=int(linewidth))
    return img


class BenchableImageResult(bch.ParametrizedSweep):
    """Demonstrates ResultImage — a lightweight polygon renderer."""

    sides = bch.IntSweep(default=3, bounds=(3, 7), doc="Number of polygon sides")
    radius = bch.FloatSweep(default=0.6, bounds=(0.2, 1.0), doc="Polygon radius")
    color = bch.StringSweep(["red", "green", "blue"], doc="Line color")

    polygon = bch.ResultImage(doc="Rendered polygon image")
    area = bch.ResultVar("u^2", doc="Polygon area")

    def __call__(self, **kwargs):
        self.update_params_from_kwargs(**kwargs)
        points = _polygon_points(self.radius, self.sides)
        img = _draw_polygon_image(points, self.color, linewidth=3)
        filepath = bch.gen_image_path("polygon")
        img.save(filepath, "PNG")
        self.polygon = str(filepath)
        self.area = (self.sides * (2 * self.radius * math.sin(math.pi / self.sides)) ** 2) / (
            4 * math.tan(math.pi / self.sides)
        )
        return super().__call__()


class BenchableRobotArm(bch.ParametrizedSweep):
    """Simulates a 2-joint robot arm reaching for a target.

    Sweep the joint angles to explore how arm configuration affects reach distance
    and energy consumption.  This is a relatable physical-simulation use case that
    new users can adapt to their own domain.
    """

    joint1 = bch.FloatSweep(
        default=0.5, bounds=[0.0, math.pi], doc="Angle of the first joint (shoulder)", units="rad"
    )
    joint2 = bch.FloatSweep(
        default=0.5, bounds=[0.0, math.pi], doc="Angle of the second joint (elbow)", units="rad"
    )
    gripper = bch.StringSweep(
        ["suction", "parallel_jaw", "soft"], doc="Type of gripper attached to the end-effector"
    )

    reach = bch.ResultVar("m", doc="Euclidean distance from base to end-effector")
    energy = bch.ResultVar("J", doc="Estimated energy to hold the pose")

    noise_scale = bch.FloatSweep(default=0.0, bounds=[0.0, 1.0], doc="Noise scale")

    # Arm link lengths
    _L1 = 1.0
    _L2 = 0.8

    def __call__(self, **kwargs):
        self.update_params_from_kwargs(**kwargs)

        # Forward kinematics for a planar 2-link arm
        x = self._L1 * math.cos(self.joint1) + self._L2 * math.cos(self.joint1 + self.joint2)
        y = self._L1 * math.sin(self.joint1) + self._L2 * math.sin(self.joint1 + self.joint2)
        self.reach = math.sqrt(x**2 + y**2)

        # Energy model: torque proportional to gravity load on each joint
        gripper_mass = {"suction": 0.5, "parallel_jaw": 1.0, "soft": 0.7}[self.gripper]
        self.energy = (
            abs(math.sin(self.joint1)) * (self._L1 + self._L2) * gripper_mass
            + abs(math.sin(self.joint2)) * self._L2 * gripper_mass
        )

        if self.noise_scale > 0:
            self.reach += random.gauss(0, self.noise_scale * 0.1)
            self.energy += random.gauss(0, self.noise_scale * 0.05)

        return super().__call__()


class BenchableMLTrainer(bch.ParametrizedSweep):
    """Simulates an ML training run to explore hyper-parameter sensitivity.

    Sweep learning rate, dropout, and optimizer choice to see how they affect
    validation accuracy and training time.  This mirrors a common ML workflow
    and gives users a template for their own hyper-parameter searches.
    """

    learning_rate = bch.FloatSweep(
        default=0.01, bounds=[0.0001, 0.1], doc="Optimizer learning rate"
    )
    dropout = bch.FloatSweep(default=0.2, bounds=[0.0, 0.8], doc="Dropout probability")
    optimizer = bch.StringSweep(["adam", "sgd", "rmsprop"], doc="Optimizer algorithm")

    accuracy = bch.ResultVar("%", bch.OptDir.maximize, doc="Validation accuracy (higher is better)")
    training_time = bch.ResultVar(
        "s", bch.OptDir.minimize, doc="Training wall-clock time (lower is better)"
    )

    noise_scale = bch.FloatSweep(default=0.0, bounds=[0.0, 1.0], doc="Noise scale")

    def __call__(self, **kwargs):
        self.update_params_from_kwargs(**kwargs)

        # Simulated accuracy: peaks around lr=0.01, low dropout, adam is best
        lr_score = math.exp(-((math.log10(self.learning_rate) + 2) ** 2))  # peak at 0.01
        dropout_penalty = 0.3 * self.dropout**2
        opt_bonus = {"adam": 0.05, "sgd": 0.0, "rmsprop": 0.03}[self.optimizer]
        self.accuracy = max(0.0, min(100.0, (lr_score - dropout_penalty + opt_bonus + 0.5) * 80))

        # Simulated training time: higher lr converges faster, adam is fastest
        opt_speed = {"adam": 1.0, "sgd": 1.5, "rmsprop": 1.2}[self.optimizer]
        self.training_time = opt_speed * (50 + 200 * (1 - lr_score) + 30 * self.dropout)

        if self.noise_scale > 0:
            self.accuracy += random.gauss(0, self.noise_scale * 5)
            self.training_time += random.gauss(0, self.noise_scale * 10)
            self.accuracy = max(0.0, min(100.0, self.accuracy))
            self.training_time = max(1.0, self.training_time)

        return super().__call__()


class BenchableVideoResult(bch.ParametrizedSweep):
    """Demonstrates ResultVideo — a polygon rotation animation."""

    sides = bch.IntSweep(default=4, bounds=(3, 7), doc="Number of polygon sides")
    speed = bch.FloatSweep(default=1.0, bounds=(0.5, 3.0), doc="Rotation speed multiplier")

    animation = bch.ResultVideo(doc="Rotating polygon video")
    frame_snapshot = bch.ResultImage(doc="Last frame snapshot")

    def __call__(self, **kwargs):
        self.update_params_from_kwargs(**kwargs)
        vid_writer = bch.VideoWriter()
        num_frames = 8
        for i in range(num_frames):
            angle = self.speed * (360.0 * i / num_frames)
            points = _polygon_points(0.7, self.sides, start_angle=angle)
            img = _draw_polygon_image(points, "white", linewidth=3, size=200)
            vid_writer.append(np.array(img.convert("RGB")))
        self.animation = vid_writer.write()
        self.frame_snapshot = bch.VideoWriter.extract_frame(self.animation)
        return super().__call__()
