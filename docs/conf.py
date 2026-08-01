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
    "sphinxcontrib.mermaid",
]

templates_path = ["_templates"]
exclude_patterns = ["_build", "Thumbs.db", ".DS_Store"]

# Generate anchors for headings h1-h4 in markdown pages so that intra- and
# cross-page links of the form `[text](page.md#some-heading)` resolve. Without
# this myst emits no heading ids at all and every such link is a broken
# reference.
myst_heading_anchors = 4

# Markdown pages that are documentation *for the docs build* and are reachable
# from the index toctree:
#   how_to_use_bencher, intro, concepts, caching, over_time, examples_index,
#   scorecard
# `plot_plugin_design` is a design document kept in-tree but deliberately not
# linked from the toctree.


# -- Options for HTML output -------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#options-for-html-output

html_theme = "sphinx_rtd_theme"
html_static_path = ["_static"]
html_css_files = ["custom.css"]
html_js_files = ["bencher-embed.js"]

# Copy HTML reports and thumbnails into the build (only if generated)
# Reports live in docs/_extra/reference/meta/ to mirror the built output structure
_extra_dir = os.path.join(os.path.dirname(__file__), "_extra")
html_extra_path = ["_extra"] if os.path.isdir(_extra_dir) else []

autoapi_dirs = ["../bencher"]
autoapi_ignore = ["*example_*", "*example*", "*experimental*"]
