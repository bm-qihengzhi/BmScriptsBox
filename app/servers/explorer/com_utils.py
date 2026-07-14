"""
Copyright (c) 2026 綦恒智
Email: bmscriptsbox@163.com
SPDX-License-Identifier: AGPL-3.0
"""
import contextlib

import pythoncom
import win32com.client
import win32gui


@contextlib.contextmanager
def com_context():
    """COM 上下文管理器，自动配对 CoInitialize / CoUninitialize"""
    pythoncom.CoInitialize()
    try:
        yield
    finally:
        pythoncom.CoUninitialize()


class COMManager:
    """COM环境管理工具"""

    @staticmethod
    def get_shell():
        pythoncom.CoInitialize()
        return win32com.client.Dispatch("Shell.Application")

    @staticmethod
    def get_active_window_text():
        return win32gui.GetWindowText(win32gui.GetForegroundWindow())