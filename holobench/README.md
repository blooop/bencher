# holobench

Bencher: sweep the inputs of any function, record its results in N-D xarray datasets, and
get interactive reports, claims, and before/after evidence.

`pip install holobench` installs everything: the `bencher` package (shipped as
`holobench-core`) together with the plotting, report-server, optimisation and video
packages.

For only sweeps, claims, `bencher compare` and `bencher ab` — no Panel, Bokeh, HoloViews,
hvplot, Optuna, moviepy, scikit-learn or plotly — install `holobench-core` instead.

Documentation: https://bencher.readthedocs.io/en/latest/ · Source: https://github.com/blooop/bencher
