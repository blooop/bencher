"""Auto-generated example: Rerun Publishing — share .rrd recordings via git or HTTP."""

from typing import Any

import math
import bencher as bn

# Rerun recordings can be published to a git branch and viewed via the
# hosted rerun web viewer at https://app.rerun.io/.
#
# Workflow:
#   1. rr.init("my_app", spawn=True)  -- start rerun with a local .rrd file
#   2. rr.save("data.rrd")            -- persist the recording
#   3. Log data with rr.log(...)
#   4. bn.publish_and_view_rrd(...)    -- push .rrd to a git branch and
#      return a Panel pane that loads it in the hosted viewer
#
# Alternatively, use bn.rrd_to_pane(url) to view any .rrd file served
# over HTTP (local or remote) in a Panel HTML pane.
#
# Functions:
#   bn.rrd_to_pane(url, width, height)
#       -> Panel HTML pane embedding the rerun web viewer for the given URL
#
#   bn.publish_and_view_rrd(file_path, remote, branch_name, content_callback)
#       -> Pushes the .rrd file to a git branch and returns rrd_to_pane()
#
#   bn.run_file_server()
#       -> Starts a local file server to serve .rrd files from the cache dir


class WaveSweep(bn.ParametrizedSweep):
    """A simple sweep for demonstrating .rrd publishing patterns."""

    frequency = bn.FloatSweep(default=1.0, bounds=[0.5, 4.0], doc="Wave frequency", units="Hz")

    amplitude = bn.ResultVar(units="v", doc="Peak amplitude")

    def __call__(self, **kwargs: Any) -> Any:
        self.update_params_from_kwargs(**kwargs)
        self.amplitude = math.sin(self.frequency * math.pi)

        # To publish rerun data:
        #   import rerun as rr
        #   rr.init("my_app", spawn=True)
        #   rr.save("data.rrd")
        #   rr.log("wave", rr.Scalars(self.amplitude))
        #
        # Then view locally:
        #   pane = bn.rrd_to_pane("http://127.0.0.1:8001/data.rrd")
        #   pane.show()
        #
        # Or publish to a git branch:
        #   pane = bn.publish_and_view_rrd(
        #       "data.rrd",
        #       remote="https://github.com/user/repo.git",
        #       branch_name="rerun_data",
        #       content_callback=bn.github_content,
        #   )
        #   pane.show()

        return super().__call__(**kwargs)


def example_rerun_rrd_publish(run_cfg: bn.BenchRunCfg | None = None) -> bn.Bench:
    """Rerun Publishing — share .rrd recordings via git or HTTP."""
    bench = WaveSweep().to_bench(run_cfg)
    bench.plot_sweep(
        input_vars=["frequency"],
        result_vars=["amplitude"],
        description="Rerun .rrd recordings can be shared by publishing them to a "
        "git branch or serving them over HTTP. Use bn.rrd_to_pane(url) to embed "
        "the hosted rerun web viewer in a Panel pane, or "
        "bn.publish_and_view_rrd() to push the .rrd file to a git branch and "
        "view it immediately. Start a local file server with "
        "bn.run_file_server() to serve .rrd files from the cache directory.\n"
        "The file server uses Python's stdlib http.server — no extra dependencies.",
        post_description="This example shows the sweep pattern. To see live rerun "
        "output, install rerun-sdk (pip install rerun-sdk) and uncomment the "
        "rr.log() calls in the class definition.",
    )

    return bench


if __name__ == "__main__":
    bn.run(example_rerun_rrd_publish, level=3)
