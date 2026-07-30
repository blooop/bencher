"""Reusable sweep declarations.

``plot_sweep`` takes fifteen keyword arguments and consumes them into a
``BenchCfg`` inside its own body, so there is no object representing "this sweep".
A benchmark that must run against more than one worker -- two backends, a mocked
and a live dependency, two hardware tiers -- therefore has one declaration and N
call sites, with nothing linking them. They drift: one side gains a result
variable, one keeps an old constant, and because each side still produces a valid
benchmark, nothing fails.

:class:`SweepSpec` is that missing object: a frozen record of ``plot_sweep``'s
*declarative* arguments only. Run configuration (repeats, sampling resolution,
publishing) is deliberately not here -- a spec states what is measured, not how
the run is driven.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, fields, replace
from typing import Any

import param

# The shaping keys bn.sweep() may put in a spec dict. Shaping applies to inputs
# and consts only: the dict branch of variable conversion calls with_samples /
# with_bounds / with_sample_values, and result variables are not SweepBase.
_SHAPING_KEYS = ("values", "bounds", "samples", "max_subsampling_divisions")

# Fields whose value is a mapping merged key-by-key rather than replaced.
_MERGED_FIELDS = frozenset({"const_vars"})

# Fields that are ordered sequences of variables.
_VAR_LIST_FIELDS = frozenset({"input_vars", "result_vars"})


def _reject_callable(field_name: str, value: Any) -> None:
    """A spec must stay a serialisable value.

    A callable in any field breaks equality and pickling, which are the two
    properties that make a spec useful for detecting drift between call sites.
    ``plot_callbacks`` and the other render-time arguments are excluded from a
    spec for the same reason, so a callable arriving here is always a mistake.
    """
    if callable(value) and not isinstance(value, (type, param.Parameter)):
        raise TypeError(
            f"SweepSpec.{field_name} may not contain a callable ({value!r}). A spec is "
            f"a value: a callable breaks equality and pickling, which is what makes "
            f"two bindings of one declaration comparable. Compute the value before "
            f"building the spec, or pass render-time arguments to plot_sweep directly."
        )


def _normalise_var_list(field_name: str, value: Any) -> tuple:
    if isinstance(value, Mapping):
        raise TypeError(
            f"SweepSpec.{field_name} must be a list, not a mapping. Passing the whole "
            f"variable list as a {{name: values}} dict is deprecated in plot_sweep; use "
            f"a list of bn.sweep() specs."
        )
    out = []
    for entry in value:
        _reject_callable(field_name, entry)
        if field_name == "result_vars" and isinstance(entry, Mapping):
            shaped = sorted(k for k in _SHAPING_KEYS if entry.get(k))
            if shaped:
                raise TypeError(
                    f"SweepSpec.result_vars entry {entry.get('name')!r} carries sweep "
                    f"shaping {shaped}. Shaping applies to inputs and consts only -- "
                    f"result variables are not SweepBase, so this raises AttributeError "
                    f"mid-run rather than at declaration. Use a bare name."
                )
        out.append(entry)
    return tuple(out)


def _normalise_consts(value: Any) -> tuple:
    """Both accepted spellings become a tuple of (variable, value) pairs."""
    items = value.items() if isinstance(value, Mapping) else value
    out = []
    for entry in items:
        if isinstance(entry, (str, bytes)) or not isinstance(entry, Sequence):
            raise TypeError(
                f"SweepSpec.const_vars list entries must be (variable, value) pairs, "
                f"got {entry!r}. Use a mapping, or a list of 2-sequences."
            )
        if len(entry) != 2:
            raise TypeError(f"SweepSpec.const_vars entries must be 2-sequences, got {entry!r}")
        _reject_callable("const_vars", entry[0])
        _reject_callable("const_vars", entry[1])
        out.append((entry[0], entry[1]))
    return tuple(out)


@dataclass(frozen=True)
class SweepSpec:
    """One sweep declaration, as a value.

    Every field defaults to ``None`` meaning *unset*, so a spec never has to state
    what it does not care about, and an unset field leaves ``plot_sweep``'s own
    default in force. ``input_vars=None`` auto-discovers every input on the worker;
    ``input_vars=()`` declares none.

    Written entirely from *names* -- a plain string, a :func:`bencher.sweep` spec
    dict, a ``{name: value}`` const mapping -- a spec references no class and can
    therefore be bound to more than one worker. That by-name form is what makes
    reuse possible, and it is why :meth:`bind` takes the worker rather than the
    spec holding one.

    Equality and pickling are the point: two bindings of one declaration can be
    compared, which is how drift between call sites becomes visible. A spec
    containing a :func:`bencher.sweep` dict is not *hashable* (a dict is not),
    exactly as a tuple containing a list is not.
    """

    title: str | None = None
    description: str | None = None
    post_description: str | None = None
    input_vars: tuple | None = None
    result_vars: tuple | None = None
    const_vars: tuple | None = None
    tag: str | None = None

    def __post_init__(self) -> None:
        for name in ("title", "description", "post_description", "tag"):
            value = getattr(self, name)
            if value is not None and not isinstance(value, str):
                raise TypeError(f"SweepSpec.{name} must be a string, got {value!r}")
        for name in _VAR_LIST_FIELDS:
            value = getattr(self, name)
            if value is not None:
                object.__setattr__(self, name, _normalise_var_list(name, value))
        if self.const_vars is not None:
            object.__setattr__(self, "const_vars", _normalise_consts(self.const_vars))

    @property
    def set_fields(self) -> dict:
        """The fields this spec actually declares, for merging."""
        return {
            f.name: getattr(self, f.name) for f in fields(self) if getattr(self, f.name) is not None
        }

    def with_(self, **overrides) -> SweepSpec:
        """A new spec with *overrides* applied, override winning.

        Precedence is per field *kind*, and the asymmetry is deliberate:

        * scalars (``title``, ``tag``, the descriptions) are **replaced**.
        * ``const_vars`` is **shallow-merged**, override winning per key -- the
          common case is one environment needing a longer timeout than another.
        * ``input_vars`` and ``result_vars`` are **replaced, not appended**.
          Order matters for ``input_vars`` (it sets the dimension layout and is
          hashed in list order), and silent appending is how duplicate result
          variables arise. Use :meth:`plus_result_vars` when appending is what you
          mean, so the intent is written down.
        """
        unknown = set(overrides) - {f.name for f in fields(self)}
        if unknown:
            raise TypeError(f"SweepSpec has no field(s) {sorted(unknown)}")
        resolved = {}
        for name, value in overrides.items():
            if value is None:
                resolved[name] = None
                continue
            if name in _MERGED_FIELDS and getattr(self, name) is not None:
                merged = dict(getattr(self, name))
                merged.update(dict(_normalise_consts(value)))
                resolved[name] = tuple(merged.items())
            else:
                resolved[name] = value
        return replace(self, **resolved)

    def plus_result_vars(self, *result_vars) -> SweepSpec:
        """Append result variables to this spec's, keeping order.

        The explicit spelling for the additive case that :meth:`with_` refuses to
        do implicitly. Appending is exactly how a metric ends up declared twice
        when lists are assembled from several sources, so the duplicate validation
        in ``plot_sweep`` is the backstop -- this method just makes the intent
        legible at the call site.
        """
        flat = []
        for entry in result_vars:
            if isinstance(entry, (list, tuple)) and not isinstance(entry, str):
                flat.extend(entry)
            else:
                flat.append(entry)
        return replace(self, result_vars=(*(self.result_vars or ()), *flat))

    def plus_input_vars(self, *input_vars) -> SweepSpec:
        """Append input variables. Order is the dimension layout, so appending
        puts the new dimension last."""
        flat = []
        for entry in input_vars:
            if isinstance(entry, (list, tuple)) and not isinstance(entry, str):
                flat.extend(entry)
            else:
                flat.append(entry)
        return replace(self, input_vars=(*(self.input_vars or ()), *flat))

    def merge(self, other: SweepSpec) -> SweepSpec:
        """``other``'s declared fields applied on top of this spec's."""
        return self.with_(**other.set_fields)

    def bind(self, worker: Any = None) -> dict:
        """The exact keyword arguments ``plot_sweep`` would receive.

        This is the testability payoff: a project can assert what each of its
        environments resolves to without constructing a bench or running anything,
        and it pairs directly with ``bn.sweep_identity(**spec.bind(W), worker=W)``.

        *worker* is accepted for symmetry and validation only -- resolution of
        by-name variables happens inside ``plot_sweep`` against the bench's own
        worker. Passing it here checks every name up front, so a typo surfaces at
        bind time with the available parameters listed rather than mid-run.

        Lists, not tuples: ``plot_sweep`` converts its variable lists in place.
        """
        inputs = list(self.input_vars) if self.input_vars is not None else None
        results = list(self.result_vars) if self.result_vars is not None else None
        consts = [list(pair) for pair in self.const_vars] if self.const_vars is not None else None

        if worker is not None:
            self._check_names(worker)
            inputs, results, consts = self._validate(worker, inputs, results, consts)

        out: dict = {}
        for name in ("title", "description", "post_description", "tag"):
            if getattr(self, name) is not None:
                out[name] = getattr(self, name)
        if inputs is not None:
            out["input_vars"] = inputs
        if results is not None:
            out["result_vars"] = results
        if consts is not None:
            out["const_vars"] = consts
        return out

    def _resolved(self, worker: Any, entry: Any, var_type: str) -> Any:
        """The param.Parameter *entry* names, or *entry* itself if it is already one."""
        from bencher.sweep_executor import _resolve_param

        if isinstance(entry, str):
            return _resolve_param(entry, worker, var_type)
        if isinstance(entry, Mapping):
            return _resolve_param(entry["name"], worker, var_type)
        return entry

    def _check_names(self, worker: Any) -> None:
        """Resolve every by-name variable now, so a typo fails at bind time."""
        for var_type, entries in (
            ("input", self.input_vars or ()),
            ("result", self.result_vars or ()),
            ("const", [pair[0] for pair in self.const_vars or ()]),
        ):
            for entry in entries:
                self._resolved(worker, entry, var_type)

    def _validate(self, worker: Any, inputs, results, consts):
        """Run ``plot_sweep``'s duplicate-variable validation at bind time.

        A spec is the main *source* of duplicates -- composing overlapping groups
        from several places is exactly what specs make easy -- so a spec should not
        be able to hand ``plot_sweep`` a declaration that ``plot_sweep`` will then
        reject or silently dedupe. Calling the one validation site here means a
        duplicate input variable fails at ``bind()``, where the composition that
        caused it is in view, and a duplicate result variable is warned about and
        dropped once rather than twice.

        Comparison is on the *resolved* name, and the entries returned are the
        caller's own declaration forms -- strings, spec dicts, param objects -- so
        the bound arguments stay bindable to a different worker.
        """
        from bencher.sweep_executor import validate_declared_vars

        def by_name(entries, var_type):
            return [self._resolved(worker, e, var_type) for e in entries or ()]

        kept_inputs, kept_results, kept_consts = validate_declared_vars(
            by_name(inputs, "input"),
            by_name(results, "result"),
            [[self._resolved(worker, pair[0], "const"), pair[1]] for pair in consts or ()],
        )

        def survivors(entries, kept_names, name_of):
            """The caller's own entries, filtered to the names validation kept.

            Consumed from a list rather than a set so that when validation keeps one
            of two same-named entries, exactly one original survives.
            """
            if entries is None:
                return None
            wanted = list(kept_names)
            out = []
            for entry in entries:
                name = name_of(entry)
                if name in wanted:
                    wanted.remove(name)
                    out.append(entry)
            return out

        def input_name(entry):
            return self._resolved(worker, entry, "input").name

        def result_name(entry):
            return self._resolved(worker, entry, "result").name

        def const_name(pair):
            return self._resolved(worker, pair[0], "const").name

        return (
            survivors(inputs, [v.name for v in kept_inputs], input_name),
            survivors(results, [v.name for v in kept_results], result_name),
            survivors(consts, [v[0].name for v in kept_consts], const_name),
        )

    def describe(self) -> str:
        """One line per declared field, for eyeballing two specs side by side."""

        def name_of(entry: Any) -> str:
            if isinstance(entry, Mapping):
                return str(entry.get("name"))
            return str(getattr(entry, "name", entry))

        lines = []
        for key, value in self.set_fields.items():
            if key in _VAR_LIST_FIELDS:
                rendered = ", ".join(name_of(v) for v in value) or "(none)"
            elif key == "const_vars":
                rendered = ", ".join(f"{name_of(v)}={val!r}" for v, val in value) or "(none)"
            else:
                rendered = str(value)
            lines.append(f"{key}: {rendered}")
        return "\n".join(lines)


def diff_specs(left: SweepSpec, right: SweepSpec) -> list[str]:
    """Lines naming every field in which two specs differ.

    The drift detector: two bindings of one declaration that should agree can be
    compared directly instead of by reading both call sites side by side.
    """
    out = []
    for f in fields(left):
        a, b = getattr(left, f.name), getattr(right, f.name)
        if a != b:
            out.append(f"{f.name}: {a!r} != {b!r}")
    return out
