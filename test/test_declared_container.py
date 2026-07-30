"""Tests for the declared-container precedence chain (BenchResultBase.ds_to_container).

A *declared* container is the single-argument renderer a result variable carries,
either attached to one stored sample or declared once on the class. It is a different
contract from the ``container=`` a renderer passes in, which is a panel pane
constructor and receives styling keywords; both are exercised here so the two do not
drift into each other.

Module-level callbacks, not lambdas: a declared container rides in BenchCfg, which
the result cache and the collect/render split both pickle.
"""

import unittest

import panel as pn

import bencher as bn
from bencher.results.bench_result_base import BenchResultBase
from test.helpers import run_cfg_with

SIDES = [3, 4]


def as_markdown(text: str) -> pn.pane.Markdown:
    """A declared container for a string result."""
    return pn.pane.Markdown(f"# {text}")


def as_heading(text: str) -> pn.pane.HTML:
    """A second one, so precedence between levels is observable."""
    return pn.pane.HTML(f"<h1>{text}</h1>")


def path_contents(path: str) -> pn.pane.Markdown:
    """Render a file's contents rather than a download widget."""
    with open(path, encoding="utf-8") as handle:
        return pn.pane.Markdown(handle.read())


def wrap_container(value) -> pn.Column:
    return pn.Column(value, name="wrapped")


class StringSweep(bn.ParametrizedSweep):
    """A string result that declares how it renders."""

    sides = bn.IntSweep(default=3, bounds=[3, 4], samples=2)
    label = bn.ResultString(container=as_markdown, doc="rendered as markdown")

    def benchmark(self):
        self.label = f"sides {self.sides}"


class PlainStringSweep(bn.ParametrizedSweep):
    """The same result without a declared container, for the default behaviour."""

    sides = bn.IntSweep(default=3, bounds=[3, 4], samples=2)
    label = bn.ResultString(doc="rendered as text")

    def benchmark(self):
        self.label = f"sides {self.sides}"


class PathSweep(bn.ParametrizedSweep):
    """A path result that renders its contents instead of a download button."""

    sides = bn.IntSweep(default=3, bounds=[3, 4], samples=2)
    report = bn.ResultPath(container=path_contents, doc="rendered as its contents")

    def benchmark(self):
        filename = bn.gen_path("report", suffix=".txt")
        with open(filename, "w", encoding="utf-8") as handle:
            handle.write(f"sides {self.sides}")
        self.report = filename


class PlainPathSweep(bn.ParametrizedSweep):
    """The same result without a declared container: the download widget."""

    sides = bn.IntSweep(default=3, bounds=[3, 4], samples=2)
    report = bn.ResultPath(doc="rendered as a download widget")

    def benchmark(self):
        filename = bn.gen_path("report", suffix=".txt")
        with open(filename, "w", encoding="utf-8") as handle:
            handle.write(f"sides {self.sides}")
        self.report = filename


class ContainerSweep(bn.ParametrizedSweep):
    """A ResultContainer whose declared container wraps the stored pane."""

    sides = bn.IntSweep(default=3, bounds=[3, 4], samples=2)
    widget = bn.ResultContainer(container=wrap_container, doc="wrapped before display")

    def benchmark(self):
        self.widget = pn.pane.Markdown(f"sides {self.sides}")


class ReferenceSweep(bn.ParametrizedSweep):
    """A ResultReference declaring its container on the class, not per sample."""

    sides = bn.IntSweep(default=3, bounds=[3, 4], samples=2)
    plot = bn.ResultReference(container=as_markdown, doc="declared on the class")

    def benchmark(self):
        self.plot = bn.ResultReference(f"sides {self.sides}")


class PerSampleReferenceSweep(bn.ParametrizedSweep):
    """A ResultReference whose sample overrides the class-declared container."""

    sides = bn.IntSweep(default=3, bounds=[3, 4], samples=2)
    plot = bn.ResultReference(container=as_markdown, doc="overridden per sample")

    def benchmark(self):
        self.plot = bn.ResultReference(f"sides {self.sides}", container=as_heading)


def run_sweep(worker: bn.ParametrizedSweep, name: str, result_vars: list[str]):
    bench = bn.Bench(name, worker, run_cfg=run_cfg_with(1))
    return bench.plot_sweep(
        name, input_vars=["sides"], result_vars=result_vars, plot_callbacks=False
    )


def panes(viewable: pn.viewable.Viewable, kind: type) -> list:
    return list(viewable.select(kind))


def rendered(worker: bn.ParametrizedSweep, name: str, result_vars: list[str]):
    res = run_sweep(worker, name, result_vars)
    return res.to_auto(plot_list=["panes"])


class TestDeclaredContainerHelper(unittest.TestCase):
    """The lookup itself: first source that declares one, tolerating old pickles."""

    class _Bare:
        """A result var pickled before its type gained the slot."""

    def test_first_declaring_source_wins(self):
        sample = bn.ResultDataSet(container=as_markdown)
        declared = bn.ResultDataSet(container=as_heading)
        self.assertIs(BenchResultBase.declared_container(sample, declared), as_markdown)

    def test_falls_through_to_the_later_source(self):
        sample = bn.ResultDataSet()
        declared = bn.ResultDataSet(container=as_heading)
        self.assertIs(BenchResultBase.declared_container(sample, declared), as_heading)

    def test_none_when_nothing_declares_one(self):
        self.assertIsNone(BenchResultBase.declared_container(bn.ResultDataSet(), None))

    def test_a_source_without_the_slot_is_skipped_not_an_error(self):
        """An old pickle unpickles without the slot; its report still has to render."""
        self.assertIs(
            BenchResultBase.declared_container(
                self._Bare(), bn.ResultDataSet(container=as_heading)
            ),
            as_heading,
        )

    def test_no_sources_is_none(self):
        self.assertIsNone(BenchResultBase.declared_container())


class TestResultString(unittest.TestCase):
    """A declared container turns text into something richer than plain text."""

    def test_declared_container_renders_the_string(self):
        found = panes(rendered(StringSweep(), "test_declared_string", ["label"]), pn.pane.Markdown)
        headings = [p for p in found if p.object.startswith("# sides ")]
        self.assertEqual(len(headings), len(SIDES))

    def test_without_one_the_string_is_not_wrapped(self):
        found = panes(
            rendered(PlainStringSweep(), "test_plain_string", ["label"]), pn.pane.Markdown
        )
        self.assertEqual([p for p in found if p.object.startswith("# sides ")], [])


class TestResultPath(unittest.TestCase):
    """The motivating case: render a file's contents, not a download button."""

    def test_declared_container_beats_the_download_widget(self):
        view = rendered(PathSweep(), "test_declared_path", ["report"])
        self.assertEqual(panes(view, pn.widgets.FileDownload), [])
        contents = [p.object for p in panes(view, pn.pane.Markdown)]
        self.assertEqual(
            sorted(c for c in contents if c.startswith("sides ")), ["sides 3", "sides 4"]
        )

    def test_without_one_the_download_widget_is_still_the_default(self):
        """to_container() must keep working for every result that declares nothing."""
        view = rendered(PlainPathSweep(), "test_plain_path", ["report"])
        self.assertEqual(len(panes(view, pn.widgets.FileDownload)), len(SIDES))


class TestResultContainer(unittest.TestCase):
    """A ResultContainer is handed to panel as-is unless it declares otherwise."""

    def test_declared_container_wraps_the_stored_value(self):
        view = rendered(ContainerSweep(), "test_declared_container_var", ["widget"])
        wrapped = [c for c in panes(view, pn.Column) if c.name == "wrapped"]
        self.assertEqual(len(wrapped), len(SIDES))


class TestResultReference(unittest.TestCase):
    """A ResultReference could only declare per sample; now the class works too."""

    def test_class_declared_container_is_honoured(self):
        view = rendered(ReferenceSweep(), "test_declared_reference", ["plot"])
        found = [p for p in panes(view, pn.pane.Markdown) if p.object.startswith("# sides ")]
        self.assertEqual(len(found), len(SIDES))

    def test_per_sample_container_overrides_the_class(self):
        view = rendered(PerSampleReferenceSweep(), "test_per_sample_reference", ["plot"])
        self.assertEqual(len(panes(view, pn.pane.HTML)), len(SIDES))
        self.assertEqual(
            [p for p in panes(view, pn.pane.Markdown) if p.object.startswith("# sides ")],
            [],
            "the per-sample container should have won",
        )

    def test_called_with_the_object_alone(self):
        """Single-argument callables must be safe, so one spec serves every type.

        as_markdown takes exactly one argument; before this, a ResultReference
        container was called with the render kwargs too and would have raised.
        """
        view = rendered(ReferenceSweep(), "test_reference_single_arg", ["plot"])
        self.assertTrue(panes(view, pn.pane.Markdown))


class TestPersistentHashUnaffected(unittest.TestCase):
    """A renderer is not data, so declaring one must not move any cache key.

    The slots added to carry a container are all in ``_hash_exclude``, which
    ``_hash_slots`` drops before hashing, so the hash is unchanged for every
    existing result — no history series is orphaned by this change.
    """

    def test_declaring_a_container_does_not_change_the_hash(self):
        for cls in (bn.ResultString, bn.ResultPath, bn.ResultContainer, bn.ResultReference):
            plain, declared = cls(), cls(container=as_markdown)
            plain.name = declared.name = "same"
            self.assertEqual(plain.hash_persistent(), declared.hash_persistent(), cls.__name__)


if __name__ == "__main__":
    unittest.main()
