from __future__ import annotations

from dataclasses import dataclass, field, replace
from datetime import datetime
from typing import Any, Protocol, assert_never, runtime_checkable

import xarray as xr
from strenum import StrEnum

from bencher.plotting.plt_cnt_cfg import PltCntCfg


class Capability(StrEnum):
    """The full vocabulary of optional BenchData context fields a plugin may require.

    A plugin's ``requires`` (see ``Plugin`` in plugin.py) names capabilities from this
    enum (plain strings with these exact values are accepted and normalized). Unknown
    names raise at plugin registration time — a misspelled capability would otherwise
    make the plugin permanently, silently unselectable (plan 23 C10)."""

    OPTIMIZER_STUDY = "optimizer_study"
    BASELINE_RUNS = "baseline_runs"
    CACHE = "cache"
    LEGACY_RESULT = "legacy_result"


def to_capability(value: str | Capability) -> Capability:
    """Normalize *value* to a :class:`Capability`.

    Raises ValueError naming the bad string and the valid vocabulary when *value*
    is not a known capability."""
    try:
        return Capability(value)
    except ValueError:
        valid = ", ".join(sorted(c.value for c in Capability))
        raise ValueError(f"Unknown capability {value!r}; valid capabilities are: {valid}") from None


@runtime_checkable
class CacheHandle(Protocol):
    """Plugin-accessible memoization surface. Bencher core supplies a concrete handle;
    plugins treat it as opaque key/value storage."""

    def get(self, key: str) -> Any | None: ...

    def set(self, key: str, value: Any) -> None: ...


@dataclass(frozen=True)
class RunMeta:
    name: str = ""
    timestamp: datetime = field(default_factory=datetime.now)
    sweep_hash: str = ""


@dataclass(frozen=True)
class BenchData:
    """Frozen value type handed to plot plugins. The stable public contract surface for
    plugin authors — internal bencher refactors must preserve this shape."""

    dataset: xr.Dataset
    input_vars: tuple = ()
    result_vars: tuple = ()
    plt_cnt_cfg: PltCntCfg | None = None
    run_meta: RunMeta = field(default_factory=RunMeta)
    optimizer_study: Any | None = None
    baseline_runs: tuple[BenchData, ...] = ()
    cache: CacheHandle | None = None
    # Transitional fields for the built-in renderer migration (A1 Phase 2). The wrapped
    # built-ins still render through BenchResult methods that read self.bench_cfg, so the
    # live result object and the to_auto kwargs ride along until the renderers consume
    # BenchData directly (A3 Phase D5). NOT part of the stable plugin contract — plugins
    # gate on them via requires={"legacy_result"} and must expect them to disappear.
    legacy_result: Any | None = None
    render_kwargs: dict = field(default_factory=dict)

    def has(self, capability: str | Capability) -> bool:
        """True when an optional context field is populated.

        Used by ``Plugin.requires`` (plugin.py) to gate plugins that need fields
        beyond dataset+vars. Raises ValueError on a capability name outside the
        :class:`Capability` vocabulary instead of silently returning False.

        The match is exhaustive over :class:`Capability` and ends in
        ``assert_never``, so a new member added without a branch here is a
        ``ty`` **check-time** error rather than a runtime abort. This is the
        licensed case of plan 24 A1: the subject comes from
        :func:`to_capability`, whose return type is established as
        ``Capability`` (it is not a ``param`` descriptor read)."""
        cap = to_capability(capability)
        match cap:
            case Capability.OPTIMIZER_STUDY:
                return self.optimizer_study is not None
            case Capability.BASELINE_RUNS:
                return len(self.baseline_runs) > 0
            case Capability.CACHE:
                return self.cache is not None
            case Capability.LEGACY_RESULT:
                return self.legacy_result is not None
            case unreachable:
                assert_never(unreachable)

    def with_changes(self, **kwargs) -> BenchData:
        return replace(self, **kwargs)

    @classmethod
    def fake(
        cls,
        *,
        dataset: xr.Dataset | None = None,
        input_vars: tuple = (),
        result_vars: tuple = (),
        plt_cnt_cfg: PltCntCfg | None = None,
        **overrides,
    ) -> BenchData:
        """Construct a minimal BenchData for plugin unit tests.

        Defaults dataset to an empty xr.Dataset and plt_cnt_cfg to a zero-counted config so
        plugin authors can construct a usable handle in one line."""
        return cls(
            dataset=dataset if dataset is not None else xr.Dataset(),
            input_vars=tuple(input_vars),
            result_vars=tuple(result_vars),
            plt_cnt_cfg=plt_cnt_cfg if plt_cnt_cfg is not None else PltCntCfg(),
            **overrides,
        )
