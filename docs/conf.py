# Configuration file for the Sphinx documentation builder.
#
# For the full list of built-in configuration values, see the documentation:
# https://www.sphinx-doc.org/en/master/usage/configuration.html

# -- Project information -----------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#project-information


from importlib import metadata
from nbsite.shared_conf import *  # noqa

copyright = "2025, Austin Gregg-Smith"  # pylint:disable=redefined-builtin
author = "Austin Gregg-Smith"
release = metadata.version("holobench")
project = f"bencher {release}"


# -- General configuration ---------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#general-configuration

extensions += [  # noqa
    "sphinx.ext.napoleon",
    "autoapi.extension",
    "nbsite.gallery",
    "sphinx_copybutton",
]

templates_path = ["_templates"]
exclude_patterns = ["_build", "Thumbs.db", ".DS_Store"]


# -- Options for HTML output -------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#options-for-html-output

# html_theme = "pydata_sphinx_theme"
html_theme = "sphinx_rtd_theme"
# html_theme_options = {
#     "sticky_navigation": True,  # Keeps the sidebar static while scrolling
# }
html_static_path = ["_static"]
html_css_files = ["custom.css"]

autoapi_dirs = ["../bencher"]
autoapi_ignore = ["*example_*", "*example*", "*experimental*"]


numpydoc_show_class_members = False

autosummary_generate = True

nbsite_gallery_conf = {
    "default_extensions": ["*.ipynb", "*.py"],
    "examples_dir": ".",
    "galleries": {
        "reference": {
            "title": "Reference Gallery",
            "intro": "This shows examples of what various dimensionalities of sweep look like.",
            "sections": [
                {"path": "meta/0_float/no_repeats", "title": "0 Float - No Repeats"},
                {"path": "meta/0_float/with_repeats", "title": "0 Float - With Repeats"},
                {"path": "meta/0_float/over_time", "title": "0 Float - Over Time"},
                {"path": "meta/1_float/no_repeats", "title": "1 Float - No Repeats"},
                {"path": "meta/1_float/with_repeats", "title": "1 Float - With Repeats"},
                {"path": "meta/1_float/over_time", "title": "1 Float - Over Time"},
                {"path": "meta/2_float/no_repeats", "title": "2 Float - No Repeats"},
                {"path": "meta/2_float/with_repeats", "title": "2 Float - With Repeats"},
                {"path": "meta/2_float/over_time", "title": "2 Float - Over Time"},
                {"path": "meta/3_float/no_repeats", "title": "3 Float - No Repeats"},
                {"path": "meta/3_float/with_repeats", "title": "3 Float - With Repeats"},
                {"path": "meta/3_float/over_time", "title": "3 Float - Over Time"},
                {"path": "levels", "title": "Levels"},
                {"path": "pareto", "title": "Pareto"},
                {"path": "yaml", "title": "YAML"},
            ],
            "skip_rst_notebook_directive": True,
        }
    },
}

nbsite_nbbuild_exclude_patterns = ["jupyter_execute/**"]
