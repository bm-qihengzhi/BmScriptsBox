"""
Copyright (c) 2026 綦恒智
Email: bmscriptsbox@163.com
SPDX-License-Identifier: MIT
SPDX-License-Identifier: LicenseRef-Commons-Clause
"""
import os
import subprocess

from PySide6.QtCore import QObject, QTimer, Signal
from PySide6.QtWidgets import QSystemTrayIcon

from xsideui import tr

from app.utils import BM_LOG, BmNotify, BmTools


class MainPresenter(QObject):
    """主程序 Presenter：窗口唤醒、快捷键、托盘与更新。"""

    show_window = Signal()
    activate_search = Signal()
    hide_window = Signal()
    request_notify = Signal(tuple)
    show_login = Signal()
    stop_login = Signal()
    show_update = Signal(dict)
    login_window = Signal()

    def __init__(self):
        super().__init__()
        self._work_manager = None
        self._hotkey_workers = {}
        self._text_menu_widget = None

    def start(self):
        QTimer.singleShot(0, self._init_work_manager)

    def _init_work_manager(self):
        from app.works.work_manager import WorkerManager
        self._work_manager = WorkerManager()
        self._work_manager.activated.connect(self._on_activate)
        self._work_manager.update_found.connect(self._on_update_found)
        self._work_manager.notify_requested.connect(self._on_notify_requested)
        self._work_manager.hotkey_triggered.connect(self._on_hotkey_triggered)
        self._work_manager.fast_copy_triggered.connect(
            self._on_fast_copy_triggered)
        self._work_manager.context_menu_triggered.connect(self._hide_window)
        QTimer.singleShot(0, self._work_manager.start_core_works)
        QTimer.singleShot(3000, self._work_manager.start_delay_works)

    def _hide_window(self, *args):
        self.hide_window.emit()

    def _on_update_found(self, data: dict):
        self.show_update.emit(data)

    def _on_notify_requested(self, data):
        self.request_notify.emit(data)

    def _on_activate(self):
        self.activate_search.emit()

    def _on_hotkey_triggered(self, hotkey_info):
        if not hotkey_info:
            return
        self.hide_window.emit()
        try:
            from app.works import ExecuteScriptFromHotkeyWork
            worker = ExecuteScriptFromHotkeyWork(hotkey_info.id)
            worker.execute_script_signal.connect(self._handle_execute_result)
            worker.finished.connect(
                lambda sid=hotkey_info.id: self._hotkey_workers.pop(sid, None))
            self._hotkey_workers[hotkey_info.id] = worker
            worker.start()
        except Exception as exc:
            BM_LOG.error(str(exc))
            self._handle_execute_result(
                {'status': False, 'message': str(exc)})

    def _handle_execute_result(self, msg: dict):
        if not msg.get('status'):
            BmNotify().show_error_notify(msg.get('message'))
        else:
            BmNotify().show_info_notify(tr("Running script"))

    def _on_fast_copy_triggered(self, text: str, error: str):
        if error:
            BmNotify().show_error_notify(tr("Failed to start the Super Copy panel"))
            return
        from app.view.fast_text_ui.fast_text_win_menu import FastTextMenu
        if (not hasattr(self, '_text_menu_widget')
                or not self._text_menu_widget
                or self._text_menu_widget.isHidden()):
            if getattr(self, '_text_menu_widget', None):
                self._text_menu_widget.close()
            self._text_menu_widget = FastTextMenu()
        self.hide_window.emit()
        self._text_menu_widget.set_clipboard_text(text)
        self._text_menu_widget.setup_list_items()
        self._text_menu_widget.show()
        self._text_menu_widget.activateWindow()

    def on_tray_activated(self, reason: QSystemTrayIcon.ActivationReason):
        if reason in (QSystemTrayIcon.DoubleClick, QSystemTrayIcon.Trigger):
            self.activate_search.emit()

    def on_tray_quit(self):
        self.shutdown()

    def shutdown(self):
        if self._work_manager:
            self._work_manager.stop_all()

    def start_update(self, save_dir: str):
        if not save_dir:
            return
        base_path = BmTools.get_root_path()
        update_path = base_path / "update.ps1"
        cmd = [
            'powershell.exe',
            '-ExecutionPolicy', 'Bypass',
            '-File', str(update_path),
            "bmscriptsboxw",
            save_dir,
            str(base_path),
            '1',
        ]
        subprocess.Popen(
            cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            creationflags=(subprocess.CREATE_NO_WINDOW
                           if os.name == 'nt' else 0))
