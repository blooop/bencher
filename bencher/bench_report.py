from __future__ import annotations

import html
import logging
import time
from typing import Callable
import os
from pathlib import Path
import tempfile
from threading import Thread
from dataclasses import dataclass

import panel as pn
import plotly.graph_objects as go
import plotly.io as pio
from bencher.results.bench_result import BenchResult
from bencher.bench_plot_server import BenchPlotServer
from bencher.bench_cfg import BenchRunCfg


@dataclass
class GithubPagesCfg:
    github_user: str
    repo_name: str
    folder_name: str = "report"
    branch_name: str = "gh-pages"


def _extract_plotly_figures(pane) -> list[go.Figure]:
    """Recursively extract all Plotly figures from a Panel pane tree."""
    figures = []
    if isinstance(pane, pn.pane.Plotly):
        obj = pane.object
        if isinstance(obj, go.Figure):
            figures.append(obj)
        elif isinstance(obj, dict):
            figures.append(go.Figure(obj))
    elif isinstance(pane, go.Figure):
        figures.append(pane)
    elif hasattr(pane, "__iter__"):
        for child in pane:
            figures.extend(_extract_plotly_figures(child))
    elif hasattr(pane, "objects"):
        for child in pane.objects:
            figures.extend(_extract_plotly_figures(child))
    elif hasattr(pane, "object"):
        obj = pane.object
        if isinstance(obj, go.Figure):
            figures.append(obj)
        elif isinstance(obj, dict):
            try:
                figures.append(go.Figure(obj))
            except (ValueError, TypeError):
                pass
    return figures


def _extract_markdown(pane) -> list[str]:
    """Recursively extract Markdown text from a Panel pane tree."""
    texts = []
    if isinstance(pane, pn.pane.Markdown):
        texts.append(pane.object or "")
    elif hasattr(pane, "__iter__"):
        for child in pane:
            texts.extend(_extract_markdown(child))
    elif hasattr(pane, "objects"):
        for child in pane.objects:
            texts.extend(_extract_markdown(child))
    return texts


def _save_tab_plotly(pane, filepath: Path) -> None:
    """Save a single tab's content as a standalone Plotly HTML file.

    Extracts all Plotly figures and markdown from the pane tree and
    writes them into a single HTML file using plotly.io.
    """
    figures = _extract_plotly_figures(pane)
    markdowns = _extract_markdown(pane)

    if not figures and not markdowns:
        # Fallback: try Panel save (for non-Plotly content like images/videos)
        try:
            pn.Column(pane).save(filename=filepath, progress=False, embed=True)
            return
        except (ValueError, TypeError, OSError):
            with open(filepath, "w", encoding="utf-8") as f:
                f.write("<html><body><p>No content</p></body></html>")
            return

    # Build a combined HTML page with all figures
    html_parts = [
        '<!DOCTYPE html><html><head><meta charset="utf-8">',
        '<script src="https://cdn.plot.ly/plotly-latest.min.js"></script>',
        "<style>body{font-family:sans-serif;margin:20px;}"
        ".plotly-graph-div{margin-bottom:20px;}</style>",
        "</head><body>",
    ]

    for md in markdowns:
        # Simple markdown-to-HTML: just wrap in a div
        escaped = html.escape(md).replace("\n", "<br>")
        html_parts.append(f"<div>{escaped}</div>")

    for i, fig in enumerate(figures):
        div_html = pio.to_html(
            fig,
            full_html=False,
            include_plotlyjs=("cdn" if i == 0 else False),
            config={"responsive": True},
        )
        html_parts.append(div_html)

    html_parts.append("</body></html>")

    with open(filepath, "w", encoding="utf-8") as f:
        f.write("\n".join(html_parts))


class BenchReport(BenchPlotServer):
    def __init__(
        self,
        bench_name: str | None = None,
    ) -> None:
        self.bench_name = bench_name
        self.pane = pn.Tabs(tabs_location="left", name=self.bench_name)
        self.last_save_ms: float = 0.0

    def append_title(self, title: str, new_tab: bool = True):
        if new_tab:
            return self.append_tab(pn.pane.Markdown(f"# {title}", name=title), title)
        return self.append_markdown(f"# {title}", title)

    def append_markdown(
        self, markdown: str, name: str | None = None, width: int = 800, **kwargs
    ) -> pn.pane.Markdown:
        if name is None:
            name = markdown
        md = pn.pane.Markdown(markdown, name=name, width=width, **kwargs)
        self.append(md, name)
        return md

    def append(self, pane: pn.panel, name: str | None = None) -> None:
        if len(self.pane) == 0:
            if name is None:
                name = pane.name
            self.append_tab(pane, name)
        else:
            self.pane[-1].append(pane)

    def append_col(self, pane: pn.panel, name: str | None = None) -> None:
        if name is not None:
            col = pn.Column(pane, name=name)
        else:
            col = pn.Column(pane, name=pane.name)
        self.pane.append(col)

    def append_result(self, bench_res: BenchResult) -> None:
        self.append_tab(bench_res.plot(), bench_res.bench_cfg.title)

    def append_tab(self, pane: pn.panel, name: str | None = None) -> None:
        if pane is not None:
            if name is None:
                name = pane.name
            self.pane.append(pn.Column(pane, name=name))

    def save_index(self, directory: str = "", filename: str = "index.html") -> Path:
        """Saves the result to index.html in the root folder so that it can be displayed by github pages.

        Returns:
            Path: save path
        """
        return self.save(directory, filename, False)

    def save(
        self,
        directory: str | Path = "cachedir",
        filename: str | None = None,
        in_html_folder: bool = True,
        **_kwargs,
    ) -> Path:
        """Save the result to an HTML file.

        Uses fast Plotly-native HTML serialization instead of Panel's
        embed pipeline, eliminating the slow HoloMap state pre-computation
        that was the primary performance bottleneck.

        Args:
            directory: base folder to save to.
            filename: The name of the html file.
            in_html_folder: Put saved files in a html subfolder.

        Returns:
            Path: the save path
        """

        t0 = time.perf_counter()
        try:
            if filename is None:
                filename = f"{self.bench_name}.html"

            base_path = Path(directory)

            if in_html_folder:
                base_path /= "html"

            logging.info(f"creating dir {base_path.absolute()}")
            os.makedirs(base_path.absolute(), exist_ok=True)

            index_path = base_path / filename

            if len(self.pane) <= 1:
                logging.info(f"saving html output to: {index_path.absolute()}")
                content = self.pane[0] if len(self.pane) == 1 else self.pane
                _save_tab_plotly(content, index_path)
                return index_path

            # Save each tab to its own HTML file
            tab_dir = base_path / "_tabs"
            os.makedirs(tab_dir, exist_ok=True)
            tab_files = []
            seen_names = set()
            for i, tab in enumerate(self.pane):
                tab_name = getattr(tab, "name", None) or f"tab_{i}"
                safe_name = "".join(c if c.isalnum() or c in "-_" else "_" for c in tab_name)
                if safe_name in seen_names:
                    safe_name = f"{safe_name}_{i}"
                seen_names.add(safe_name)
                tab_file = f"{safe_name}.html"
                tab_path = tab_dir / tab_file
                logging.info(f"saving tab '{tab_name}' to: {tab_path.absolute()}")
                _save_tab_plotly(tab, tab_path)
                tab_files.append((tab_name, f"_tabs/{tab_file}"))

            # Generate an index page with tab buttons and an iframe.
            self._write_iframe_index(index_path, tab_files)
            logging.info(f"saving index to: {index_path.absolute()}")
            return index_path
        finally:
            self.last_save_ms = (time.perf_counter() - t0) * 1000.0

    @staticmethod
    def _write_iframe_index(index_path: Path, tab_files: list) -> None:
        """Write a lightweight HTML index with tab buttons and an iframe."""
        buttons = ""
        for i, (name, path) in enumerate(tab_files):
            active = " active" if i == 0 else ""
            escaped_name = html.escape(name)
            buttons += (
                f'<button class="tab-btn{active}" '
                f"onclick=\"switchTab(this, '{path}')\">{escaped_name}</button>\n"
            )
        first_src = tab_files[0][1] if tab_files else ""
        page = f"""\
<!DOCTYPE html>
<html><head><meta charset="utf-8"><title>Report</title>
<style>
body {{ margin:0; font-family:sans-serif; }}
.tab-bar {{ display:flex; gap:2px; background:#e0e0e0; padding:4px; }}
.tab-btn {{ padding:8px 16px; border:none; cursor:pointer; background:#ccc; font-size:14px; }}
.tab-btn.active {{ background:#fff; font-weight:bold; }}
iframe {{ width:100%; border:none; }}
</style></head><body>
<div class="tab-bar">{buttons}</div>
<iframe id="content" src="{first_src}"></iframe>
<script>
function switchTab(btn, src) {{
  document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
  btn.classList.add('active');
  document.getElementById('content').src = src;
}}
function resizeIframe() {{
  var f = document.getElementById('content');
  f.style.height = (window.innerHeight - f.getBoundingClientRect().top) + 'px';
}}
window.addEventListener('resize', resizeIframe);
document.getElementById('content').addEventListener('load', resizeIframe);
resizeIframe();
</script></body></html>"""
        with open(index_path, "w", encoding="utf-8") as f:
            f.write(page)

    def show(self, run_cfg: BenchRunCfg | None = None) -> Thread:  # pragma: no cover
        """Launches a webserver with plots of the benchmark results, blocking

        Args:
            run_cfg (BenchRunCfg, optional): Options for the webserve such as the port. Defaults to None.

        """
        if run_cfg is None:
            run_cfg = BenchRunCfg()

        bench_name = self.bench_name or ""
        return BenchPlotServer().plot_server(bench_name, run_cfg, self.pane)

    def publish_gh_pages(
        self,
        github_user: str,
        repo_name: str,
        folder_name: str = "report",
        branch_name: str = "gh-pages",
    ) -> str:  # pragma: no cover
        remote = f"https://github.com/{github_user}/{repo_name}.git"
        publish_url = f"https://{github_user}.github.io/{repo_name}/{folder_name}"

        with tempfile.TemporaryDirectory() as td:
            directory = td
            report_path = self.save(
                directory + f"/{folder_name}/",
                filename="index.html",
                in_html_folder=False,
            )
            logging.info(f"created report at: {report_path.absolute()}")

            cd_dir = f"cd {directory} &&"
            # TODO DON'T OVERWRITE EVERYTHING
            os.system(f"{cd_dir} git init")
            os.system(f"{cd_dir} git checkout -b {branch_name}")
            os.system(f"{cd_dir} git add {folder_name}/index.html")
            os.system(f'{cd_dir} git commit -m "publish {branch_name}"')
            os.system(f"{cd_dir} git remote add origin {remote}")
            os.system(f"{cd_dir} git push --set-upstream origin {branch_name} -f")

        logging.info("Published report @")
        logging.info(publish_url)

        return publish_url

    def publish(
        self, remote_callback: Callable, branch_name: str | None = None, debug: bool = False
    ) -> str:  # pragma: no cover
        """Publish the results as an html file by committing it to the bench_results branch in the current repo. If you have set up your repo with github pages or equivalent then the html file will be served as a viewable webpage.  This is an example of a callable to publish on github pages:

        .. code-block:: python

            def publish_args(branch_name) -> tuple[str, str]:
                return (
                    "https://github.com/blooop/bencher.git",
                    f"https://github.com/blooop/bencher/blob/{branch_name}")


        Args:
            remote (Callable): A function the returns a tuple of the publishing urls. It must follow the signature def publish_args(branch_name) -> tuple[str, str].  The first url is the git repo name, the second url needs to match the format for viewable html pages on your git provider.  The second url can use the argument branch_name to point to the report on a specified branch.

        Returns:
            str: the url of the published report
        """

        if branch_name is None:
            branch_name = self.bench_name
        branch_name += "_debug" if debug else ""

        remote, publish_url = remote_callback(branch_name)

        with tempfile.TemporaryDirectory() as td:
            directory = td
            report_path = self.save(directory, filename="index.html", in_html_folder=False)
            logging.info(f"created report at: {report_path.absolute()}")

            cd_dir = f"cd {directory} &&"

            os.system(f"{cd_dir} git init")
            os.system(f"{cd_dir} git checkout -b {branch_name}")
            os.system(f"{cd_dir} git add index.html")
            os.system(f'{cd_dir} git commit -m "publish {branch_name}"')
            os.system(f"{cd_dir} git remote add origin {remote}")
            os.system(f"{cd_dir} git push --set-upstream origin {branch_name} -f")

        logging.info("Published report @")
        logging.info(publish_url)

        return publish_url
