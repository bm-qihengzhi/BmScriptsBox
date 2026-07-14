"""
Copyright (c) 2026 綦恒智
Email: bmscriptsbox@163.com
SPDX-License-Identifier: AGPL-3.0
"""
import threading

from xsideui import XNotif


class BmNotify:
    """
    通知类
    """
    _instance = None
    _lock = threading.Lock()
    _main_window = None  # 存储主窗口对象的类变量

    def __new__(cls, *args, **kwargs):
        if not cls._instance:
            with cls._lock:
                if not cls._instance:
                    cls._instance = super().__new__(cls)
        return cls._instance

    @classmethod
    def initialize(cls, main_window):
        """在主窗口启动时调用，设置主窗口对象"""
        cls._main_window = main_window

    def show_info_notify(self, content: str, duration: int = 1000, show_close: bool = True, in_window: bool = False,
                         position=XNotif.Pos.BOTTOM_RIGHT):
        XNotif.info(text=content, in_window=in_window, show_close=show_close, position=position,
                           duration=duration, animated=True,parent=self._main_window)

    def show_success_notify(self, content: str, duration: int = 1000, show_close: bool = True, in_window: bool = False,
                            position=XNotif.Pos.BOTTOM_RIGHT):
        XNotif.success(text=content, in_window=in_window, show_close=show_close, position=position,
                              duration=duration, animated=True,parent=self._main_window)

    def show_error_notify(self, content: str, duration: int = 5000, show_close: bool = True, in_window: bool = False,
                          position=XNotif.Pos.BOTTOM_RIGHT):
        XNotif.error(text=content, in_window=in_window, show_close=show_close, position=position,
                            duration=duration,animated=True, parent=self._main_window)

    def show_warning_notify(self, content: str, duration: int = 3000, show_close: bool = True, in_window: bool = False,
                            position=XNotif.Pos.BOTTOM_RIGHT):
        XNotif.warning(text=content, in_window=in_window, show_close=show_close, position=position,
                              duration=duration, animated=True,parent=self._main_window)
