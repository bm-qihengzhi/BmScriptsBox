"""
Copyright (c) 2026 綦恒智
Email: bmscriptsbox@163.com
SPDX-License-Identifier: MIT
SPDX-License-Identifier: LicenseRef-Commons-Clause
"""
import ctypes
from pathlib import Path

from PySide6.QtCore import QObject, Signal

from xsideui import tr

from app.utils import BmError, BmTools, BM_LOG
from app.utils import BmNotify
from .context_model import ContextModel


class MenuPresenter(QObject):
    """右键菜单逻辑处理器"""

    # dict 会被转成 QVariantMap（键变字符串），level_map 的 int 键会全部失配，
    # 所以这里必须用 object 保持原样传递
    data_loaded = Signal(list, object)
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
            self.model.modify_menu_status(script_id, status, self._current_target)
        except Exception as e:
            text = str(e) if isinstance(e, BmError) else tr(
                "Update status failed: %1").replace("%1", str(e))
            self.notification.emit(text, "error")

    def on_move_up(self, script_id: str):
        """上移菜单项"""
        self._do_move(script_id, 'up')

    def on_move_down(self, script_id: str):
        """下移菜单项"""
        self._do_move(script_id, 'down')

    def on_move_top(self, script_id: str):
        """置顶菜单项（本层级分组内）"""
        self._do_move(script_id, 'top')

    def on_move_bottom(self, script_id: str):
        """置底菜单项（本层级分组内）"""
        self._do_move(script_id, 'bottom')

    def _do_move(self, script_id: str, direction: str):
        result = self.model.move_menu_item(script_id, direction, self._current_target)
        if result == 'ok':
            success_messages = {
                'up': tr("Moved up"),
                'down': tr("Moved down"),
                'top': tr("Moved to top"),
                'bottom': tr("Moved to bottom"),
            }
            self.notification.emit(success_messages.get(direction, tr("Moved")), "success")
            self.refresh_data()
            self.action_completed.emit("move", True, direction)
        elif result == 'first':
            if direction == 'top':
                self.notification.emit(tr("Already at the top of the group"), "warning")
            else:
                self.notification.emit(tr("The first row cannot move up"), "warning")
        elif result == 'last':
            if direction == 'bottom':
                self.notification.emit(tr("Already at the bottom of the group"), "warning")
            else:
                self.notification.emit(tr("The last row cannot move down"), "warning")
        elif result == 'boundary':
            self.notification.emit(tr("Cannot move across level-1 and level-2 groups"), "warning")
        else:
            self.notification.emit(tr("Menu item not found"), "error")

    def on_change_level(self, script_id: str, new_level: int):
        """改变菜单级别"""
        try:
            success = self.model.change_menu_level(script_id, new_level, self._current_target)
        except Exception as e:
            text = str(e) if isinstance(e, BmError) else tr(
                "Failed to change the menu level: %1").replace("%1", str(e))
            self.notification.emit(text, "error")
            return
        if success:
            level_text = tr("Level 1") if new_level == 1 else tr("Level 2")
            self.notification.emit((tr("Promoted to %1") if new_level == 1
                                else tr("Demoted to %1")).replace("%1", level_text),
                                  "success")
            self.refresh_data()
        else:
            self.notification.emit(tr("Failed to change the menu level"), "error")

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
            'register': ('RegisterContext.bat', tr("Register context menu")),
            'uninstall': ('UninstallContext.bat', tr("Unregister context menu")),
            'Switch': ('W11MenuStyleSwitch.bat', tr("Switch menu style")),
        }

        if action_data not in actions:
            return

        bat_file, message = actions[action_data]

        try:
            base_path = BmTools.get_root_path() / 'BmContext'
            cmd_path = base_path / bat_file

            if not cmd_path.exists():
                raise BmError('menu.batch.missing', path=str(cmd_path))


            # 使用 ctypes 调用 ShellExecute 以管理员权限运行
            ctypes.windll.shell32.ShellExecuteW(
                None,
                "runas",  # 以管理员权限运行
                str(cmd_path),
                None,  # 参数
                str(base_path),
                1  # 窗口显示状态
            )

            BmNotify().show_success_notify(tr("Operation succeeded"), in_window=True)

        except Exception as e:
            BM_LOG.error(f"{message}时发生错误: {str(e)}")
            BmNotify().show_error_notify(tr("Operation failed"), in_window=True)


