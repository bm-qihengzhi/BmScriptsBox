"""
Copyright (c) 2026 綦恒智
Email: bmscriptsbox@163.com
SPDX-License-Identifier: MIT
SPDX-License-Identifier: LicenseRef-Commons-Clause
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
        scripts = self.db.get_all_scripts()
        ProjectGlobal.safe_set('SCRIPTS', scripts)
        return sorted(
            [s for s in scripts if s and s.triggers_schema['shortcut'].get('enabled')],
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
        """保存快捷键（校验 → 试注册 → 写库 → reload，失败回滚）"""
        hotkey_key = (hotkey_key or '').strip()
        if not hotkey_key:
            raise ValueError("快捷键不能为空")
        if re.search(r'[\u4e00-\u9fa5]', hotkey_key):
            raise ValueError("快捷键不能包含中文")
        self._assert_registerable(hotkey_key)

        prev = self.db.get_script_by_id(script_id)
        prev_key = prev.hotkey if prev else None

        if overwrite:
            conflict = self.find_conflict(script_id, hotkey_key)
            if conflict:
                self.db.update_status(conflict.id, 'hotkey', None)
        self.db.update_status(script_id, 'hotkey', hotkey_key)

        try:
            self.hotkey_manager.reload_hotkeys()
        except Exception:
            # 注册失败：回滚数据库并尽力恢复旧热键
            self.db.update_status(script_id, 'hotkey', prev_key)
            try:
                self.hotkey_manager.reload_hotkeys()
            except Exception:
                pass
            raise

    @staticmethod
    def _assert_registerable(hotkey_key: str) -> None:
        """用真实 add/remove 预检组合键是否可注册（避免小键盘命名差异被误判）"""
        import keyboard as kb
        hook = None
        try:
            hook = kb.add_hotkey(hotkey_key, lambda: None, suppress=False)
        except Exception as e:
            raise ValueError(f"无法识别的快捷键: {hotkey_key}") from e
        finally:
            if hook is not None:
                try:
                    kb.remove_hotkey(hook)
                except Exception:
                    pass

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
