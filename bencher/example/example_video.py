import colorcet as cc
import numpy as np
import numpy.typing as npt
from PIL import Image

import bencher as bn


def apply_colormap(data: npt.NDArray) -> npt.NDArray:
    """Apply a perceptually uniform colormap to the data"""
    # Normalize data to [0, 1]
    normalized = (data - data.min()) / (data.max() - data.min())
    # Convert hex colors to RGB values using numpy's frombuffer
    colors = np.array(
        [np.frombuffer(bytes.fromhex(c.lstrip("#")), dtype=np.uint8) for c in cc.rainbow]
    )
    # Map normalized values to colormap indices
    indices = (normalized * (len(colors) - 1)).astype(int)
    # Create RGB array from the colormap
    return colors[indices]


class TuringPattern(bn.ParametrizedSweep):
    alpha = bn.FloatSweep(default=2.8e-4, bounds=(2e-4, 5e-3))
    beta = bn.FloatSweep(default=5e-3, bounds=(1e-3, 9e-3))
    tau = bn.FloatSweep(default=0.1, bounds=(0.01, 0.5))
    k = bn.FloatSweep(default=-0.005, bounds=(-0.01, 0.01))

    size = bn.IntSweep(default=30, bounds=(30, 200), doc="size of the 2D grid")
    time = bn.FloatSweep(default=20.0, bounds=(1, 100), doc="total time of simulation")
    dt = bn.FloatSweep(default=0.001, doc="simulation time step")

    video = bn.ResultVideo()
    score = bn.ResultFloat()
    img = bn.ResultImage()
    img_extracted = bn.ResultImage()

    def laplacian(self, z, dx):
        z_top = z[0:-2, 1:-1]
        z_left = z[1:-1, 0:-2]
        z_bottom = z[2:, 1:-1]
        z_right = z[1:-1, 2:]
        z_center = z[1:-1, 1:-1]
        return (z_top + z_left + z_bottom + z_right - 4 * z_center) / dx**2

    def update(self, u, v, dx):
        # We compute the Laplacian of u and v.
        delta_u = self.laplacian(u, dx)
        delta_v = self.laplacian(v, dx)
        # We take the values of u and v inside the grid.
        u_c = u[1:-1, 1:-1]
        v_c = v[1:-1, 1:-1]
        # We update the variables.
        u[1:-1, 1:-1], v[1:-1, 1:-1] = (
            u_c + self.dt * (self.alpha * delta_u + u_c - u_c**3 - v_c + self.k),
            v_c + self.dt * (self.beta * delta_v + u_c - v_c) / self.tau,
        )
        # Neumann conditions: derivatives at the edges
        # are null.
        for z in (u, v):
            z[0, :] = z[1, :]
            z[-1, :] = z[-2, :]
            z[:, 0] = z[:, 1]
            z[:, -1] = z[:, -2]

    def benchmark(self):
        n = int(self.time / self.dt)
        dx = 2.0 / self.size

        u = np.random.rand(self.size, self.size)
        v = np.random.rand(self.size, self.size)

        vid_writer = bn.VideoWriter()
        for i in range(n):
            self.update(u, v, dx)
            if i % 500 == 0:
                # Apply colormap to create RGB image
                rgb = apply_colormap(u)
                # Create PIL image with alpha channel
                img = Image.fromarray(rgb, "RGB").convert("RGBA")
                img = img.resize((200, 200), Image.Resampling.LANCZOS)
                rgb_alpha = np.array(img)
                vid_writer.append(rgb_alpha)

        self.img = bn.add_image(rgb_alpha)
        self.video = vid_writer.write()
        self.img_extracted = bn.video_writer.VideoWriter.extract_frame(self.video)
        print("img path", self.img_extracted)
        self.score = self.alpha + self.beta


def example_video(run_cfg: bn.BenchRunCfg | None = None) -> bn.Bench:
    bench = TuringPattern().to_bench(run_cfg)

    bench.plot_sweep(
        "Turing patterns with different parameters",
        input_vars=["alpha", "beta"],
        result_vars=["video"],
    )

    return bench


def example_video_tap(run_cfg: bn.BenchRunCfg | None = None) -> bn.Bench:  # pragma: no cover
    bench = TuringPattern().to_bench(run_cfg)
    res = bench.plot_sweep(input_vars=["alpha", "beta"])

    bench.report.append(res.to_video_grid(result_types=(bn.ResultVideo)))

    res = bench.plot_sweep(input_vars=["alpha"])
    bench.report.append(
        res.to_video_grid(
            result_types=(bn.ResultVideo),
            compose_method_list=[bn.ComposeType.right],
        )
    )

    bench.worker_class_instance.get_results_only()

    return bench


if __name__ == "__main__":
    bn.run(example_video_tap, subsampling_divisions=2)
