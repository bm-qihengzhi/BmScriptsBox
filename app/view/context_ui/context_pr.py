"""
Copyright (c) 2026 綦恒智
Email: bmscriptsbox@163.com
SPDX-License-Identifier: AGPL-3.0
"""
import ctypes
from pathlib import Path

from PySide2.QtCore import QObject, Signal

from app.utils import BmTools, BM_LOG
from app.utils import BmNotify
from .context_model import ContextModel


class MenuPresenter(QObject):
    """右键菜单逻辑处理器"""

    data_loaded = Signal(list, dict)
    notification = Signal(str, str)
    show_context_menu = Signal(object, dict)
    action_completed = Signal(str, bool, str)

    def __init__(self):
        super().__init__()
        self.model = ContextModel()
        self._current_data = []
        self._current_target = 'files'
        self._level_map = self.model.level_map

    def initialize(self):
        """初始化"""
        self.model.load_menu_data()
        self.refresh_data()

    def on_search_type_changed(self, index: int):
        """搜索类型改变"""
        self._current_target = self.model.get_target_by_index(index)
        self.refresh_data()

    def on_status_changed(self, script_id: str, status: bool):
        """状态改变"""
        try:
            self.model.modify_menu_status(script_id, status)
        except Exception as e:
            self.notification.emit(f"修改状态失败: {str(e)}", "error")

    def on_move_up(self, row: int):
        """上移菜单项"""
        success = self.model.move_menu_item(row, 'up', self._current_target)
        if success:
            self.notification.emit("菜单上移成功", "success")
            self.refresh_data()
            self.action_completed.emit("move", True, "up")
        else:
            self.notification.emit("第一行无法上移", "warning")

    def on_move_down(self, row: int):
        """下移菜单项"""
        success = self.model.move_menu_item(row, 'down', self._current_target)
        if success:
            self.notification.emit("菜单下移成功", "success")
            self.refresh_data()
            self.action_completed.emit("move", True, "down")
        else:
            self.notification.emit("最后一行无法下移", "warning")

    def on_change_level(self, row: int, new_level: int):
        """改变菜单级别"""
        success = self.model.change_menu_level(row, new_level, self._current_target)
        if success:
            level_text = "一级" if new_level == 1 else "二级"
            self.notification.emit(f"已{'升' if new_level == 1 else '降'}为{level_text}菜单", "success")
            self.refresh_data()
        else:
            self.notification.emit("菜单级别变更失败", "error")

    def on_context_menu_requested(self, pos, row_data: dict):
        """请求显示上下文菜单"""
        self.show_context_menu.emit(pos, row_data)

    def refresh_data(self):
        """刷新数据"""
        self._current_data = self.model.get_menu_data_by_target(self._current_target)
        self.data_loaded.emit(self._current_data, self._level_map)


    def on_menu_action_triggered(self, action_data: str):
        """菜单操作触发"""

        actions = {
            'register': ('RegisterContext.bat', "注册右键"),
            'uninstall': ('UninstallContext.bat', "卸载右键")
        }

        if action_data not in actions:
            return

        bat_file, message = actions[action_data]

        try:
            base_path = BmTools.get_root_path() / 'BmContext'
            cmd_path = base_path / bat_file

            if not cmd_path.exists():
                raise FileNotFoundError(f"找不到批处理文件: {cmd_path}")


            # 使用 ctypes 调用 ShellExecute 以管理员权限运行
            ctypes.windll.shell32.ShellExecuteW(
                None,
                "runas",  # 以管理员权限运行
                str(cmd_path),
                None,  # 参数
                str(base_path),
                1  # 窗口显示状态
            )

            BmNotify().show_success_notify("操作成功", in_window=True)

        except Exception as e:
            BM_LOG.error(f"{message}时发生错误: {str(e)}")
            BmNotify().show_error_notify("操作失败", in_window=True)


