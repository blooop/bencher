"""The declared rerun support window, the installed SDK, and the viewer must agree.

Bencher embeds the rerun web viewer by asking a CDN for a viewer whose version
matches the ``rerun-sdk`` that recorded the ``.rrd`` file.  That only works if
three things stay in lockstep: the version declared by the ``rerun`` extra, the
version actually installed, and the version bencher falls back to when
``rerun-sdk`` is absent.  These tests pin that agreement so a version bump
cannot land half-done.
"""

import tomllib
import unittest
from importlib.metadata import PackageNotFoundError
from importlib.metadata import version as get_package_version
from pathlib import Path
from unittest import mock

from packaging.requirements import Requirement
from packaging.specifiers import SpecifierSet

from bencher.utils_rrd import _get_rerun_version

RERUN_PACKAGES = ("rerun-sdk", "rerun-notebook")


def declared_rerun_specifiers() -> dict[str, SpecifierSet]:
    """The version specifiers declared by the ``rerun`` extra, keyed by package name."""
    pyproject = Path(__file__).resolve().parents[1] / "pyproject.toml"
    with pyproject.open("rb") as handle:
        config = tomllib.load(handle)
    requirements = [
        Requirement(spec) for spec in config["project"]["optional-dependencies"]["rerun"]
    ]
    return {req.name: req.specifier for req in requirements}


def declared_pin(specifier: SpecifierSet) -> set[str]:
    """The distinct versions a specifier names, ignoring exclusions."""
    return {clause.version for clause in specifier if clause.operator != "!="}


class TestDeclaredRerunPin(unittest.TestCase):
    """The ``rerun`` extra names exactly one supported rerun version."""

    def setUp(self):
        self.specifiers = declared_rerun_specifiers()
        self.assertEqual(sorted(self.specifiers), sorted(RERUN_PACKAGES))

    def test_each_rerun_package_is_pinned_to_a_single_version(self):
        """The rerun API is alpha-stage, so bencher supports one version at a time."""
        for name in RERUN_PACKAGES:
            with self.subTest(package=name):
                specifier = self.specifiers[name]
                self.assertEqual(
                    len(declared_pin(specifier)),
                    1,
                    f"{name} should pin exactly one version, got {specifier}",
                )

    def test_both_rerun_packages_are_pinned_to_the_same_version(self):
        """``rerun-notebook`` ships the viewer assets for its matching ``rerun-sdk``."""
        pinned = {frozenset(declared_pin(self.specifiers[name])) for name in RERUN_PACKAGES}
        self.assertEqual(len(pinned), 1, f"rerun packages disagree on version: {pinned}")

    def test_installed_rerun_packages_satisfy_the_declared_pin(self):
        for name in RERUN_PACKAGES:
            with self.subTest(package=name):
                try:
                    installed = get_package_version(name)
                except PackageNotFoundError:  # pragma: no cover - rerun extra is always installed
                    self.skipTest(f"{name} is not installed")
                self.assertTrue(
                    self.specifiers[name].contains(installed, prereleases=True),
                    f"installed {name} {installed} violates declared {self.specifiers[name]}",
                )

    def test_viewer_fallback_version_is_within_the_declared_pin(self):
        """With no ``rerun-sdk`` installed, the CDN viewer version is still a supported one."""
        with mock.patch("bencher.utils_rrd.get_package_version", side_effect=PackageNotFoundError):
            fallback = _get_rerun_version()
        self.assertTrue(
            self.specifiers["rerun-sdk"].contains(fallback, prereleases=True),
            f"viewer fallback {fallback} violates declared rerun-sdk pin "
            f"{self.specifiers['rerun-sdk']}",
        )


if __name__ == "__main__":
    unittest.main()
