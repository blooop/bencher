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
            "intro": ("This shows examples of what various dimensionalities of sweep look like."),
            "sections": [
                {
                    "path": "inputs_0_float",
                    "title": "0 Continuous Variables, 0-3 Categorical Variables",
                },
                {
                    "path": "inputs_1_float",
                    "title": "1 Continuous Variable, 0-3 Categorical Variables",
                },
                {
                    "path": "inputs_2_float",
                    "title": "2 Continuous Variables, 0-3 Categorical Variables",
                },
                {
                    "path": "inputs_3_float",
                    "title": "3 Continuous Variables, 0-3 Categorical Variables",
                },
                {"path": "1D", "title": "1D"},
                {"path": "pareto", "title": "Pareto"},
                {"path": "2D", "title": "2D"},
                {"path": "levels", "title": "Levels"},
                {"path": "examples", "title": "Examples"},
                {"path": "Meta", "title": "Meta"},
                {"path": "yaml", "title": "YAML"},
                {"path": "media", "title": "Media"},
            ],
            "skip_rst_notebook_directive": True,
        }
    },
}

nbsite_nbbuild_exclude_patterns = ["jupyter_execute/**"]
