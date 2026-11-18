"""
Copyright (c) 2026 綦恒智
Email: bmscriptsbox@163.com
SPDX-License-Identifier: MIT
SPDX-License-Identifier: LicenseRef-Commons-Clause

兼容入口：主窗口已迁移到 app.view.shell.main_window。
"""
from app.view.shell.main_window import MainWindow

MainView = MainWindow

__all__ = ["MainView", "MainWindow"]
