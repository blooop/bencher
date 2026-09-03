"""The declared rerun support window, the environments that resolve it, and the viewer must agree.

Bencher embeds the rerun web viewer by asking a CDN for a viewer whose version
matches the ``rerun-sdk`` that recorded the ``.rrd`` file.  That version is read off
the installed distribution, so the pairing is exact for free — what the ``rerun``
extra has to state is which *minors* bencher was tested against, since that is where
this still-alpha API reshapes archetypes, blueprint types and ``rerun.experimental``.
Patches inside a minor are fixes to a format bencher already round-trips, so the
window floats across them.

A window may span more than one minor, but only a minor some environment actually
resolves: the newest is what the default environment installs, and every older one
needs a pixi feature pinning it, so the support claim is exercised rather than
asserted.  These tests hold the window to contiguous minors, keep both rerun
distributions on the same window, require an environment per minor below the top,
and keep the no-metadata viewer fallback inside the window — so a version bump
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
from packaging.version import Version

from bencher.utils_rrd import _get_rerun_version

RERUN_PACKAGES = ("rerun-sdk", "rerun-notebook")
PYPROJECT = Path(__file__).resolve().parents[1] / "pyproject.toml"


def load_pyproject() -> dict:
    with PYPROJECT.open("rb") as handle:
        return tomllib.load(handle)


def declared_rerun_specifiers() -> dict[str, SpecifierSet]:
    """The version specifiers declared by the ``rerun`` extra, keyed by package name."""
    requirements = [
        Requirement(spec) for spec in load_pyproject()["project"]["optional-dependencies"]["rerun"]
    ]
    return {req.name: req.specifier for req in requirements}


def declared_floor(specifier: SpecifierSet) -> Version:
    """The lowest version a specifier admits, as its ``>=`` clause names it."""
    floors = [Version(clause.version) for clause in specifier if clause.operator == ">="]
    if len(floors) != 1:
        raise AssertionError(f"expected exactly one >= clause, got {specifier}")
    return floors[0]


def declared_ceiling(specifier: SpecifierSet) -> Version:
    """The exclusive upper bound a specifier names, as its ``<`` clause names it."""
    ceilings = [Version(clause.version) for clause in specifier if clause.operator == "<"]
    if len(ceilings) != 1:
        raise AssertionError(f"expected exactly one < clause, got {specifier}")
    return ceilings[0]


def declared_minors(specifier: SpecifierSet) -> set[int]:
    """The ``0.x`` minors a window admits, from its floor up to its exclusive ceiling."""
    floor, ceiling = declared_floor(specifier), declared_ceiling(specifier)
    if floor.major != ceiling.major:
        raise AssertionError(f"window {specifier} spans major versions")
    return set(range(floor.minor, ceiling.minor))


def pinned_minors_by_feature() -> dict[str, set[int]]:
    """The rerun minors each ``rerun-*`` pixi feature pins, keyed by feature name."""
    features = load_pyproject()["tool"]["pixi"].get("feature", {})
    pinned = {}
    for name, feature in features.items():
        spec = feature.get("pypi-dependencies", {}).get("rerun-sdk")
        if spec is not None:
            pinned[name] = declared_minors(SpecifierSet(spec))
    return pinned


def features_in_environments() -> set[str]:
    """Every feature named by an environment, so a pin nothing solves is visible."""
    environments = load_pyproject()["tool"]["pixi"]["environments"]
    named = set()
    for environment in environments.values():
        features = environment.get("features", []) if isinstance(environment, dict) else environment
        named.update(features)
    return named


class TestDeclaredRerunPin(unittest.TestCase):
    """The ``rerun`` extra names only minors an environment resolves."""

    def setUp(self):
        self.specifiers = declared_rerun_specifiers()
        self.assertEqual(sorted(self.specifiers), sorted(RERUN_PACKAGES))

    def test_each_window_admits_every_patch_of_its_minors(self):
        """A patch fixes a format bencher round-trips; a minor reshapes the API."""
        for name in RERUN_PACKAGES:
            with self.subTest(package=name):
                specifier = self.specifiers[name]
                floor = declared_floor(specifier)
                minors = declared_minors(specifier)
                self.assertTrue(minors, f"{name} {specifier} admits no whole minor")
                for minor in sorted(minors):
                    for patch in (0, 99):
                        self.assertTrue(
                            specifier.contains(f"{floor.major}.{minor}.{patch}"),
                            f"{name} {specifier} does not admit all of {floor.major}.{minor}.x",
                        )
                for outside in (
                    f"{floor.major}.{max(minors) + 1}.0",
                    f"{floor.major}.{min(minors) - 1}.99",
                ):
                    self.assertFalse(
                        specifier.contains(outside),
                        f"{name} {specifier} reaches outside its minors to {outside}",
                    )

    def test_both_rerun_packages_declare_the_same_window(self):
        """``rerun-notebook`` ships the viewer assets for its matching ``rerun-sdk``."""
        windows = {str(self.specifiers[name]) for name in RERUN_PACKAGES}
        self.assertEqual(len(windows), 1, f"rerun packages disagree on window: {windows}")

    def test_every_minor_below_the_top_is_pinned_by_an_environment(self):
        """The default env resolves the newest minor; each older one needs its own env."""
        minors = declared_minors(self.specifiers["rerun-sdk"])
        pinned = pinned_minors_by_feature()
        self.assertEqual(
            minors - {max(minors)},
            set().union(*pinned.values()) if pinned else set(),
            "the rerun window names a minor no environment resolves (or pins one it "
            f"does not name): window {sorted(minors)}, pinned {pinned}",
        )
        in_environments = features_in_environments()
        for feature in pinned:
            self.assertIn(
                feature,
                in_environments,
                f"feature {feature} pins a rerun minor but no environment includes it, "
                f"so nothing solves or tests it",
            )

    def test_pinned_features_stay_inside_the_declared_window(self):
        declared = self.specifiers["rerun-sdk"]
        for feature, minors in pinned_minors_by_feature().items():
            with self.subTest(feature=feature):
                self.assertLessEqual(
                    minors,
                    declared_minors(declared),
                    f"feature {feature} pins a rerun minor outside {declared}",
                )

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
