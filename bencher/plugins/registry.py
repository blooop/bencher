from __future__ import annotations

import logging
import traceback
from collections.abc import Iterable
from dataclasses import dataclass, field
from importlib import metadata

import panel as pn

from bencher.plugins.bench_data import BenchData
from bencher.plugins.plugin import PlotPlugin

ENTRY_POINT_GROUP = "bencher.plot_plugins"

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class PluginDecision:
    """One row of a selection decision table: whether a plugin was chosen for a
    given BenchData, and the first gate that rejected it when it wasn't."""

    name: str
    backend: str
    chosen: bool
    reason: str
    plugin: PlotPlugin = field(repr=False)


def decisions_to_table(decisions: Iterable[PluginDecision]) -> str:
    """Render a decision table (from ``PluginRegistry.explain``) as a markdown-ish
    text table, chosen rows first."""
    rows = [("chart type", "backend", "chosen", "reason")]
    rows += [(d.name, d.backend, "yes" if d.chosen else "no", d.reason) for d in decisions]
    widths = [max(len(r[i]) for r in rows) for i in range(4)]
    lines = [
        f"| {r[0]:<{widths[0]}} | {r[1]:<{widths[1]}} | {r[2]:<{widths[2]}} | {r[3]:<{widths[3]}} |"
        for r in rows
    ]
    lines.insert(1, "|" + "|".join("-" * (w + 2) for w in widths) + "|")
    return "\n".join(lines)


def _render_error_pane(plugin_name: str, exc: BaseException) -> pn.viewable.Viewable:
    tb = "".join(traceback.format_exception(type(exc), exc, exc.__traceback__))
    body = f"### Plugin error: `{plugin_name}`\n\n```\n{tb}\n```"
    return pn.pane.Markdown(body, sizing_mode="stretch_width")


class PluginRegistry:
    """In-process registry of plot plugins, keyed by (name, backend).

    `name` is the chart type ("line", "heatmap", ...); `backend` is the rendering
    library namespace ("holoviews", "rerun", ...). Several backends may implement the
    same chart type; selection resolves each chart type to one implementation — the
    preferred backend when given, otherwise the highest-priority one. Registering an
    existing (name, backend) pair replaces it, which is the documented override
    mechanism (a user plugin replaces a built-in by sharing its name and backend, or
    outranks it from a different backend via priority/preference)."""

    def __init__(self) -> None:
        self._plugins: dict[tuple[str, str], PlotPlugin] = {}
        self._entry_points_loaded = False

    def register(self, plugin: PlotPlugin) -> None:
        if not isinstance(plugin.name, str) or not plugin.name:
            raise ValueError("Plugin must have a non-empty string name")
        if not isinstance(plugin.backend, str) or not plugin.backend:
            raise ValueError("Plugin must have a non-empty string backend")
        self._plugins[(plugin.name, plugin.backend)] = plugin

    def unregister(self, name: str, backend: str | None = None) -> None:
        """Remove a plugin. With no backend, removes every backend's implementation
        of that chart type."""
        if backend is not None:
            self._plugins.pop((name, backend), None)
            return
        for key in [k for k in self._plugins if k[0] == name]:
            self._plugins.pop(key, None)

    def clear(self) -> None:
        self._plugins.clear()
        self._entry_points_loaded = False

    def mark_entry_points_loaded(self) -> None:
        """Skip the entry-point scan on next lookup. Test-only helper."""
        self._entry_points_loaded = True

    def get(self, name: str, backend: str | None = None) -> PlotPlugin | None:
        """Resolve a chart type to one implementation.

        With a backend, exact lookup. Without, the preferred implementation:
        highest priority among all backends providing `name` (ties broken by
        backend string for determinism)."""
        self._ensure_entry_points_loaded()
        if backend is not None:
            return self._plugins.get((name, backend))
        impls = [p for (n, _b), p in self._plugins.items() if n == name]
        if not impls:
            return None
        return max(impls, key=lambda p: (p.priority, p.backend))

    def implementations(self, name: str) -> tuple[PlotPlugin, ...]:
        """Every backend's implementation of a chart type, highest priority first."""
        self._ensure_entry_points_loaded()
        impls = [p for (n, _b), p in self._plugins.items() if n == name]
        impls.sort(key=lambda p: (-p.priority, p.backend))
        return tuple(impls)

    def all(self) -> tuple[PlotPlugin, ...]:
        self._ensure_entry_points_loaded()
        return tuple(self._plugins.values())

    def _ensure_entry_points_loaded(self) -> None:
        if self._entry_points_loaded:
            return
        # Mark first to avoid recursion if a load triggers another lookup.
        self._entry_points_loaded = True
        try:
            eps = metadata.entry_points(group=ENTRY_POINT_GROUP)
        except TypeError:  # pragma: no cover - older importlib.metadata API
            all_eps = metadata.entry_points()
            eps = all_eps.get(ENTRY_POINT_GROUP, [])  # pylint: disable=no-member
        for ep in eps:
            try:
                obj = ep.load()
            except Exception as exc:  # pylint: disable=broad-exception-caught  # noqa: BLE001
                log.warning("Skipping plugin entry-point %r: %s", ep.name, exc)
                continue
            self._register_loaded(ep.name, obj)

    def _register_loaded(self, ep_name: str, obj) -> None:
        # Entry points may resolve to a single plugin instance, a plugin class (no-arg
        # constructor), or a callable returning an iterable of plugins. Accept all three.
        if callable(obj) and not hasattr(obj, "render"):
            try:
                produced = obj()
            except Exception as exc:  # pylint: disable=broad-exception-caught  # noqa: BLE001
                log.warning("Plugin factory %r raised: %s", ep_name, exc)
                return
            if isinstance(produced, PlotPlugin):
                self.register(produced)
                return
            try:
                for p in produced:
                    self.register(p)
            except TypeError:
                log.warning(
                    "Plugin entry-point %r returned non-iterable, non-plugin %r",
                    ep_name,
                    produced,
                )
            return
        if isinstance(obj, PlotPlugin):
            self.register(obj)
            return
        log.warning("Plugin entry-point %r resolved to unrecognised object %r", ep_name, obj)

    def select(
        self,
        data: BenchData,
        *,
        include: Iterable[str] | None = None,
        exclude: Iterable[str] | None = None,
        backend: str | None = None,
        only: str | None = None,
    ) -> tuple[PlotPlugin, ...]:
        """Return one matching implementation per chart type, by descending priority.

        - `only` short-circuits to a single named chart type (no match-filter check;
          explicit opt-in by name implies the user knows what they want).
        - `include` / `exclude` filter the candidate set by chart-type name.
        - Named-only plugins (``auto=False``) are skipped during automatic selection
          (`include is None`); naming them via `include` or `only` selects them.
        - `backend` states the *preferred* backend: where a chart type is implemented
          by several backends, the preferred one is chosen when it matches; chart
          types the preferred backend does not provide still render through their
          best other implementation. This is what lets a config flag swap the
          rendering library under the same set of plotters.
        """
        return tuple(
            d.plugin
            for d in self.explain(
                data, include=include, exclude=exclude, backend=backend, only=only
            )
            if d.chosen
        )

    def explain(
        self,
        data: BenchData,
        *,
        include: Iterable[str] | None = None,
        exclude: Iterable[str] | None = None,
        backend: str | None = None,
        only: str | None = None,
    ) -> tuple[PluginDecision, ...]:
        """The full selection decision table: one entry per registered plugin, chosen
        entries first (in `select()` order — descending priority, then name), each
        rejected entry carrying the first gate that dropped it. `select()` is exactly
        the chosen subset, so this is the authoritative record of why a plot did or
        did not appear (A2 Phase S2)."""
        chosen: list[PluginDecision] = []
        rejected: list[PluginDecision] = []

        def reject(plugin: PlotPlugin, reason: str) -> None:
            rejected.append(PluginDecision(plugin.name, plugin.backend, False, reason, plugin))

        if only is not None:
            picked = self.get(only, backend) or self.get(only)
            for plugin in self.all():
                if plugin is picked:
                    chosen.append(
                        PluginDecision(
                            plugin.name,
                            plugin.backend,
                            True,
                            f"explicitly requested (only={only!r}; filters bypassed)",
                            plugin,
                        )
                    )
                else:
                    reject(plugin, f"not requested (only={only!r})")
            return tuple(chosen + rejected)

        inc = set(include) if include is not None else None
        exc = set(exclude) if exclude is not None else set()

        matched: list[PlotPlugin] = []
        for plugin in self.all():
            if inc is not None and plugin.name not in inc:
                reject(plugin, "not named in include/plot_list")
                continue
            if inc is None and not getattr(plugin, "auto", True):
                reject(plugin, "named-only (auto=False): request explicitly by name")
                continue
            if plugin.name in exc:
                reject(plugin, "excluded by name")
                continue
            missing = [cap for cap in plugin.requires if not data.has(cap)]
            if missing:
                reject(plugin, f"missing capability: {', '.join(sorted(missing))}")
                continue
            if data.plt_cnt_cfg is None:
                reject(plugin, "no plot signature (plt_cnt_cfg missing)")
                continue
            result = plugin.match.matches_result(data.plt_cnt_cfg, plugin.name, override=False)
            if not result.overall:
                failed = "; ".join(
                    line.strip() for line in result.matches_info.splitlines()[1:]
                ).replace("\t", " ")
                reject(plugin, f"shape filter mismatch: {failed}")
                continue
            matched.append(plugin)

        # Resolve each chart type to one implementation.
        by_name: dict[str, list[PlotPlugin]] = {}
        for plugin in matched:
            by_name.setdefault(plugin.name, []).append(plugin)
        picked_plugins: list[PlotPlugin] = []
        for impls in by_name.values():
            preferred = [p for p in impls if p.backend == backend] if backend else []
            pool = preferred or impls
            winner = max(pool, key=lambda p: (p.priority, p.backend))
            picked_plugins.append(winner)
            for plugin in impls:
                if plugin is winner:
                    continue
                if backend and winner.backend == backend and plugin.backend != backend:
                    why = f"backend {backend!r} preferred over {plugin.backend!r}"
                else:
                    why = (
                        f"lower priority ({plugin.priority}) than {winner.backend!r} "
                        f"implementation (priority={winner.priority})"
                    )
                reject(plugin, f"superseded for chart type {plugin.name!r}: {why}")

        picked_plugins.sort(key=lambda p: (-p.priority, p.name))
        chosen = [
            PluginDecision(p.name, p.backend, True, f"chosen (priority={p.priority})", p)
            for p in picked_plugins
        ]
        return tuple(chosen + rejected)

    def render(
        self,
        data: BenchData,
        *,
        include: Iterable[str] | None = None,
        exclude: Iterable[str] | None = None,
        backend: str | None = None,
        only: str | None = None,
        strict: bool = False,
    ) -> tuple[tuple[str, pn.viewable.Viewable], ...]:
        """Run every selected plugin, returning (name, pane) pairs in priority order.

        With strict=False (default) a render exception is caught and replaced with a
        visible error pane so one broken plugin doesn't kill the report. strict=True
        re-raises the first failure — intended for development."""
        plugins = self.select(data, include=include, exclude=exclude, backend=backend, only=only)
        out: list[tuple[str, pn.viewable.Viewable]] = []
        for plugin in plugins:
            try:
                pane = plugin.render(data)
            except Exception as exc:  # pylint: disable=broad-exception-caught
                if strict:
                    raise
                log.exception("Plugin %r raised during render", plugin.name)
                pane = _render_error_pane(plugin.name, exc)
            if pane is not None:
                out.append((plugin.name, pane))
        return tuple(out)


_REGISTRY = PluginRegistry()


def get_registry() -> PluginRegistry:
    return _REGISTRY


def register_plugin(plugin: PlotPlugin) -> PlotPlugin:
    _REGISTRY.register(plugin)
    return plugin


def unregister_plugin(name: str, backend: str | None = None) -> None:
    _REGISTRY.unregister(name, backend)
