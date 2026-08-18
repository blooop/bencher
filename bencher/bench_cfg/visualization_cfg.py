from __future__ import annotations

import param

from bencher.results.composable_container.composable_container_base import PaneLayout


class VisualizationCfg(param.Parameterized):
    """Configuration for plotting and visualization."""

    auto_plot: bool = param.Boolean(
        True, doc=" Automatically dedeuce the best type of plot for the results."
    )

    use_holoview: bool = param.Boolean(False, doc="Use holoview for plotting")

    use_optuna: bool = param.Boolean(False, doc="show optuna plots")

    plot_size: int | None = param.Integer(default=None, doc="Sets the width and height of the plot")

    plot_width: int | None = param.Integer(
        default=None,
        doc="Sets with width of the plots, this will override the plot_size parameter",
    )

    plot_height: int | None = param.Integer(
        default=None, doc="Sets the height of the plot, this will override the plot_size parameter"
    )

    pane_layout = param.Selector(
        default=PaneLayout.grid,
        objects=list(PaneLayout),
        doc="Controls how multi-dimensional data is laid out in panel displays. "
        "'grid' uses rows/columns (default). "
        "'tabs' uses tabs for all outer dimensions. "
        "'tabs_and_grid' uses tabs for the outermost dimension and grid for inner ones.",
    )

    backend = param.Selector(
        default="panel",
        objects=["panel", "rerun"],
        doc="Visualization backend. 'panel' uses the default holoviews/panel plotting pipeline. "
        "'rerun' renders N-dimensional benchmark data in the rerun viewer.",
    )
