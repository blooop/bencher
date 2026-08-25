"""The declared rerun support window, the installed SDK, and the viewer must agree.

Bencher embeds the rerun web viewer by asking a CDN for a viewer whose version
matches the ``rerun-sdk`` that recorded the ``.rrd`` file.  That version is read off
the installed distribution, so the pairing is exact for free — what the ``rerun``
extra has to state is which *minor* bencher was tested against, since that is where
this still-alpha API reshapes archetypes and blueprint types.  Patches inside a minor
are fixes to a format bencher already round-trips, so the window floats across them
and only the minor is pinned.  These tests hold the window to exactly one minor, keep
both rerun distributions on the same one, and keep the no-metadata viewer fallback
inside it, so a version bump cannot land half-done.
"""

import tomllib
import unittest
from importlib.metadata import PackageNotFoundError
from importlib.metadata import version as get_package_version
from pathlib import Path
from unittest import mock

from packaging.requirements import Requirement
from packaging.specifiers import SpecifierSet
from packaging.version import Version

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


def declared_floor(specifier: SpecifierSet) -> Version:
    """The lowest version a specifier admits, as its ``>=`` clause names it."""
    floors = [Version(clause.version) for clause in specifier if clause.operator == ">="]
    if len(floors) != 1:
        raise AssertionError(f"expected exactly one >= clause, got {specifier}")
    return floors[0]


class TestDeclaredRerunPin(unittest.TestCase):
    """The ``rerun`` extra names exactly one supported rerun minor."""

    def setUp(self):
        self.specifiers = declared_rerun_specifiers()
        self.assertEqual(sorted(self.specifiers), sorted(RERUN_PACKAGES))

    def test_each_window_admits_every_patch_of_one_minor(self):
        """A patch fixes a format bencher round-trips; a minor reshapes the API."""
        for name in RERUN_PACKAGES:
            with self.subTest(package=name):
                specifier = self.specifiers[name]
                floor = declared_floor(specifier)
                series = f"{floor.major}.{floor.minor}"
                for patch in (0, 99):
                    self.assertTrue(
                        specifier.contains(f"{series}.{patch}"),
                        f"{name} {specifier} does not admit all of {series}.x",
                    )
                for outside in (
                    f"{floor.major}.{floor.minor + 1}.0",
                    f"{floor.major}.{floor.minor - 1}.99",
                ):
                    self.assertFalse(
                        specifier.contains(outside),
                        f"{name} {specifier} reaches outside {series}.x to {outside}",
                    )

    def test_both_rerun_packages_declare_the_same_window(self):
        """``rerun-notebook`` ships the viewer assets for its matching ``rerun-sdk``."""
        windows = {str(self.specifiers[name]) for name in RERUN_PACKAGES}
        self.assertEqual(len(windows), 1, f"rerun packages disagree on window: {windows}")

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
