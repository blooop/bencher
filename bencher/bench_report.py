from __future__ import annotations

import html
import logging
import os
import subprocess
import tempfile
import time
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from threading import Thread
from typing import Protocol, runtime_checkable

import numpy as np
import pandas as pd
import panel as pn

from bencher.bench_cfg import BenchRunCfg
from bencher.bench_plot_server import BenchPlotServer
from bencher.blob_store import DEFAULT_CACHE_DIR
from bencher.results.bench_result import BenchResult

logger = logging.getLogger(__name__)


def _inline_rrd(
    html_path: Path,
    rrd_base: Path | None = None,
    portable: bool = False,
) -> None:
    """Rewrite .rrd viewer iframes in a saved HTML report for static hosting.

    By default copies .rrd files as sidecars (fast, works on any HTTP server).
    With ``portable=True``, base64-encodes the data into the viewer HTML so
    the report works from ``file://`` without a server.
    """
    try:
        from bencher.utils_rrd import inline_rrd_iframes

        inline_rrd_iframes(html_path, rrd_base=rrd_base, portable=portable)
    except Exception:  # pylint: disable=broad-except
        logger.warning("inline_rrd_iframes failed for %s", html_path, exc_info=True)


# Injected into every saved report so that, when embedded in an iframe, the
# document measures itself and posts its height to the parent. The parent
# (docs page or multi-tab index) just sets the iframe height it receives, so
# the page keeps a single scrollbar. Standalone viewing is untouched.
_EMBED_HEIGHT_SCRIPT = """
<script>
/* bencher:height embed reporter */
(function () {
  "use strict";
  if (window.parent === window) return; /* standalone page: leave it alone */
  function report() {
    var de = document.documentElement;
    var body = document.body;
    if (!body) return;
    /* Content keeps its natural scale; the embedder is told the full size and
       provides horizontal scrolling when the content is wider than the page. */
    var h = Math.max(de.scrollHeight, body.scrollHeight);
    var w = Math.max(de.scrollWidth, body.scrollWidth);
    if (h > 0) {
      window.parent.postMessage({ type: "bencher:height", height: h, width: w }, "*");
    }
  }
  function init() {
    var de = document.documentElement;
    var body = document.body;
    /* Panel pins html/body to height:100%, which hides content growth from
       ResizeObserver; un-pin so the document takes its natural height. */
    de.style.height = "auto";
    body.style.height = "auto";
    /* The embedder sizes the iframe to the posted width/height, so this
       document never needs its own scrollbars. */
    de.style.overflow = "hidden";
    body.style.overflow = "hidden";
    new ResizeObserver(report).observe(body);
    new ResizeObserver(report).observe(de);
    report();
    /* Fallbacks for content that changes size without resizing body
       (absolutely positioned overlays). */
    setTimeout(report, 1000);
    setTimeout(report, 3000);
  }
  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
  window.addEventListener("load", report);
})();
</script>
"""


def _inject_embed_script(html_path: Path) -> None:
    """Append the self-measuring embed script to a saved report HTML file.

    Idempotent: skips files that already contain the reporter.
    """
    try:
        content = html_path.read_text(encoding="utf-8")
        if "bencher:height embed reporter" in content:
            return
        for anchor in ("</body>", "</html>"):
            if anchor in content:
                content = content.replace(anchor, _EMBED_HEIGHT_SCRIPT + anchor, 1)
                break
        else:
            content += _EMBED_HEIGHT_SCRIPT
        html_path.write_text(content, encoding="utf-8")
    except Exception:  # pylint: disable=broad-except
        logger.warning("inject_embed_script failed for %s", html_path, exc_info=True)


@runtime_checkable
class Publisher(Protocol):
    """Generic publisher protocol for benchmark reports.

    Any object with a ``publish(report)`` method satisfies this protocol.
    Downstream projects implement their own publishers (GCS, S3, etc.)
    without modifying bencher.
    """

    def publish(self, report: BenchReport) -> str | None:
        """Publish a report. Returns the published URL, or None."""
        ...  # pylint: disable=unnecessary-ellipsis


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
        # Each result is stored together with the tab that was created for it
        # (None when its plot() produced nothing), so tab routing can never
        # resolve into a *different* result's tab (plan 23 C9). The previous
        # representation — two parallel lists correlated by index — silently
        # misrouted once a None plot desynced them.
        self._result_tabs: list[tuple[BenchResult, pn.Column | None]] = []

    @property
    def bench_results(self) -> tuple[BenchResult, ...]:
        """The results registered via :meth:`append_result`, in registration order.

        Read-only snapshot: register results through :meth:`append_result` so each
        one is paired with its tab. (A mutable list here would make direct appends
        a silent no-op — a tuple fails loudly instead.)
        """
        return tuple(res for res, _tab in self._result_tabs)

    def clear(self) -> None:
        """Remove all tabs and results so the report can be reused between runs.

        Not safe to call while the report is being served to a live Panel session.
        """
        self.pane.clear()
        self._result_tabs.clear()

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
        if not bench_res.bench_cfg.time.over_time or "over_time" not in bench_res.ds.coords:
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

    def append_result(self, bench_res: BenchResult, render_from: BenchResult | None = None) -> None:
        title = bench_res.bench_cfg.title
        label = self._time_event_label(bench_res)
        if label:
            title = f"{title} [{label}]"
        # render_from lets callers register one result for identity-based tab
        # routing (append_to_result) while building the pane from another — used
        # by the BENCHER_FORCE_SPLIT_RENDER path to render from a deserialized
        # copy without breaking routing. Defaults to bench_res (normal path).
        tab = self.append_tab((render_from or bench_res).plot(), title)
        self._result_tabs.append((bench_res, tab))

    def _tab_for_result(self, bench_res: BenchResult) -> pn.Column | None:
        """The tab created for *bench_res*, or None when untracked / plot() was None."""
        for res, tab in self._result_tabs:
            if res is bench_res:
                return tab
        return None

    @staticmethod
    def _result_title(bench_res: BenchResult) -> str:
        """Best-effort human title for *bench_res*, for attributing a fallback pane."""
        cfg = getattr(bench_res, "bench_cfg", None)
        return getattr(cfg, "title", None) or getattr(bench_res, "title", None) or "unknown sweep"

    def _append_unattributed(self, bench_res: BenchResult, pane: pn.panel) -> None:
        """Fallback for a result with no tab of its own: append to the last tab.

        The pane lands under a *different* result's heading, so it is labelled
        with its true owner and a warning is emitted. A silently misattributed
        pane is worse than a missing one — a reader would otherwise credit this
        content (a regression verdict, say) to the sweep whose tab it sits in.
        """
        title = self._result_title(bench_res)
        logger.warning(
            "No tab for result %r (its plot() produced nothing, or it was never "
            "registered via append_result); appending its content to the last tab "
            "instead, labelled with its origin",
            title,
        )
        self.append(
            pn.pane.Markdown(
                f"**⚠️ From `{title}`** — this sweep produced no tab of its own, "
                "so its content appears here. It does **not** belong to the sweep "
                "above.",
                name=f"{title} (no tab)",
            )
        )
        self.append(pane)

    def append_to_result(self, bench_res: BenchResult, pane: pn.panel) -> None:
        """Append *pane* to the tab that belongs to *bench_res*.

        Falls back to the last tab when the result is untracked or its plot()
        produced no tab; the fallback labels the pane with its true owner (see
        :meth:`_append_unattributed`).
        """
        tab = self._tab_for_result(bench_res)
        if tab is None:
            self._append_unattributed(bench_res, pane)
        else:
            tab.append(pane)

    def prepend_to_result(self, bench_res: BenchResult, pane: pn.panel) -> None:
        """Insert *pane* at the beginning of the tab that belongs to *bench_res*.

        Falls back to the last tab when the result is untracked or its plot()
        produced no tab; the fallback labels the pane with its true owner (see
        :meth:`_append_unattributed`).
        """
        tab = self._tab_for_result(bench_res)
        if tab is None:
            self._append_unattributed(bench_res, pane)
        else:
            tab.insert(0, pane)

    def append_tab(self, pane: pn.panel, name: str | None = None) -> pn.Column | None:
        """Add *pane* as a new tab and return the created tab column (None if no pane)."""
        if pane is None:
            return None
        if name is None:
            name = pane.name
        tab = pn.Column(pane, name=name)
        self.pane.append(tab)
        self.pane.active = len(self.pane) - 1
        return tab

    def save_index(self, directory: str = "", filename: str = "index.html") -> Path:
        """Saves the result to index.html in the root folder so that it can be displayed by github pages.

        Returns:
            Path: save path
        """
        return self.save(directory, filename, False)

    def save(
        self,
        directory: str | Path = DEFAULT_CACHE_DIR,
        filename: str | None = None,
        in_html_folder: bool = True,
        portable: bool = False,
        emit_json: bool | str = False,
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
            emit_json (bool | str, optional): When truthy, also write a
                machine-readable ``result.json`` (see
                :func:`bencher.report_export.result_to_dict`) next to the HTML
                for each contained result. A string sets the filename when the
                report holds a single result. Defaults to False (no JSON).
            portable (bool, optional): When True, base64-encode .rrd data
                directly into the viewer HTML so the report works from
                ``file://`` without any server.  When False (default), .rrd
                files are copied as sidecar files and loaded via relative
                URLs — the report must be served over HTTP.

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

            logger.info(f"creating dir {base_path.absolute()}")
            os.makedirs(base_path.absolute(), exist_ok=True)

            index_path = base_path / filename

            if emit_json:
                self._emit_json(base_path, emit_json)

            if len(self.pane) <= 1:
                logger.info(f"saving html output to: {index_path.absolute()}")
                # Save inner content directly so the Tabs sidebar is not rendered
                content = self.pane[0] if len(self.pane) == 1 else self.pane
                content.save(filename=index_path, progress=True, embed=True, **kwargs)
                _inline_rrd(index_path, portable=portable)
                _inject_embed_script(index_path)
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
                logger.info(f"saving tab '{tab_name}' to: {tab_path.absolute()}")
                pn.Column(tab).save(filename=tab_path, progress=True, embed=True, **kwargs)
                _inline_rrd(tab_path, rrd_base=base_path, portable=portable)
                _inject_embed_script(tab_path)
                tab_files.append((tab_name, f"_tabs/{tab_file}"))

            # Generate an index page with tab buttons and an iframe.
            self._write_iframe_index(index_path, tab_files)
            logger.info(f"saving index to: {index_path.absolute()}")
            return index_path
        finally:
            self.last_save_ms = (time.perf_counter() - t0) * 1000.0
            # Propagate save timing back to bench result timings
            for br in self.bench_results:
                if br.timings is not None:
                    br.timings.report_save_ms = self.last_save_ms
                    br.timings.total_ms = br.timings.compute_total()

    def _emit_json(self, base_path: Path, emit_json: bool | str) -> None:
        """Write a machine-readable result.json for each contained result.

        A string ``emit_json`` sets the filename when there is exactly one
        result; with multiple results each is named ``<bench_name>.result.json``
        so they do not collide.
        """
        from bencher.report_export import result_to_json

        results = self.bench_results
        single_name = emit_json if isinstance(emit_json, str) else "result.json"
        for br in results:
            if len(results) == 1:
                name = single_name
            else:
                safe = "".join(
                    c if c.isalnum() or c in "-_" else "_"
                    for c in (br.bench_cfg.bench_name or "result")
                )
                name = f"{safe}.result.json"
            result_to_json(br, base_path / name)

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
        # Each tab document carries the bencher:height reporter (see
        # _inject_embed_script) and posts its height here; this index sizes the
        # inner iframe to match and, when itself embedded, relays the total
        # height (tab bar + content) to its own parent. Opened standalone, the
        # page scrolls natively and the sticky tab bar stays visible.
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
iframe {{ width:100%; border:none; display:block; min-height:400px; }}
</style></head><body>
<div class="tab-bar">{buttons}</div>
<iframe id="content" src="{first_src}" scrolling="no" allowfullscreen></iframe>
<script>
var _content = document.getElementById('content');
var _embedded = window.parent !== window;
function switchTab(btn, src) {{
  document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
  btn.classList.add('active');
  _content.style.height = '';  /* drop stale height; new tab re-posts on load */
  _content.src = src;
}}
window.addEventListener('message', function (e) {{
  if (!e.data || e.data.type !== 'bencher:height') return;
  if (e.source !== _content.contentWindow) return;
  _content.style.height = e.data.height + 'px';
  var w = Number(e.data.width) || 0;
  /* Keep natural scale: grow the inner iframe to the content's full width and
     let the embedder (or this page when standalone) scroll horizontally. */
  _content.style.width = w > document.documentElement.clientWidth ? w + 'px' : '';
  if (_embedded) {{
    var bar = document.querySelector('.tab-bar');
    window.parent.postMessage(
      {{ type: 'bencher:height',
         height: e.data.height + (bar ? bar.offsetHeight : 0),
         width: w }}, '*');
  }}
}});
if (_embedded) {{
  document.documentElement.style.overflow = 'hidden';
  document.body.style.overflow = 'hidden';
}}
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
            logger.info(f"created report at: {report_path.absolute()}")

            def git(*args: str) -> None:
                subprocess.run(["git", *args], cwd=directory, check=True)

            # TODO DON'T OVERWRITE EVERYTHING
            git("init")
            git("checkout", "-b", branch_name)
            git("add", f"{folder_name}/index.html")
            git("commit", "-m", f"publish {branch_name}")
            git("remote", "add", "origin", remote)
            git("push", "--set-upstream", "origin", branch_name, "-f")

        logger.info("Published report @")
        logger.info(publish_url)

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
            if self.bench_name is None:
                # Previously this fell through to `None += "_debug" if debug else ""`, so
                # publishing an unnamed report died with `TypeError: unsupported operand
                # type(s) for +=: 'NoneType' and 'str'` -- on *both* debug settings, since
                # `None += ""` raises too. Name the missing input instead.
                raise ValueError(
                    "publish() has no branch name to push to: pass branch_name= explicitly, "
                    "or construct BenchReport(bench_name=...) so the report has a name."
                )
            branch_name = self.bench_name
        branch_name += "_debug" if debug else ""

        remote, publish_url = remote_callback(branch_name)

        with tempfile.TemporaryDirectory() as td:
            directory = td
            report_path = self.save(directory, filename="index.html", in_html_folder=False)
            logger.info(f"created report at: {report_path.absolute()}")

            def git(*args: str) -> None:
                subprocess.run(["git", *args], cwd=directory, check=True)

            git("init")
            git("checkout", "-b", branch_name)
            git("add", "index.html")
            git("commit", "-m", f"publish {branch_name}")
            git("remote", "add", "origin", remote)
            git("push", "--set-upstream", "origin", branch_name, "-f")

        logger.info("Published report @")
        logger.info(publish_url)

        return publish_url
