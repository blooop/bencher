"""The two distributions built from this repo stay in step.

``pyproject.toml`` builds holobench-core (the bencher package, light dependencies, and a
``full`` extra with the heavy ones). ``holobench/pyproject.toml`` builds holobench, which
ships no code and installs ``holobench-core[full]`` at its own version. Nothing at build
time ties the two files together, so these tests do.
"""

from __future__ import annotations

import re
import tomllib
from pathlib import Path

from bencher.optional_deps import HEAVY_PACKAGES

ROOT = Path(__file__).resolve().parent.parent
CORE = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))["project"]
FULL = tomllib.loads((ROOT / "holobench" / "pyproject.toml").read_text(encoding="utf-8"))["project"]

# Distribution name -> top-level import name, where they differ.
IMPORT_NAME = {"scikit-learn": "sklearn", "pyyaml": "yaml"}


def _name(requirement: str) -> str:
    return re.split(r"[\[<>=!~ ;]", requirement, maxsplit=1)[0].lower()


def _import_name(requirement: str) -> str:
    name = _name(requirement)
    return IMPORT_NAME.get(name, name)


def test_holobench_pins_holobench_core_at_its_own_version() -> None:
    assert CORE["name"] == "holobench-core"
    assert FULL["name"] == "holobench"
    assert FULL["version"] == CORE["version"], (
        "holobench/pyproject.toml and pyproject.toml must carry the same version: "
        "holobench pins holobench-core to it. Bump both."
    )
    pins = [FULL["dependencies"], *FULL["optional-dependencies"].values()]
    for requirements in pins:
        for requirement in requirements:
            assert requirement.endswith(f"=={CORE['version']}"), requirement


def test_holobench_installs_everything() -> None:
    assert FULL["dependencies"] == [f"holobench-core[full]=={CORE['version']}"]


def test_holobench_passes_through_the_user_facing_extras() -> None:
    assert set(FULL["optional-dependencies"]) == {"rerun"}
    assert "rerun" in CORE["optional-dependencies"]


def test_the_full_extra_is_what_a_core_install_lacks() -> None:
    """bencher.optional_deps names the packages a core install is missing.

    That set is what turns a missing import into "pip install holobench", and what
    test_core_install blocks. A package added to `full` but not to it fails with a
    bare ModuleNotFoundError on a core install; one in `dependencies` and in it is
    reported missing when it is not.
    """
    full = {_import_name(r) for r in CORE["optional-dependencies"]["full"]}
    core = {_import_name(r) for r in CORE["dependencies"]}
    assert full <= HEAVY_PACKAGES
    assert not core & HEAVY_PACKAGES


def test_the_docs_build_installs_the_full_stack() -> None:
    """Read the Docs installs the repo from docs/conda-environment.yml, then runs every example.

    The repo root is holobench-core, so a bare ``-e ../`` gets no Panel or HoloViews and the
    gallery fails to render.
    """
    env = (ROOT / "docs" / "conda-environment.yml").read_text(encoding="utf-8")
    editable = [line.strip() for line in env.splitlines() if line.strip().startswith("- -e ")]
    assert editable == ["- -e ../[full]"], editable
