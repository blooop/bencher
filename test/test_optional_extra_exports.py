"""The ``rerun``-gated names on the ``bencher`` package are always present.

``bencher.utils_rerun`` is the only module in the package that imports ``rerun`` at
module scope, so its three exports (``capture_rerun_rrd``, ``capture_rerun_window``,
``rerun_to_pane``) are the only ones that could go missing. They used to be bound only
inside ``try``/``except ModuleNotFoundError`` in ``bencher/__init__.py``: without
``rerun-sdk`` they did not exist, and ``bn.capture_rerun_rrd`` raised ``AttributeError:
module 'bencher' has no attribute ...``, a message naming neither the optional
dependency nor how to install it. That partial surface is what ty reports as
``possibly-missing-attribute`` (plan 23 P12b).

**Why these tests are shaped the way they are.** Every pixi environment in this repo
installs the ``rerun`` feature, so there is no environment in which the ``except``
branch runs -- an ``assert hasattr(bn, name)`` test would pass identically on the
unfixed code and prove nothing. So:

* ``test_gated_imports_bind_on_both_branches`` parses ``bencher/__init__.py`` and checks
  the *structure*: every name bound in a ``ModuleNotFoundError``-guarded ``try`` must
  also be bound by its handler. That is the regression that can actually recur -- a
  fourth gated import added without a matching placeholder -- and it is checked without
  needing an install that lacks the extra.
* The rest drive ``_requires_rerun`` directly, because the placeholder is code that only
  ever runs on the installs least able to report a problem.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from bencher import _requires_rerun

INIT_PY = Path(__file__).resolve().parent.parent / "bencher" / "__init__.py"


def _handler_catches_import_failure(handler: ast.ExceptHandler) -> bool:
    """True when *handler* would catch a failed import.

    Matches the bare name, a tuple of names, a dotted spelling, and a bare ``except:``.
    Deliberately generous: this predicate decides whether a block is *inspected at all*,
    so anything it misses is a silent skip -- a false pass in the one direction that
    matters. The first version required ``isinstance(h.type, ast.Name)`` with the exact
    id ``ModuleNotFoundError``, so a block written ``except ImportError:`` (the more
    common spelling of the two) or ``except (ModuleNotFoundError, ImportError):`` was
    dropped from the scan entirely and the test reported green.
    """
    caught = ["ImportError", "ModuleNotFoundError", "Exception", "BaseException"]
    if handler.type is None:  # bare `except:`
        return True
    nodes = handler.type.elts if isinstance(handler.type, ast.Tuple) else [handler.type]
    for node in nodes:
        if isinstance(node, ast.Name) and node.id in caught:
            return True
        if isinstance(node, ast.Attribute) and node.attr in caught:  # builtins.ImportError
            return True
    return False


def _bound_names(statements: list[ast.stmt]) -> set[str]:
    """Names assigned at the top level of *statements* (``x = ...`` and ``x: T = ...``)."""
    names = set()
    for stmt in statements:
        if isinstance(stmt, ast.Assign):
            names |= {t.id for t in stmt.targets if isinstance(t, ast.Name)}
        elif isinstance(stmt, ast.AnnAssign) and isinstance(stmt.target, ast.Name):
            names.add(stmt.target.id)
    return names


def _gated_import_blocks() -> list[tuple[set[str], set[str]]]:
    """(names bound by the try, names bound by its import-catching handlers) per block."""
    tree = ast.parse(INIT_PY.read_text())
    blocks = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Try):
            continue
        # Only handlers that catch an import failure count as providing the fallback.
        # Harvesting from *every* handler would let `except ValueError: x = ...` satisfy
        # a block whose `except ModuleNotFoundError:` arm is a bare `pass`.
        catching = [h for h in node.handlers if _handler_catches_import_failure(h)]
        if not catching:
            continue
        imported = {
            alias.asname or alias.name.split(".")[0]
            for stmt in node.body
            if isinstance(stmt, (ast.Import, ast.ImportFrom))
            for alias in stmt.names
        }
        bound_in_handler = set().union(*(_bound_names(h.body) for h in catching))
        blocks.append((imported, bound_in_handler))
    return blocks


def test_gated_imports_bind_on_both_branches() -> None:
    """A name that can fail to import must have a placeholder, or the surface is partial.

    Structural, not behavioural, and deliberately so: every pixi environment here has
    ``rerun-sdk``, so a runtime check of the fallback would be vacuous. This catches the
    recurrence that matters -- someone adds a gated import and forgets the handler --
    in the one environment we actually run.
    """
    blocks = _gated_import_blocks()
    assert blocks, (
        f"no import-guarded try blocks found in {INIT_PY.name}. If the last one was "
        "removed, delete this test with it; if the guard was respelled in a way "
        "_handler_catches_import_failure does not recognise, teach it the new spelling "
        "rather than leaving it matching nothing."
    )
    for imported, bound in blocks:
        missing = imported - bound
        assert not missing, (
            f"{sorted(missing)} are imported inside an import-guarded try block in "
            f"{INIT_PY.name} but are not bound by the handler that catches the failure, "
            "so on an install without the optional dependency they vanish from the "
            "bencher namespace and reads raise AttributeError. Bind each to "
            "_requires_rerun(<name>)."
        )


def test_the_gated_block_is_the_one_module_that_needs_it() -> None:
    """Only ``utils_rerun`` imports ``rerun`` at module scope; the rest defer it.

    Pins the fact that justifies importing the other five rerun exports unconditionally.
    If someone hoists an ``import rerun`` to module scope in one of those files, that
    import becomes genuinely optional and needs a guard -- this fails and says so.
    """
    package = INIT_PY.parent
    module_scope_importers = set()
    for path in package.rglob("*.py"):
        rel = path.relative_to(package).as_posix()
        # The rerun *examples* import rerun at module scope, correctly -- they are
        # standalone scripts run by name. `bencher/example/` is not wholly off the
        # `import bencher` path (`__init__.py` pulls in `example.benchmark_data`), so the
        # exemption is spelled per-file rather than per-tree: benchmark_data.py is the one
        # example module the package imports, and it stays in scope.
        if rel.startswith("example/") and rel != "example/benchmark_data.py":
            continue
        for node in ast.parse(path.read_text()).body:  # body = module scope only
            names = []
            if isinstance(node, ast.Import):
                names = [a.name for a in node.names]
            elif isinstance(node, ast.ImportFrom):
                # `from . import utils_rerun` has module None and the name on the alias;
                # `from .utils_rerun import x` has it on module. Both re-export the
                # rerun-importing module into another module's scope, which breaks
                # `import bencher` exactly as a direct `import rerun` would -- so both
                # count. The first version matched only literal `rerun*` module names and
                # skipped `node.module is None` outright, missing both forms.
                names = [node.module or ""] + [a.name for a in node.names]
            if any(
                n == "rerun" or n.startswith("rerun.") or n.split(".")[-1] == "utils_rerun"
                for n in names
            ):
                module_scope_importers.add(rel)
    assert module_scope_importers == {"utils_rerun.py"}, (
        f"modules importing `rerun` at module scope changed to {sorted(module_scope_importers)}. "
        "bencher/__init__.py imports RerunResult, ComposableContainerRerun, RerunRecording, "
        "RerunViewKind and RerunSummaryResult unconditionally *because* their modules defer "
        "`import rerun` into the methods that need it. A new module-scope import makes one of "
        "those genuinely optional, and it needs a guarded import with a placeholder."
    )


def test_placeholder_names_the_missing_dependency() -> None:
    """Using a placeholder says what to install, rather than 'has no attribute'."""
    placeholder = _requires_rerun("capture_rerun_rrd")
    with pytest.raises(ImportError) as ctx:
        placeholder()
    message = str(ctx.value)
    assert "bencher.capture_rerun_rrd" in message
    assert "rerun-sdk" in message
    assert "pip install rerun-sdk" in message


def test_placeholder_raises_on_any_call_signature() -> None:
    """The real exports take varied arguments; the placeholder must not shadow the
    ImportError with a TypeError about the arguments."""
    placeholder = _requires_rerun("capture_rerun_window")
    with pytest.raises(ImportError):
        placeholder(600, height=600)


def test_placeholder_is_a_class_so_isinstance_stays_legal() -> None:
    """Returned as a class, not a function: code doing ``isinstance(x, bn.rerun_to_pane)``
    on an install without the extra gets False, not ``TypeError: isinstance() arg 2 must
    be a type``."""
    placeholder = _requires_rerun("rerun_to_pane")
    assert isinstance(placeholder, type)
    assert not isinstance(object(), placeholder)


def test_placeholder_does_not_break_feature_probes() -> None:
    """``hasattr`` and ``getattr(..., default)`` must keep working on a placeholder.

    An earlier revision gave the placeholder a metaclass whose ``__getattr__`` raised
    ``ImportError``, so attribute access would carry the branded message too. Both
    builtins only swallow ``AttributeError``, so that turned every defensive probe --
    autodoc, plugin discovery, ``getattr(x, "__wrapped__", None)`` -- into an
    uncatchable-by-idiom crash, on precisely the installs least able to diagnose it.
    The branded error belongs at call time, where the caller meant to *use* the thing.
    """
    placeholder = _requires_rerun("capture_rerun_rrd")
    assert hasattr(placeholder, "nope") is False
    assert getattr(placeholder, "nope", "DEFAULT") == "DEFAULT"


def test_placeholder_keeps_its_own_identity_attributes() -> None:
    """Ordinary class introspection still answers."""
    placeholder = _requires_rerun("rerun_to_pane")
    assert placeholder.__name__ == "rerun_to_pane"
    assert placeholder.__doc__ is not None
    assert "rerun-sdk" in placeholder.__doc__
