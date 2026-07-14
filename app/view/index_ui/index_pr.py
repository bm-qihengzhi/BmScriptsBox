"""
Copyright (c) 2026 綦恒智
Email: bmscriptsbox@163.com
SPDX-License-Identifier: AGPL-3.0
"""
import os
import subprocess

from PySide2.QtCore import QObject, Signal, QTimer
from PySide2.QtWidgets import QSystemTrayIcon

from app.utils import BmTools, BM_LOG, BmNotify


class MainPresenter(QObject):
    """主程序 Presenter - 处理所有业务逻辑"""

    show_window = Signal()
    hide_window = Signal()
    switch_page = Signal(int)
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
        """启动Presenter"""
        QTimer.singleShot(0, self._init_work_manager)

    def _init_work_manager(self):
        """初始化工作管理器"""
        from app.works.work_manager import WorkerManager
        self._work_manager = WorkerManager()
        self._work_manager.activated.connect(self._on_activate)
        self._work_manager.update_found.connect(self._on_update_found)
        self._work_manager.notify_requested.connect(self._on_notify_requested)
        self._work_manager.hotkey_triggered.connect(self._on_hotkey_triggered)
        self._work_manager.fast_copy_triggered.connect(self._on_fast_copy_triggered)
        self._work_manager.context_menu_triggered.connect(self._hide_window)
        QTimer.singleShot(0, self._work_manager.start_core_works)
        QTimer.singleShot(3000, self._work_manager.start_delay_works)

    def _hide_window(self, id, path):
        """隐藏窗口"""
        self.hide_window.emit()

    def _on_update_found(self, data: dict):
        """发现更新"""
        self.show_update.emit(data)

    def _on_notify_requested(self, data):
        """通知请求"""
        self.request_notify.emit(data)

    def _on_activate(self):
        self.show_window.emit()

    def _on_hotkey_triggered(self, hotkey_info):
        if not hotkey_info:
            return
        from app.data import ProjectGlobal
        with ProjectGlobal.RUNNING_SCRIPTS_LOCK:
            if hotkey_info.id in ProjectGlobal.RUNNING_SCRIPTS:
                BM_LOG.warning(f"脚本 {hotkey_info.id} 正在执行中，跳过重复触发")
                name = getattr(hotkey_info, 'name', hotkey_info.id)
                BmNotify().show_warning_notify(f"脚本「{name}」正在运行中，请等待完成")
                return
        self.hide_window.emit()
        try:
            from app.works import ExecuteScriptFromHotkeyWork
            worker = ExecuteScriptFromHotkeyWork(hotkey_info.id)
            worker.execute_script_signal.connect(self._handle_execute_result)
            worker.finished.connect(lambda sid=hotkey_info.id: self._hotkey_workers.pop(sid, None))
            self._hotkey_workers[hotkey_info.id] = worker
            worker.start()
        except Exception as e:
            BM_LOG.error(str(e))
            self._handle_execute_result({'status': False, 'message': str(e)})

    def _handle_execute_result(self, msg: dict):
        """处理脚本执行结果"""
        if not msg.get('status'):
            BmNotify().show_error_notify(msg.get('message'))
        else:
            BmNotify().show_info_notify("正在执行脚本")

    def _on_fast_copy_triggered(self, text: str, error:str):
        """超级复制触发"""
        if error:
            BmNotify().show_error_notify("极速复制面板启动失败")
        else:
            from app.view.fast_text_ui.fast_text_win_menu import FastTextMenu
            if not hasattr(self, '_text_menu_widget') or not self._text_menu_widget or self._text_menu_widget.isHidden():
                if hasattr(self, '_text_menu_widget') and self._text_menu_widget:
                    self._text_menu_widget.close()
                self._text_menu_widget = FastTextMenu()
            self.hide_window.emit()
            self._text_menu_widget.set_clipboard_text(text)
            self._text_menu_widget.setup_list_items()
            self._text_menu_widget.show()
            self._text_menu_widget.activateWindow()

    def on_nav_changed(self, item_id: str):
        """导航切换"""
        page_map = {
            "code": 0, "mouse": 1, "keyboard": 2, 'copy': 3, "time": 4,
            "setting": 6, "me": 5, "market": 7,
        }
        if item_id == 'me':
            self.login_window.emit()
        else:
            self.switch_page.emit(page_map.get(item_id, 0))



    def on_tray_activated(self, reason: QSystemTrayIcon.ActivationReason):
        """托盘激活"""
        if reason in (QSystemTrayIcon.DoubleClick, QSystemTrayIcon.Trigger):
            self.show_window.emit()

    def on_tray_quit(self):
        """托盘退出"""
        self.shutdown()

    def shutdown(self):
        """关闭应用"""
        if self._work_manager:
            self._work_manager.stop_all()


    def start_update(self, save_dir: str):
        """开始更新"""
        if save_dir:
            base_path = BmTools.get_root_path()
            update_path = base_path / "update.ps1"
            cmd = [
                'powershell.exe',
                '-ExecutionPolicy', 'Bypass',
                '-File', str(update_path),
                "bmscriptsboxw",
                save_dir,
                str(base_path),
                '1'
            ]
            subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                              creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)





