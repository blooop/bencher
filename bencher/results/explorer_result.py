from __future__ import annotations

import panel as pn

from bencher.results.hvplot_accessor import hvplot_of
from bencher.results.pane_result import PaneResult


class ExplorerResult(PaneResult):
    def to_plot(self, **kwargs) -> pn.pane.Pane:  # pylint: disable=unused-argument
        """Produces a hvplot explorer instance to explore the generated dataset
        see: https://hvplot.holoviz.org/getting_started/explorer.html

        Returns:
            pn.pane.Pane: A dynamic pane for exploring a dataset
        """

        if len(self.bench_cfg.input_vars) > 0:
            return hvplot_of(self.to_xarray()).explorer()

        # For some reason hvplot doesn't like 1D datasets in xarray, so convert to pandas which it has no problem with
        # TODO look into why this is, its probably due to how I am setting up the indexing in xarray.
        return hvplot_of(self.to_pandas()).explorer()
