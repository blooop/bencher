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

import numpy as np
import pandas as pd
import panel as pn
from bencher.results.bench_result import BenchResult
from bencher.bench_plot_server import BenchPlotServer
from bencher.bench_cfg import BenchRunCfg


@dataclass
class GithubPagesCfg:
    github_user: str
    repo_name: str
    folder_name: str = "report"
    branch_name: str = "gh-pages"


class BenchReport(BenchPlotServer):
    def __init__(
        self,
        bench_name: str | None = None,
    ) -> None:
        self.bench_name = bench_name
        self.pane = pn.Tabs(tabs_location="above", name=self.bench_name)
        self.last_save_ms: float = 0.0
        self.bench_results: list[BenchResult] = []

    def clear(self) -> None:
        """Remove all tabs and results so the report can be reused between runs.

        Not safe to call while the report is being served to a live Panel session.
        """
        self.pane.clear()
        self.bench_results.clear()

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

    @staticmethod
    def _time_event_label(bench_res: BenchResult) -> str | None:
        """Extract a human-readable label for the latest time event from a result."""
        if not bench_res.bench_cfg.over_time or "over_time" not in bench_res.ds.coords:
            return None
        time_vals = bench_res.ds.coords["over_time"].values
        if len(time_vals) == 0:
            return None
        last = time_vals[-1]
        if isinstance(last, (np.datetime64,)):
            label = pd.Timestamp(last).strftime("%Y-%m-%d %H:%M:%S")
        else:
            label = str(last).replace("\n", " ")
        if len(label) > 60:
            label = label[:57] + "..."
        return label

    def append_result(self, bench_res: BenchResult) -> None:
        self.bench_results.append(bench_res)
        title = bench_res.bench_cfg.title
        label = self._time_event_label(bench_res)
        if label:
            title = f"{title} [{label}]"
        self.append_tab(bench_res.plot(), title)

    def append_to_result(self, bench_res: BenchResult, pane: pn.panel) -> None:
        """Append *pane* to the tab that belongs to *bench_res*."""
        try:
            idx = self.bench_results.index(bench_res)
            self.pane[idx].append(pane)
        except (ValueError, IndexError):
            self.append(pane)

    def append_tab(self, pane: pn.panel, name: str | None = None) -> None:
        if pane is not None:
            if name is None:
                name = pane.name
            self.pane.append(pn.Column(pane, name=name))
            self.pane.active = len(self.pane) - 1

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
        **kwargs,
    ) -> Path:
        """Save the result to a html file.

        When the report contains multiple tabs, each tab is saved to its own
        embedded HTML file and the index page uses iframes to display them.
        This prevents HoloMap slider widgets from colliding across tabs.

        Args:
            directory (str | Path, optional): base folder to save to. Defaults to "cachedir" which should be ignored by git.
            filename (str, optional): The name of the html file. Defaults to the name of the benchmark
            in_html_folder (bool, optional): Put the saved files in a html subfolder to help keep the results separate from source code. Defaults to True.

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
                # Save inner content directly so the Tabs sidebar is not rendered
                content = self.pane[0] if len(self.pane) == 1 else self.pane
                content.save(filename=index_path, progress=True, embed=True, **kwargs)
                return index_path

            # Save each tab to its own HTML so HoloMap sliders don't collide.
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
                pn.Column(tab).save(filename=tab_path, progress=True, embed=True, **kwargs)
                tab_files.append((tab_name, f"_tabs/{tab_file}"))

            # Generate an index page with tab buttons and an iframe.
            self._write_iframe_index(index_path, tab_files)
            logging.info(f"saving index to: {index_path.absolute()}")
            return index_path
        finally:
            self.last_save_ms = (time.perf_counter() - t0) * 1000.0
            # Propagate save timing back to bench result timings
            for br in self.bench_results:
                if br.timings is not None:
                    br.timings.report_save_ms = self.last_save_ms
                    br.timings.total_ms = br.timings.compute_total()

    @staticmethod
    def _write_iframe_index(index_path: Path, tab_files: list) -> None:
        """Write a lightweight HTML index with tab buttons and an iframe."""
        last_idx = len(tab_files) - 1
        buttons = ""
        for i, (name, path) in enumerate(tab_files):
            active = " active" if i == last_idx else ""
            escaped_name = html.escape(name)
            buttons += (
                f'<button class="tab-btn{active}" '
                f"onclick=\"switchTab(this, '{path}')\">{escaped_name}</button>\n"
            )
        first_src = tab_files[last_idx][1] if tab_files else ""
        page = f"""\
<!DOCTYPE html>
<html><head><meta charset="utf-8"><title>Report</title>
<style>
body {{ margin:0; font-family:sans-serif; }}
.tab-bar {{ display:flex; gap:4px; background:rgba(0,0,0,0.9); padding:10px; position:sticky; top:0; z-index:100; }}
.tab-btn {{ padding:10px 16px; border:none; cursor:pointer; background:rgba(255,255,255,0.15); color:#fff; font-size:14px; border-radius:4px; transition:background 0.15s ease,color 0.15s ease; }}
.tab-btn:hover {{ background:rgba(255,255,255,0.3); }}
.tab-btn:focus-visible {{ background:rgba(255,255,255,0.3); outline:2px solid #fff; outline-offset:2px; }}
.tab-btn.active {{ background:rgba(255,255,255,0.9); color:#000; font-weight:bold; }}
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
