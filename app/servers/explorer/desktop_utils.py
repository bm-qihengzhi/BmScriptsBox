"""
Copyright (c) 2026 綦恒智
Email: bmscriptsbox@163.com
SPDX-License-Identifier: AGPL-3.0
"""
import win32api
import win32gui

class DesktopMouseChecker:
    """检查鼠标是否在桌面"""
    DESKTOP_CLASSES = ["Progman", "WorkerW", "SysListView32"]

    @classmethod
    def is_mouse_on_desktop(cls):
        x, y = win32api.GetCursorPos()
        hwnd = win32gui.WindowFromPoint((x, y))
        class_name = win32gui.GetClassName(hwnd)
        if class_name in cls.DESKTOP_CLASSES:
            if class_name == "SysListView32":
                return cls._is_syslistview_on_desktop(hwnd)
        return False

    @staticmethod
    def _is_syslistview_on_desktop(hwnd):
        parent = win32gui.GetParent(hwnd)
        if not parent or win32gui.GetClassName(parent) != "SHELLDLL_DefView":
            return False
        gp = win32gui.GetParent(parent)
        return gp and win32gui.GetClassName(gp) in ["Progman", "WorkerW"]