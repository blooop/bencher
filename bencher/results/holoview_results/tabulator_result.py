from __future__ import annotations
import panel as pn

from bencher.results.holoview_results.holoview_result import HoloviewResult


class TabulatorResult(HoloviewResult):
    def to_plot(self, **kwargs) -> pn.widgets.Tabulator:  # pylint:disable=unused-argument
        """Create an interactive table visualization of the data.

        Passes the data to the panel Tabulator type to display an interactive table.
        See https://panel.holoviz.org/reference/widgets/Tabulator.html for extra options.

        Args:
            **kwargs: Additional parameters to pass to the Tabulator constructor.

        Returns:
            pn.widgets.Tabulator: An interactive table widget.
        """
        return pn.widgets.Tabulator(self.to_pandas())
