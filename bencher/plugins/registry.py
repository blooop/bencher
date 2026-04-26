from __future__ import annotations

import logging
import traceback
from importlib import metadata
from typing import Iterable, Optional

import panel as pn

from bencher.plugins.bench_data import BenchData
from bencher.plugins.plugin import PlotPlugin

ENTRY_POINT_GROUP = "bencher.plot_plugins"

log = logging.getLogger(__name__)


def _render_error_pane(plugin_name: str, exc: BaseException) -> pn.viewable.Viewable:
    tb = "".join(traceback.format_exception(type(exc), exc, exc.__traceback__))
    body = f"### Plugin error: `{plugin_name}`\n\n```\n{tb}\n```"
    return pn.pane.Markdown(body, sizing_mode="stretch_width")


class PluginRegistry:
    """In-process registry of plot plugins.

    Built-in chart types and third-party plugins go through the same path. Registration
    by `name` is idempotent — re-registering with the same name replaces the prior entry,
    which is the documented override mechanism (a user-supplied plugin replaces a built-in
    by sharing its name)."""

    def __init__(self) -> None:
        self._plugins: dict[str, PlotPlugin] = {}
        self._entry_points_loaded = False

    def register(self, plugin: PlotPlugin) -> None:
        if not isinstance(plugin.name, str) or not plugin.name:
            raise ValueError("Plugin must have a non-empty string name")
        self._plugins[plugin.name] = plugin

    def unregister(self, name: str) -> None:
        self._plugins.pop(name, None)

    def clear(self) -> None:
        self._plugins.clear()
        self._entry_points_loaded = False

    def mark_entry_points_loaded(self) -> None:
        """Skip the entry-point scan on next lookup. Test-only helper."""
        self._entry_points_loaded = True

    def get(self, name: str) -> Optional[PlotPlugin]:
        self._ensure_entry_points_loaded()
        return self._plugins.get(name)

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
            except Exception as exc:  # pylint: disable=broad-exception-caught
                log.warning("Skipping plugin entry-point %r: %s", ep.name, exc)
                continue
            self._register_loaded(ep.name, obj)

    def _register_loaded(self, ep_name: str, obj) -> None:
        # Entry points may resolve to a single plugin instance, a plugin class (no-arg
        # constructor), or a callable returning an iterable of plugins. Accept all three.
        if callable(obj) and not hasattr(obj, "render"):
            try:
                produced = obj()
            except Exception as exc:  # pylint: disable=broad-exception-caught
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
        include: Optional[Iterable[str]] = None,
        exclude: Optional[Iterable[str]] = None,
        backend: Optional[str] = None,
        only: Optional[str] = None,
    ) -> tuple[PlotPlugin, ...]:
        """Return plugins matching `data`, ordered by descending priority then name.

        - `only` short-circuits to a single named plugin (no match-filter check; explicit
          opt-in by name implies the user knows what they want).
        - `include` / `exclude` filter the candidate set by name.
        - `backend` restricts to plugins in a single namespace.
        """
        if only is not None:
            picked = self.get(only)
            return (picked,) if picked is not None else ()

        candidates = list(self.all())
        if include is not None:
            inc = set(include)
            candidates = [p for p in candidates if p.name in inc]
        if exclude is not None:
            exc = set(exclude)
            candidates = [p for p in candidates if p.name not in exc]
        if backend is not None:
            candidates = [p for p in candidates if p.backend == backend]

        matched: list[PlotPlugin] = []
        for plugin in candidates:
            if not all(data.has(cap) for cap in plugin.requires):
                continue
            if data.plt_cnt_cfg is None:
                continue
            result = plugin.match.matches_result(data.plt_cnt_cfg, plugin.name, override=False)
            if result.overall:
                matched.append(plugin)

        matched.sort(key=lambda p: (-p.priority, p.name))
        return tuple(matched)

    def render(
        self,
        data: BenchData,
        *,
        include: Optional[Iterable[str]] = None,
        exclude: Optional[Iterable[str]] = None,
        backend: Optional[str] = None,
        only: Optional[str] = None,
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


def unregister_plugin(name: str) -> None:
    _REGISTRY.unregister(name)
