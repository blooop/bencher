import logging
from copy import deepcopy

import panel as pn
import seaborn as sns

import bencher.plotting_functions as plt_func
from bencher.bench_cfg import BenchCfg, PltCfgBase, PltCntCfg, describe_benchmark
from bencher.optuna_conversions import collect_optuna_plots
from bencher.variables.parametrised_sweep import ParametrizedSweep

from bencher.variables.results import ResultVar, ResultVec

import xarray as xr


class BenchPlotter:
    @staticmethod
    def plot(bench_cfg: BenchCfg, main_tab=None, append_cols=None) -> pn.pane:
        """Given the dataset result of a benchmark run, automatically dedeuce how to plot the data based on the types of variables that were sampled

        Args:
            bench_cfg (BenchCfg): Information on how the benchmark was sampled and the resulting data

        Returns:
            pn.pane: A panel containing plot results
        """

        if main_tab is None:
            main_tab = pn.Tabs(tabs_location="left")
        if bench_cfg.auto_plot:
            if len(bench_cfg.result_vars) == 0:
                tabs = pn.Column(name=bench_cfg.title)
                tabs.append(pn.pane.Markdown(f"{bench_cfg.description}"))

            else:
                plot_cols = pn.Column(name="Plots View")
                plot_cols.append(pn.pane.Markdown(f"# {bench_cfg.title}\n{bench_cfg.description}"))
                benmark_str = describe_benchmark(bench_cfg)
                plot_cols.append(pn.pane.Markdown(f"{benmark_str}"))
                if bench_cfg.over_time:
                    if len(bench_cfg.ds.coords["over_time"]) > 1:
                        plot_cols.append(pn.pane.Markdown("## Results Over Time"))
                        plot_cols.append(BenchPlotter.plot_results_row(bench_cfg))
                    else:
                        plot_cols.append(
                            pn.pane.Markdown(
                                "Results over time needs at least 2 time snapshots to plot"
                            )
                        )

                plot_cols.append(pn.pane.Markdown("## Most Recent Results"))
                if bench_cfg.over_time:
                    bench_deep = deepcopy(bench_cfg)  # TODO do this in the future without copying
                    bench_deep.over_time = False
                    bench_deep.iv_time = []
                    last_time = bench_deep.ds.coords["over_time"][-1]
                    try:
                        bench_deep.ds = bench_deep.ds.sel(over_time=last_time)
                        plot_cols.append(BenchPlotter.plot_results_row(bench_deep))
                    except ValueError as e:
                        warning = f"failed to load historical data: {e}"
                        plot_cols.append(pn.pane.Markdown(warning))
                        logging.warning(warning)

                else:
                    plot_cols.append(BenchPlotter.plot_results_row(bench_cfg))

                if bench_cfg.use_optuna:
                    plot_cols.extend(collect_optuna_plots(bench_cfg))

                if append_cols is not None:
                    plot_cols.extend(append_cols)
                # plot_cols.append(pn.Column(pn.Row()))#attempt to add spacer to stop overlapping but does not work todo

                plot_cols.append(pn.pane.Markdown(f"{bench_cfg.post_description}"))

                tabs = pn.Tabs(plot_cols, name=bench_cfg.title)

                if bench_cfg.serve_xarray:
                    tabs.append(
                        pn.Column(
                            pn.pane.Markdown(
                                """This page shows the with the inputs of the parameter sweep and the results in its native N-D xarray dataset format."""
                            ),
                            bench_cfg.ds,
                            name="Xarray Dataset View",
                        )
                    )
                if bench_cfg.serve_pandas:
                    tabs.append(
                        pn.Column(
                            pn.pane.Markdown(
                                """This page shows the with the inputs of the parameter sweep and the results as a pandas multiindex."""
                            ),
                            bench_cfg.ds.to_dataframe(),
                            name="Pandas Dataframe MultiIndex View",
                        )
                    )

                    tabs.append(
                        pn.Column(
                            pn.pane.Markdown(
                                """This page shows the with the inputs of the parameter sweep and the results as a flattened padas dataframe."""
                            ),
                            bench_cfg.get_dataframe(),
                            name="Pandas Dataframe Flattened View",
                        )
                    )

            main_tab.append(tabs)
        main_tab.servable()
        return main_tab

    @staticmethod
    def plot_results_row(bench_cfg: BenchCfg) -> pn.Row:
        """Given a BenchCfg, plot each result variable and add to a panel row

        Args:
            bench_cfg (BenchCfg): The BenchCfg to plot

        Returns:
            pn.Row: A panel row with plots in it
        """
        # todo remove the scroll and make it resize dynamically
        plot_rows = pn.Row(name=bench_cfg.bench_name)

        plt_cnt_cfg = BenchPlotter.generate_plt_cnt_cfg(bench_cfg)

        for rv in bench_cfg.result_vars:
            plt_cnt_cfg.result_vars = 1
            if type(rv) == ResultVec:
                plt_cnt_cfg.vector_len = rv.size
            else:
                plt_cnt_cfg.vector_len = 1

            if bench_cfg.plot_lib is not None:
                logging.info(f"float: {plt_cnt_cfg.float_cnt}")
                logging.info(f"cat: {plt_cnt_cfg.cat_cnt}")
                logging.info(f"vec: {plt_cnt_cfg.vector_len}")
                plot_rows.append(bench_cfg.plot_lib.gather_plots(bench_cfg, rv, plt_cnt_cfg))
            # todo enable this check in future pr
            # if len(plot_rows) == 0:  # use the old plotting method as a backup
            plot_rows.append(
                pn.panel(BenchPlotter.plot_result_variable(bench_cfg, rv, plt_cnt_cfg))
            )

        return plot_rows

    @staticmethod
    def generate_plt_cnt_cfg(
        bench_cfg: BenchCfg,
    ) -> PltCntCfg:
        """Given a BenchCfg work out how many float and cat variables there are and store in a PltCntCfg class

        Args:
            bench_cfg (BenchCfg): See BenchCfg definition

        Raises:
            ValueError: If no plotting procedure could be automatically detected

        Returns:
            PltCntCfg: see PltCntCfg definition
        """
        plt_cnt_cfg = PltCntCfg()
        plt_cnt_cfg.float_vars = deepcopy(bench_cfg.iv_time)
        plt_cnt_cfg.cat_vars = []

        for iv in bench_cfg.input_vars:
            type_allocated = False
            typestr = str(type(iv))

            if "IntSweep" in typestr or "FloatSweep" in typestr:
                plt_cnt_cfg.float_vars.append(iv)
                type_allocated = True
            if "EnumSweep" in typestr or "BoolSweep" in typestr or "StringSweep" in typestr:
                plt_cnt_cfg.cat_vars.append(iv)
                type_allocated = True

            if not type_allocated:
                raise ValueError(f"No rule for type {typestr}")

        plt_cnt_cfg.float_cnt = len(plt_cnt_cfg.float_vars)
        plt_cnt_cfg.cat_cnt = len(plt_cnt_cfg.cat_vars)
        return plt_cnt_cfg

    @staticmethod
    def plot_result_variable(
        bench_cfg: BenchCfg, rv: ParametrizedSweep, plt_cnt_cfg: PltCntCfg
    ) -> pn.Column:
        """This method returns a single plot based on 1 result variable and a set of input variables.  It dedeuces the correct plot type by passing it to several configuration functions that operate on the number of inputs

        Args:
            bench_cfg (BenchCfg): A config of the input vars
            rv (ParametrizedSweep): a config of the result variable
            plt_cnt_cfg (PltCntCfg): A config of how many input types there are

        Raises:
            FileExistsError: If there are file naming conflicts

        Returns:
            PlotResult: A summary of all the data used to generate a plot
        """
        surf_col = pn.Column()

        sns_cfg = PltCfgBase()
        sns_cfg.y = rv.name  # by default the result variable is always plotted on the y axis

        if plt_cnt_cfg.float_cnt < 2:
            # set a marker for time series to its easy to see the measurment points
            if bench_cfg.over_time:
                sns_cfg.marker = "."
            if plt_cnt_cfg.float_cnt == 0:
                sns_cfg = BenchPlotter.plot_float_cnt_0(sns_cfg, plt_cnt_cfg)
            elif plt_cnt_cfg.float_cnt == 1:
                sns_cfg = BenchPlotter.plot_float_cnt_1(sns_cfg, plt_cnt_cfg)
            sns_cfg = BenchPlotter.get_axes_and_title(rv, sns_cfg, plt_cnt_cfg)
            surf_col.append(plt_func.plot_sns(bench_cfg, rv, sns_cfg))

        return surf_col

    @staticmethod
    def axis_mapping(cat_axis_order, sns_cfg: PltCfgBase, plt_cnt_cfg: PltCntCfg) -> PltCfgBase:
        """A function for determining the plot settings if there are 0 float variable and updates the PltCfgBase

        Args:
            sns_cfg (PltCfgBase): See PltCfgBase definition
            plt_cnt_cfg (PltCntCfg): See PltCntCfg definition

        Returns:
            PltCfgBase: See PltCfgBase definition
        """
        sns_dict = {}
        for i, v in enumerate(plt_cnt_cfg.cat_vars):
            axis = cat_axis_order[i]
            sns_dict[axis] = v.name

        sns_cfg.param.set_param(**sns_dict)

        return sns_cfg

    @staticmethod
    def get_axes_and_title(
        rv: ParametrizedSweep, sns_cfg: PltCfgBase, plt_cnt_cfg: PltCntCfg
    ) -> PltCntCfg:
        """Work out the axes label and plot tite

        Args:
            rv (ParametrizedSweep): result variable
            sns_cfg (PltCfgBase): plotting config
            plt_cnt_cfg (PltCntCfg): plot count config

        Returns:
            PltCfgBase: plot count config with titles added
        """
        all_vars = plt_cnt_cfg.float_vars + plt_cnt_cfg.cat_vars
        xvar = None
        for i in all_vars:
            if i.name == sns_cfg.x:
                xvar = i.units
        if xvar is not None:
            sns_cfg.xlabel = f"{sns_cfg.x} [{xvar}]"
        sns_cfg.ylabel = f"{sns_cfg.y} [{rv.units}]"
        sns_cfg.title = f"{sns_cfg.x} vs {sns_cfg.y}"
        return sns_cfg

    @staticmethod
    def plot_float_cnt_0(sns_cfg: PltCfgBase, plt_cnt_cfg: PltCntCfg) -> PltCfgBase:
        """A function for determining the plot settings if there are 0 float variable and updates the PltCfgBase

        Args:
            sns_cfg (PltCfgBase): See PltCfgBase definition
            plt_cnt_cfg (PltCntCfg): See PltCntCfg definition

        Returns:
            PltCfgBase: See PltCfgBase definition
        """

        if plt_cnt_cfg.float_cnt == 0:
            sns_cfg.plot_callback = sns.catplot
            sns_cfg.kind = "swarm"

            # as more cat variables are added, map them to these plot axes
            cat_axis_order = ["x", "row", "col", "hue"]
            sns_cfg = BenchPlotter.axis_mapping(cat_axis_order, sns_cfg, plt_cnt_cfg)

        return sns_cfg

    @staticmethod
    def plot_float_cnt_1(sns_cfg: PltCfgBase, plt_cnt_cfg: PltCntCfg) -> PltCfgBase:
        """A function for determining the plot settings if there is 1 float variable and updates the PltCfgBase

        Args:
            sns_cfg (PltCfgBase): See PltCfgBase definition
            plt_cnt_cfg (PltCntCfg): See PltCntCfg definition

        Returns:
            PltCfgBase: See PltCfgBase definition
        """

        if plt_cnt_cfg.float_cnt == 1:
            sns_cfg.x = plt_cnt_cfg.float_vars[0].name
            sns_cfg.kind = "line"
            sns_cfg.plot_callback = sns.relplot

            # as more cat variables are added, map them to these plot axes
            cat_axis_order = ["hue", "row", "col", "hue"]

            sns_cfg = BenchPlotter.axis_mapping(cat_axis_order, sns_cfg, plt_cnt_cfg)

        return sns_cfg

    @staticmethod
    def plot_float_cnt_2(plt_cnt_cfg: PltCntCfg, rv: ResultVar, debug: bool) -> PltCfgBase:
        """A function for determining the plot settings if there are 2 float variable and updates the PltCfgBase
        Args:
            sns_cfg (PltCfgBase): See PltCfgBase definition
            plt_cnt_cfg (PltCntCfg): See PltCntCfg definition
        Returns:
            PltCfgBase: See PltCfgBase definition
        """
        xr_cfg = PltCfgBase()
        if plt_cnt_cfg.float_cnt == 2:
            logging.info(f"surface plot: {rv.name}")
            xr_cfg.plot_callback_xra = xr.plot.plot
            xr_cfg.x = plt_cnt_cfg.float_vars[0].name
            xr_cfg.y = plt_cnt_cfg.float_vars[1].name
            xr_cfg.xlabel = f"{xr_cfg.x} [{plt_cnt_cfg.float_vars[0].units}]"
            xr_cfg.ylabel = f"{xr_cfg.y} [{plt_cnt_cfg.float_vars[1].units}]"
            xr_cfg.zlabel = f"{rv.name} [{rv.units}]"
            xr_cfg.title = f"{rv.name} vs ({xr_cfg.x} and {xr_cfg.y})"

            if plt_cnt_cfg.cat_cnt >= 1:
                logging.info("surface plot with 1 categorical")
                xr_cfg.row = plt_cnt_cfg.cat_vars[0].name
                xr_cfg.num_rows = len(plt_cnt_cfg.cat_vars[0].values(debug))
            if plt_cnt_cfg.cat_cnt >= 2:
                logging.info("surface plot with 2> categorical")
                xr_cfg.col = plt_cnt_cfg.cat_vars[1].name
                xr_cfg.num_cols = len(plt_cnt_cfg.cat_vars[1].values(debug))
        return xr_cfg
