"""
Copyright (c) 2026 綦恒智
Email: bmscriptsbox@163.com
SPDX-License-Identifier: AGPL-3.0
"""
from PySide2.QtCore import QObject, Signal


class WorkerManager(QObject):
    activated = Signal()
    hotkey_triggered = Signal(object)
    notify_requested = Signal(tuple)
    fast_copy_triggered = Signal(str, str)
    update_found = Signal(dict)
    context_menu_triggered = Signal(str, str)

    def __init__(self):
        super().__init__()
        self.http_work = None
        self.fast_copy_menu_work = None
        self.update_banner_work = None
        self.update_soft_work = None
        self.scheduled_work = None


    def start_core_works(self):
        """统一启动后台核心线程（轻量，仅剪贴板监听）"""
        from app.data import ProjectGlobal, ConfigDatabase
        ProjectGlobal.CONFIG = ConfigDatabase().get_all()
        from app.servers.monitor import get_clipboard_monitor
        cm = get_clipboard_monitor()
        cm.start()
        cm.triggered.connect(self._on_fast_copy)


    def start_delay_works(self):
        """统一启动后台延迟线程（耗时服务，3秒后执行）"""
        from app.servers.monitor import get_mouse_monitor, get_double_monitor, get_hotkey_manager
        from .work_http import FlaskWork

        mm = get_mouse_monitor()
        mm.start()
        mm.middle_clicked.connect(self._on_activate)

        dm = get_double_monitor()
        dm.start()
        dm.double_key_triggered.connect(self._on_activate)

        hm = get_hotkey_manager()
        hm.start()
        hm.hotkey_triggered.connect(self._on_hotkey)

        self.http_work = FlaskWork()
        self.http_work.signals.show_notify.connect(self._on_notify)
        self.http_work.signals.execute_script_request.connect(lambda sid, jp: self.context_menu_triggered.emit(sid,jp))
        self.http_work.start()

        try:
            from app.cloud.works import BannerUpdateWork, CheckUpdateWork
            if BannerUpdateWork:
                self.update_banner_work = BannerUpdateWork()
                self.update_banner_work.start()
            if CheckUpdateWork:
                self.update_soft_work = CheckUpdateWork()
                self.update_soft_work.update_signal.connect(self._on_update_soft)
                self.update_soft_work.start()
        except ImportError:
            pass

    def stop_all(self):
        """统一关闭线程"""
        if self.http_work:
            self.http_work.stop()
        if hasattr(self, 'update_banner_work') and self.update_banner_work:
            self.update_banner_work.stop()
        if hasattr(self, 'update_soft_work') and self.update_soft_work:
            self.update_soft_work.stop()
        if self.scheduled_work:
            self.scheduled_work.stop()
        try:
            from app.servers.monitor import get_mouse_monitor, get_double_monitor, get_hotkey_manager, get_clipboard_monitor
            get_mouse_monitor().stop()
            get_double_monitor().stop()
            get_hotkey_manager().stop()
            get_clipboard_monitor().stop()
        except ImportError:
            pass

    def _on_update_soft(self,data:dict):
        """软件更新信号"""
        self.update_found.emit(data)

    def _on_fast_copy(self, text: str, error: str):  # 增加 error 参数
        """极速复制信号"""
        self.fast_copy_triggered.emit(text, error)


    def _on_activate(self):
        """激活窗口信号"""
        self.activated.emit()

    def _on_hotkey(self, hotkey_info):
        """快捷键执行信号"""
        self.hotkey_triggered.emit(hotkey_info)

    def _on_notify(self, notify_info:tuple):
        """外部通知信号"""
        self.notify_requested.emit(notify_info)
