# Configuration file for the Sphinx documentation builder.
#
# For the full list of built-in configuration values, see the documentation:
# https://www.sphinx-doc.org/en/master/usage/configuration.html

# -- Project information -----------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#project-information

import os
from importlib import metadata

copyright = "2025, Austin Gregg-Smith"  # pylint:disable=redefined-builtin
author = "Austin Gregg-Smith"
release = metadata.version("holobench")
project = f"bencher {release}"


# -- General configuration ---------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#general-configuration

extensions = [
    "myst_parser",
    "sphinx.ext.napoleon",
    "autoapi.extension",
    "sphinx_copybutton",
]

templates_path = ["_templates"]
exclude_patterns = ["_build", "Thumbs.db", ".DS_Store"]


# -- Options for HTML output -------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#options-for-html-output

html_theme = "sphinx_rtd_theme"
html_static_path = ["_static"]
html_css_files = ["custom.css"]

# Copy HTML reports into the build so iframes resolve (only if generated)
# Reports live in docs/_extra/reference/meta/ to mirror the built output structure
_extra_dir = os.path.join(os.path.dirname(__file__), "_extra")
html_extra_path = ["_extra"] if os.path.isdir(_extra_dir) else []

autoapi_dirs = ["../bencher"]
autoapi_ignore = ["*example_*", "*example*", "*experimental*"]
