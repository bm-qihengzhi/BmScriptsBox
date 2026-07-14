"""
Copyright (c) 2026 綦恒智
Email: bmscriptsbox@163.com
SPDX-License-Identifier: AGPL-3.0
"""
from typing import List

from PySide2.QtCore import QObject, Signal

from .hotkey_model import HotkeyModel
from ...data import ScriptEntity


class HotkeyPresenter(QObject):
    """热键逻辑处理器 - 负责业务逻辑"""

    scripts_loaded = Signal(list)
    notification = Signal(str, bool)
    open_hotkey_window = Signal(str, str, str)

    def __init__(self):
        super().__init__()
        self.model = HotkeyModel()
        self._all_scripts: List[ScriptEntity] = []

    def load_scripts(self):
        """加载脚本数据"""
        # try:
        scripts = self.model.load_scripts()
        self._all_scripts = scripts
        self.scripts_loaded.emit(scripts)
        # except Exception as e:
        #     print(e)
        #     self.notification.emit(f"加载数据失败: {str(e)}", False)

    def search_scripts(self, keyword: str):
        """搜索脚本"""
        try:
            if not keyword:
                self.scripts_loaded.emit(self._all_scripts)
                return

            filtered = self.model.search_scripts(keyword)
            if not filtered:
                self.notification.emit("未搜索到任何脚本", False)
                return

            self.scripts_loaded.emit(filtered)
        except Exception as e:
            self.notification.emit(f"搜索失败: {str(e)}", False)

    def edit_hotkey(self, script_id: str):
        """请求编辑快捷键"""
        script = self.model.get_script_by_id(script_id)
        if script:
            self.open_hotkey_window.emit(script_id, script.hotkey or "", script.name)

    def remove_hotkey(self, script_id: str):
        """删除快捷键"""
        try:
            self.model.remove_hotkey(script_id)
            self.notification.emit("快捷键已清空", True)
            self.load_scripts()
        except Exception as e:
            self.notification.emit(f"删除快捷键失败: {str(e)}", False)

    def toggle_status(self, script_id: str, status: bool):
        """切换状态"""
        try:
            self.model.toggle_status(script_id, status)
        except Exception as e:
            self.notification.emit(f"切换状态失败: {str(e)}", False)

    def save_hotkey(self, script_id: str, hotkey_key: str):
        """保存快捷键（冲突自动覆盖）"""
        try:
            self.model.save_hotkey(script_id, hotkey_key, overwrite=True)
            self.notification.emit("快捷键设置成功", True)
            self.load_scripts()
        except Exception as e:
            self.notification.emit(str(e), False)

    def check_conflict(self, script_id: str, hotkey_key: str):
        """检查快捷键是否冲突，返回冲突脚本名称或 None"""
        conflict = self.model.find_conflict(script_id, hotkey_key)
        return conflict.name if conflict else None

    def get_script_by_row(self, row: int) -> ScriptEntity:
        """根据行号获取脚本"""
        if 0 <= row < len(self._all_scripts):
            return self._all_scripts[row]
        return None
