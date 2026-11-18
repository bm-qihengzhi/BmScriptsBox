"""
Copyright (c) 2026 綦恒智
Email: bmscriptsbox@163.com
SPDX-License-Identifier: MIT
SPDX-License-Identifier: LicenseRef-Commons-Clause
"""
from .app_shell import ApplicationShell
from .config_window import ConfigWindow
from .launcher_window import LauncherWindow

MainWindow = ApplicationShell

__all__ = [
    "ApplicationShell",
    "LauncherWindow",
    "ConfigWindow",
    "MainWindow",
]
