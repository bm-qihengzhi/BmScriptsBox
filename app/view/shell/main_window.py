"""
Copyright (c) 2026 綦恒智
Email: bmscriptsbox@163.com
SPDX-License-Identifier: MIT
SPDX-License-Identifier: LicenseRef-Commons-Clause

兼容入口：应用壳已拆分到 app_shell / launcher_window / config_window。
"""
from .app_shell import ApplicationShell

MainWindow = ApplicationShell

__all__ = ["MainWindow", "ApplicationShell"]
