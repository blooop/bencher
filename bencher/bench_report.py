import logging
from typing import Callable
import os
from pathlib import Path
import tempfile
from threading import Thread
from dataclasses import dataclass

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
        bench_name: str = None,
    ) -> None:
        self.bench_name = bench_name
        self.pane = pn.Tabs(tabs_location="left", name=self.bench_name)

    def append_title(self, title: str, new_tab: bool = True):
        if new_tab:
            return self.append_tab(pn.pane.Markdown(f"# {title}", name=title), title)
        return self.append_markdown(f"# {title}", title)

    def append_markdown(self, markdown: str, name=None, width=800, **kwargs) -> pn.pane.Markdown:
        if name is None:
            name = markdown
        md = pn.pane.Markdown(markdown, name=name, width=width, **kwargs)
        self.append(md, name)
        return md

    def append(self, pane: pn.panel, name: str = None) -> None:
        if len(self.pane) == 0:
            if name is None:
                name = pane.name
            self.append_tab(pane, name)
        else:
            self.pane[-1].append(pane)

    def append_col(self, pane: pn.panel, name: str = None) -> None:
        if name is not None:
            col = pn.Column(pane, name=name)
        else:
            col = pn.Column(pane, name=pane.name)
        self.pane.append(col)

    def append_result(self, bench_res: BenchResult) -> None:
        self.append_tab(bench_res.plot(), bench_res.bench_cfg.title)

    def append_tab(self, pane: pn.panel, name: str = None) -> None:
        if pane is not None:
            if name is None:
                name = pane.name
            self.pane.append(pn.Column(pane, name=name))

    def save_index(self, directory="", filename="index.html") -> Path:
        """Saves the result to index.html in the root folder so that it can be displayed by github pages.

        Returns:
            Path: save path
        """
        return self.save(directory, filename, False)

    def save(
        self,
        directory: str | Path = "cachedir",
        filename: str = None,
        in_html_folder: bool = True,
        **kwargs,
    ) -> Path:
        """Save the result to a html file.  Note that dynamic content will not work.  by passing save(__file__) the html output will be saved in the same folder as the source code in a html subfolder.

        Args:
            directory (str | Path, optional): base folder to save to. Defaults to "cachedir" which should be ignored by git.
            filename (str, optional): The name of the html file. Defaults to the name of the benchmark
            in_html_folder (bool, optional): Put the saved files in a html subfolder to help keep the results separate from source code. Defaults to True.

        Returns:
            Path: the save path
        """

        if filename is None:
            filename = f"{self.bench_name}.html"

        base_path = Path(directory)

        if in_html_folder:
            base_path /= "html"

        logging.info(f"creating dir {base_path.absolute()}")
        os.makedirs(base_path.absolute(), exist_ok=True)

        base_path = base_path / filename

        logging.info(f"saving html output to: {base_path.absolute()}")

        self.pane.save(filename=base_path, progress=True, embed=True, **kwargs)
        return base_path

    def show(self, run_cfg: BenchRunCfg = None) -> Thread:  # pragma: no cover
        """Launches a webserver with plots of the benchmark results, blocking

        Args:
            run_cfg (BenchRunCfg, optional): Options for the webserve such as the port. Defaults to None.

        """
        if run_cfg is None:
            run_cfg = BenchRunCfg()

        return BenchPlotServer().plot_server(self.bench_name, run_cfg, self.pane)

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
        self, remote_callback: Callable, branch_name: str = None, debug: bool = False
    ) -> str:  # pragma: no cover
        """Publish the results as an html file by committing it to the bench_results branch in the current repo. If you have set up your repo with github pages or equivalent then the html file will be served as a viewable webpage.  This is an example of a callable to publish on github pages:

        .. code-block:: python

            def publish_args(branch_name) -> Tuple[str, str]:
                return (
                    "https://github.com/blooop/bencher.git",
                    f"https://github.com/blooop/bencher/blob/{branch_name}")


        Args:
            remote (Callable): A function the returns a tuple of the publishing urls. It must follow the signature def publish_args(branch_name) -> Tuple[str, str].  The first url is the git repo name, the second url needs to match the format for viewable html pages on your git provider.  The second url can use the argument branch_name to point to the report on a specified branch.

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
