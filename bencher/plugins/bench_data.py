from __future__ import annotations

from dataclasses import dataclass, field, replace
from datetime import datetime
from typing import Any, Optional, Protocol, runtime_checkable

import xarray as xr

from bencher.plotting.plt_cnt_cfg import PltCntCfg


@runtime_checkable
class CacheHandle(Protocol):
    """Plugin-accessible memoization surface. Bencher core supplies a concrete handle;
    plugins treat it as opaque key/value storage."""

    def get(self, key: str) -> Optional[Any]: ...

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
    plt_cnt_cfg: Optional[PltCntCfg] = None
    run_meta: RunMeta = field(default_factory=RunMeta)
    optimizer_study: Optional[Any] = None
    baseline_runs: tuple["BenchData", ...] = ()
    cache: Optional[CacheHandle] = None
    # Transitional fields for the built-in renderer migration (A1 Phase 2). The wrapped
    # built-ins still render through BenchResult methods that read self.bench_cfg, so the
    # live result object and the to_auto kwargs ride along until the renderers consume
    # BenchData directly (A3 Phase D5). NOT part of the stable plugin contract — plugins
    # gate on them via requires={"legacy_result"} and must expect them to disappear.
    legacy_result: Optional[Any] = None
    render_kwargs: dict = field(default_factory=dict)

    def has(self, capability: str) -> bool:
        """True when an optional context field is populated.

        Used by PlotFilter.requires to gate plugins that need fields beyond dataset+vars."""
        if capability == "optimizer_study":
            return self.optimizer_study is not None
        if capability == "baseline_runs":
            return len(self.baseline_runs) > 0
        if capability == "cache":
            return self.cache is not None
        if capability == "legacy_result":
            return self.legacy_result is not None
        return False

    def with_changes(self, **kwargs) -> "BenchData":
        return replace(self, **kwargs)

    @classmethod
    def fake(
        cls,
        *,
        dataset: Optional[xr.Dataset] = None,
        input_vars: tuple = (),
        result_vars: tuple = (),
        plt_cnt_cfg: Optional[PltCntCfg] = None,
        **overrides,
    ) -> "BenchData":
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
