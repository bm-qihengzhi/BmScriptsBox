"""
Copyright (c) 2026 綦恒智
Email: bmscriptsbox@163.com
SPDX-License-Identifier: AGPL-3.0
"""
import re
from typing import List, Optional


from app.data import ProjectGlobal, ScriptDatabase, ScriptEntity
from app.servers.monitor import HotkeyManager


class HotkeyModel:
    """热键数据层 - 负责数据操作"""

    def __init__(self):
        self.db = ScriptDatabase()
        self.hotkey_manager = HotkeyManager()

    def load_scripts(self) -> List[ScriptEntity]:
        """加载所有支持热键排序后的脚本"""
        ProjectGlobal.SCRIPTS = self.db.get_all_scripts()
        return sorted(
            [s for s in ProjectGlobal.SCRIPTS if s and s.triggers_schema['shortcut'].get('enabled')],
            key=lambda s: s.hotkey or '',
            reverse=True  # True 排在前面
        )


    def search_scripts(self, keyword: str) -> List[ScriptEntity]:
        """搜索脚本"""
        all_scripts = self.load_scripts()
        if not keyword:
            return all_scripts

        keyword = keyword.lower()
        return [
            s for s in all_scripts
            if keyword in (s.name or "").lower() or keyword in (s.hotkey or "").lower()
        ]

    def find_conflict(self, script_id: str, hotkey_key: str):
        """查找快捷键冲突的脚本"""
        for s in self.db.get_all_scripts():
            if s.hotkey == hotkey_key and s.id != script_id:
                return s
        return None

    def save_hotkey(self, script_id: str, hotkey_key: str, overwrite: bool = False) -> None:
        """保存快捷键"""
        if re.search(r'[\u4e00-\u9fa5]', hotkey_key):
            raise ValueError("快捷键不能包含中文")
        if overwrite:
            conflict = self.find_conflict(script_id, hotkey_key)
            if conflict:
                self.db.update_status(conflict.id, 'hotkey', None)
        self.db.update_status(script_id, 'hotkey', hotkey_key)
        self.hotkey_manager.reload_hotkeys()

    def remove_hotkey(self, script_id: str) -> None:
        """删除快捷键"""
        self.db.update_status(script_id,'hotkey',None)
        self.hotkey_manager.reload_hotkeys()

    def toggle_status(self, script_id: str, status: bool) -> None:
        """切换脚本状态"""
        self.db.update_status(script_id, 'hotkey_active',status)
        self.hotkey_manager.reload_hotkeys()

    def get_script_by_id(self, script_id: str) -> Optional[ScriptEntity]:
        """根据ID获取脚本"""
        for script in self.load_scripts():
            if script.id == script_id:
                return script
        return None
