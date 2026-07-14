__all__ = [
    "FlaskWork",
    "InstallLocalScriptWork",
    "UninstallScriptWork",
    "ExecuteScriptWork",
    "ExecuteScriptFromHotkeyWork",
    "ScheduledWork",
]

_import_map = {
    "FlaskWork": ".work_http",
    "InstallLocalScriptWork": ".script_work",
    "UninstallScriptWork": ".script_work",
    "ExecuteScriptWork": ".script_work",
    "ExecuteScriptFromHotkeyWork": ".script_work",
    "ScheduledWork": ".work_scheduled",
}

def __getattr__(name):
    if name in _import_map:
        import importlib
        return getattr(importlib.import_module(_import_map[name], __name__), name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")