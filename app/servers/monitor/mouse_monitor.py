"""
Copyright (c) 2026 綦恒智
Email: bmscriptsbox@163.com
SPDX-License-Identifier: AGPL-3.0
"""
from PySide2.QtCore import QObject, Signal

from app.data import ProjectGlobal


class MouseMiddleMonitor(QObject):
    """
    鼠标中键激活主窗口监听器
    """
    middle_clicked = Signal()
    _instance = None

    def __new__(cls, *args, **kwargs):
        if not cls._instance:
            cls._instance = super(MouseMiddleMonitor, cls).__new__(cls)
        return cls._instance

    def __init__(self):
        if not hasattr(self, '_initialized'):
            super().__init__()
            self._initialized = True
            self.listener = None

    def start(self):
        """启动监听"""
        if self.listener is None or not self.listener.running:
            import pynput
            self._pynput = pynput
            self.listener = pynput.mouse.Listener(on_click=self._on_click)
            self.listener.start()

    def _on_click(self, x, y, button, pressed):
        if ProjectGlobal.CONFIG.get('mouse_middle') and \
           button == self._pynput.mouse.Button.middle and \
           pressed:
            self.middle_clicked.emit()

    def stop(self):
        """停止监听"""
        if self.listener:
            self.listener.stop()
            self.listener = None
            print("鼠标中键监听已停止")

_mouse_monitor_instance = None
def get_mouse_monitor():
    global _mouse_monitor_instance
    if _mouse_monitor_instance is None:
        _mouse_monitor_instance = MouseMiddleMonitor()
    return _mouse_monitor_instance