"""A server for display plots of benchmark results"""

from __future__ import annotations

import logging
import os
from pathlib import Path
from threading import Thread

import panel as pn
from diskcache import Cache
from tornado.web import StaticFileHandler

from bencher.bench_cfg import BenchCfg, BenchPlotSrvCfg

logging.basicConfig(level=logging.INFO)


class _CorsStaticHandler(StaticFileHandler):
    """A Tornado static file handler that adds CORS headers.

    Required for rerun integration: the rerun web viewer (localhost:9090)
    fetches .rrd files from the Panel server (localhost:8051).  Without
    Access-Control-Allow-Origin and OPTIONS preflight handling the browser
    silently blocks the cross-origin fetch and the viewer shows 0 B.
    """

    def data_received(self, chunk):  # pragma: no cover
        pass

    def set_default_headers(self):
        self.set_header("Access-Control-Allow-Origin", "*")
        self.set_header("Access-Control-Allow-Methods", "GET, OPTIONS")
        self.set_header("Access-Control-Allow-Headers", "*")

    def options(self, *_args):
        self.set_status(204)
        self.finish()


class BenchPlotServer:
    """A server for display plots of benchmark results"""

    def __init__(self) -> None:
        """Create a new BenchPlotServer object"""

    def plot_server(
        self, bench_name: str, plot_cfg: BenchPlotSrvCfg | None = None, plots_instance=None
    ) -> Thread:
        """Load previously calculated benchmark data from the database and start a plot server to display it

        Args:
            bench_name (str): The name of the benchmark and output folder for the figures
            plot_cfg (BenchPlotSrvCfg, optional): Options for the plot server. Defaults to None.

        Raises:
            FileNotFoundError: No data found was found in the database to plot
        """

        if plot_cfg is None:
            plot_cfg = BenchPlotSrvCfg()

        if plots_instance is None:
            plots_instance = self.load_data_from_cache(bench_name)
        if plot_cfg.port is not None and plot_cfg.allow_ws_origin:
            os.environ["BOKEH_ALLOW_WS_ORIGIN"] = f"localhost:{plot_cfg.port}"

        return self.serve(bench_name, plots_instance, port=plot_cfg.port, show=plot_cfg.show)

    def load_data_from_cache(self, bench_name: str) -> tuple[BenchCfg, list[pn.panel]] | None:
        """Load previously calculated benchmark data from the database and start a plot server to display it

        Args:
            bench_name (str): The name of the benchmark and output folder for the figures

        Returns:
            tuple[BenchCfg, list[pn.panel]] | None: benchmark result data and any additional panels

        Raises:
            FileNotFoundError: No data found was found in the database to plot
        """

        with Cache("cachedir/benchmark_inputs") as cache:
            if bench_name in cache:
                logging.info(f"loading benchmarks: {bench_name}")
                # use the benchmark name to look up the hash of the results
                bench_cfg_hashes = cache[bench_name]
                plots_instance = None
                for bench_cfg_hash in bench_cfg_hashes:
                    # load the results based on the hash retrieved from the benchmark name
                    if bench_cfg_hash in cache:
                        logging.info(f"loading cached results from key: {bench_cfg_hash}")
                        bench_res = cache[bench_cfg_hash]
                        logging.info(f"loaded: {bench_res.bench_cfg.title}")

                        plots_instance = bench_res.to_auto_plots()
                    else:
                        raise FileNotFoundError(
                            "The benchmarks have been run and saved, but the specific results you are trying to load do not exist.  This should not happen and could be because the cache was cleared."
                        )
                return plots_instance
        raise FileNotFoundError(
            "This benchmark name does not exist in the results cache. Was not able to load the results to plot!  Make sure to run the bencher to generate and save results to the cache"
        )

    def serve(
        self,
        bench_name: str,
        plots_instance: list[pn.panel],
        port: int | None = None,
        show: bool = True,
    ) -> Thread:
        """Launch a panel server to view results


        Args:
            bench_cfg (BenchCfg): benchmark results
            plots_instance (list[pn.panel]): list of panel objects to display
            port (int): use a fixed port to launch the server
        """

        # suppress verbose tornado and bokeh output
        for logger in ["tornado", "bokeh"]:
            logging.getLogger(logger).setLevel(logging.WARNING)

        extra = self._rrd_extra_patterns()

        # When serving .rrd files, use a known port so rerun iframe URLs work.
        if port is None and extra:
            from bencher.utils_rrd import PANEL_PORT

            port = PANEL_PORT

        serve_kwargs = dict(
            title=bench_name,
            threaded=True,
            show=show,
            address="0.0.0.0",
            websocket_origin=["*"],
            extra_patterns=extra,
        )
        if port is not None:
            serve_kwargs["port"] = port

        return pn.serve(plots_instance, **serve_kwargs)

    @staticmethod
    def _rrd_extra_patterns() -> list:
        """Return Tornado route patterns for serving .rrd files with CORS headers.

        Mounts ``cachedir/rrd/`` at ``/rrd_static/`` so that the local rerun
        viewer can fetch ``.rrd`` files from the Panel server.  See the module
        docstring in ``utils_rerun.py`` for the full architecture explanation.
        """
        rrd_dir = Path("cachedir/rrd").resolve()
        if rrd_dir.is_dir():
            return [
                (
                    r"/rrd_static/(.*)",
                    _CorsStaticHandler,
                    {"path": str(rrd_dir)},
                )
            ]
        return []
