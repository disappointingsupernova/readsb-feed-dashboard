"""Plugin system — discover and load user plugins from a plugins directory."""

import importlib.util
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Optional


PLUGIN_DIRS = [
    Path("/opt/readsb-feed-dashboard/plugins"),
    Path.home() / ".config" / "readsb-feed-dashboard" / "plugins",
    Path("/etc/readsb-feed-dashboard/plugins"),
]


@dataclass
class Plugin:
    """A loaded plugin."""

    name: str
    module: Any
    path: Path


@dataclass
class PluginRegistry:
    """Registry of loaded plugins and their hooks."""

    plugins: list[Plugin] = field(default_factory=list)
    _panel_hooks: list[Callable] = field(default_factory=list)
    _collector_hooks: list[Callable] = field(default_factory=list)
    _alert_hooks: list[Callable] = field(default_factory=list)

    def register_panel(self, func: Callable) -> None:
        """Register a function that returns a Rich renderable panel."""
        self._panel_hooks.append(func)

    def register_collector(self, func: Callable) -> None:
        """Register a function called each collection cycle with feed data."""
        self._collector_hooks.append(func)

    def register_alert_handler(self, func: Callable) -> None:
        """Register a function called when alerts fire."""
        self._alert_hooks.append(func)

    def get_panels(self, **kwargs) -> list:
        """Call all panel hooks and return their renderables."""
        panels = []
        for hook in self._panel_hooks:
            try:
                result = hook(**kwargs)
                if result is not None:
                    panels.append(result)
            except Exception:
                pass
        return panels

    def notify_collectors(self, **kwargs) -> None:
        """Call all collector hooks."""
        for hook in self._collector_hooks:
            try:
                hook(**kwargs)
            except Exception:
                pass

    def notify_alerts(self, alerts: list) -> None:
        """Call all alert handler hooks."""
        for hook in self._alert_hooks:
            try:
                hook(alerts)
            except Exception:
                pass


# Global registry
_registry = PluginRegistry()


def get_registry() -> PluginRegistry:
    """Get the global plugin registry."""
    return _registry


def discover_and_load_plugins(extra_dirs: Optional[list[str]] = None) -> int:
    """Discover and load all plugins from plugin directories.

    Returns the number of plugins loaded.

    Plugins are Python files (*.py) in the plugin directories.
    Each plugin should define a `register(registry)` function that
    registers its hooks with the PluginRegistry.
    """
    global _registry
    dirs = list(PLUGIN_DIRS)
    if extra_dirs:
        dirs.extend(Path(d) for d in extra_dirs)

    loaded = 0
    for plugin_dir in dirs:
        if not plugin_dir.is_dir():
            continue

        for py_file in sorted(plugin_dir.glob("*.py")):
            if py_file.name.startswith("_"):
                continue

            try:
                plugin = _load_plugin(py_file)
                if plugin:
                    _registry.plugins.append(plugin)
                    loaded += 1
            except Exception:
                pass  # Skip broken plugins silently

    return loaded


def _load_plugin(path: Path) -> Optional[Plugin]:
    """Load a single plugin file."""
    module_name = f"readsb_dashboard_plugin_{path.stem}"

    spec = importlib.util.spec_from_file_location(module_name, path)
    if spec is None or spec.loader is None:
        return None

    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)

    # Call register() if it exists
    register_func = getattr(module, "register", None)
    if callable(register_func):
        register_func(_registry)

    return Plugin(name=path.stem, module=module, path=path)
