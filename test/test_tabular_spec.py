"""Tests for the intra-sample chart machinery (holoview_results/tabular_spec.py).

The column helpers are exercised in depth through the charts built on them (see
test_xy_scatter_result.py); what is tested here is the base contract every chart
inherits, so a new chart gets it for free and cannot quietly lose it.
"""

import pickle
import unittest
from dataclasses import FrozenInstanceError, dataclass
from typing import ClassVar

import holoviews as hv
import pandas as pd
import pytest
import xarray as xr

from bencher.results.holoview_results.tabular_spec import (
    TabularSpec,
    check_column,
    plot_frame,
    resolve_axes,
    to_dataframe,
)


@dataclass(frozen=True)
class _Probe(TabularSpec):
    """A minimal chart: the smallest thing a subclass has to provide."""

    chart_name: ClassVar[str] = "probe_chart"

    x: str | None = None
    y: str | None = None

    def build(self, df) -> hv.Curve:
        x_col, y_col = self.axes(df, self.x, self.y)
        plot_df, names = self.frame(df, [x_col, y_col])
        return hv.Curve(plot_df, kdims=[names[x_col]], vdims=[names[y_col]]).opts(
            **self.element_opts(xlabel=names[x_col], ylabel=names[y_col])
        )


def frame() -> pd.DataFrame:
    return pd.DataFrame({"a": [1.0, 2.0], "b": [3.0, 4.0], "label": ["p", "q"]})


def plot_opts(element) -> dict:
    return hv.Store.lookup_options("bokeh", element, "plot").kwargs


def style_opts(element) -> dict:
    return hv.Store.lookup_options("bokeh", element, "style").kwargs


class TestSpecContract(unittest.TestCase):
    """What a ResultDataSet container has to satisfy, provided by the base."""

    def test_called_with_the_object_alone(self):
        """The whole container contract: one positional argument, no plot kwargs."""
        assert isinstance(_Probe(x="a", y="b")(frame()), hv.Curve)

    def test_build_is_abstract(self):
        with pytest.raises(NotImplementedError):
            TabularSpec()(frame())

    def test_spec_round_trips_through_pickle(self):
        """Why a spec is a frozen dataclass: it rides in BenchCfg, which is pickled."""
        spec = _Probe(x="a", y="b", title="t", opts={"alpha": 0.5})
        restored = pickle.loads(pickle.dumps(spec))
        assert restored == spec
        assert isinstance(restored(frame()), hv.Curve)

    def test_frozen(self):
        with pytest.raises(FrozenInstanceError):
            _Probe(x="a").x = "b"


class TestElementOpts(unittest.TestCase):
    """The options every chart shares."""

    def setUp(self):
        self.df = frame()

    def test_axis_labels_default_to_the_columns(self):
        opts = plot_opts(_Probe(x="a", y="b")(self.df))
        assert (opts["xlabel"], opts["ylabel"]) == ("a", "b")

    def test_axis_labels_can_be_overridden(self):
        opts = plot_opts(_Probe(x="a", y="b", xlabel="A [m]", ylabel="B [s]")(self.df))
        assert (opts["xlabel"], opts["ylabel"]) == ("A [m]", "B [s]")

    def test_title_is_opt_in(self):
        assert "title" not in plot_opts(_Probe(x="a", y="b")(self.df))
        assert plot_opts(_Probe(x="a", y="b", title="T")(self.df))["title"] == "T"

    def test_data_aspect_is_opt_in(self):
        assert "data_aspect" not in plot_opts(_Probe(x="a", y="b")(self.df))
        assert plot_opts(_Probe(x="a", y="b", data_aspect=1)(self.df))["data_aspect"] == 1

    def test_hover_on_by_default_and_disablable(self):
        """hover=False has to set tools empty, not omit it.

        set_default_opts registers tools=["hover"] globally for most element types,
        so an omitted key would put hover back and make the option a no-op.
        """
        assert plot_opts(_Probe(x="a", y="b")(self.df))["tools"] == ["hover"]
        assert plot_opts(_Probe(x="a", y="b", hover=False)(self.df))["tools"] == []

    def test_passthrough_opts_reach_holoviews(self):
        element = _Probe(x="a", y="b", opts={"alpha": 0.25})(self.df)
        assert style_opts(element)["alpha"] == 0.25

    def test_passthrough_opts_mapping_is_not_mutated(self):
        extra_opts = {"alpha": 0.25}
        element = _Probe(x="a", y="b", opts=extra_opts)(self.df)
        style_opts(element)
        assert extra_opts == {"alpha": 0.25}

    def test_passthrough_opts_win_over_the_defaults(self):
        """``**opts`` is the escape hatch, so it is applied last."""
        element = _Probe(x="a", y="b", opts={"xlabel": "override"})(self.df)
        assert plot_opts(element)["xlabel"] == "override"


class TestSharedHelpers(unittest.TestCase):
    """The pieces every chart's build() draws on, named by the chart that failed."""

    def setUp(self):
        self.df = frame()

    def test_errors_name_the_chart(self):
        """A chart-agnostic helper must still say which chart rejected the column."""
        with pytest.raises(ValueError, match="y='nope' is not a column of the result") as ctx:
            _Probe(x="a", y="nope")(self.df)
        assert "probe_chart" in str(ctx.value)

    def test_dataframe_passes_through_unchanged(self):
        assert to_dataframe(self.df, "c") is self.df

    def test_xarray_dimension_coords_become_columns(self):
        ds = xr.Dataset({"b": ("a", [1.0, 2.0])}, coords={"a": [0.0, 1.0]})
        assert sorted(to_dataframe(ds, "c").columns) == ["a", "b"]

    def test_hv_dataset_accepted(self):
        assert len(to_dataframe(hv.Dataset(self.df), "c")) == 2

    def test_non_table_names_the_chart_and_the_type(self):
        with pytest.raises(TypeError) as ctx:
            to_dataframe([1, 2, 3], "probe_chart")
        assert "probe_chart" in str(ctx.value)
        assert "list" in str(ctx.value)

    def test_check_column_reports_what_is_available(self):
        with pytest.raises(ValueError, match="x='nope' is not a column of the result") as ctx:
            check_column(self.df, "nope", "x", "c")
        assert "'a'" in str(ctx.value)

    def test_axes_inferred_skip_non_numeric_columns(self):
        assert resolve_axes(self.df, None, None, "c") == ("a", "b")

    def test_plot_frame_keeps_only_the_plotted_columns(self):
        plot_df, names = plot_frame(self.df, ["a", "b"], "c")
        assert list(plot_df.columns) == ["a", "b"]
        assert names == {"a": "a", "b": "b"}

    def test_plot_frame_does_not_mutate_the_stored_frame(self):
        """A sample's table is rendered repeatedly; renaming must not touch it."""
        df = pd.DataFrame({0: [1.0], 1: [2.0]})
        plot_frame(df, [0, 1], "c")
        assert list(df.columns) == [0, 1]


class TestValueColumns(unittest.TestCase):
    """vdims plus the columns a chart option implies, without duplicates."""

    def setUp(self):
        self.spec = _Probe()
        self.df = frame()

    def test_extra_appended(self):
        assert self.spec.value_columns(self.df, ["a"], "b") == ["a", "b"]

    def test_extra_already_present_is_not_duplicated(self):
        assert self.spec.value_columns(self.df, ["a", "b"], "b") == ["a", "b"]

    def test_none_extra_ignored(self):
        assert self.spec.value_columns(self.df, ["a"], None) == ["a"]

    def test_unknown_vdim_raises(self):
        with pytest.raises(ValueError, match="vdims entry='nope' is not a column of the result"):
            self.spec.value_columns(self.df, ["nope"])

    def test_unknown_extra_raises_before_the_frame_is_built(self):
        """An unchecked extra would reach frame() and raise a bare pandas KeyError."""
        with pytest.raises(
            ValueError, match="value column='nope' is not a column of the result"
        ) as ctx:
            self.spec.value_columns(self.df, ["a"], "nope")
        assert "probe_chart" in str(ctx.value)
        assert "'a'" in str(ctx.value), "the error should list the available columns"


if __name__ == "__main__":
    unittest.main()
