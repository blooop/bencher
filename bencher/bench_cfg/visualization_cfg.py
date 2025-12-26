"""Configuration for benchmark visualization settings."""

from __future__ import annotations

from typing import Optional

import param


class VisualizationCfg(param.Parameterized):
    """Plotting and visualization: plot types, sizes, and rendering options."""

    auto_plot: bool = param.Boolean(
        True, doc="Automatically deduce the best type of plot for the results."
    )

    use_holoview: bool = param.Boolean(False, doc="Use holoview for plotting")

    use_optuna: bool = param.Boolean(False, doc="show optuna plots")

    render_plotly: bool = param.Boolean(
        True,
        doc="Plotly and Bokeh don't play nicely together, so by default pre-render plotly "
        "figures to a non dynamic version so that bokeh plots correctly. If you want "
        "interactive 3D graphs, set this to true but be aware that your 2D interactive "
        "graphs will probably stop working.",
    )

    raise_duplicate_exception: bool = param.Boolean(False, doc="Used to debug unique plot names.")

    plot_size: Optional[int] = param.Integer(
        default=None, doc="Sets the width and height of the plot"
    )

    plot_width: Optional[int] = param.Integer(
        default=None,
        doc="Sets with width of the plots, this will override the plot_size parameter",
    )

    plot_height: Optional[int] = param.Integer(
        default=None, doc="Sets the height of the plot, this will override the plot_size parameter"
    )
