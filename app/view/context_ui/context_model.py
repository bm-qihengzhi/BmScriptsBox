"""
Copyright (c) 2026 綦恒智
Email: bmscriptsbox@163.com
SPDX-License-Identifier: MIT
SPDX-License-Identifier: LicenseRef-Commons-Clause
"""
import copy
import os
from typing import Dict, List

from app.data import ProjectGlobal
from app.servers.context import ContextManager
from app.utils import BmTools


class ContextModel:
    """右键菜单数据层"""

    def __init__(self):
        self.menu_manager = ContextManager()
        self.level_map = {1: "一级菜单", 2: "二级菜单"}
        self.index_map = {0: 'files', 1: 'directory', 2: 'background'}

    def load_menu_data(self) -> Dict:
        """加载菜单配置"""
        ProjectGlobal.MENU = self.menu_manager.load_config()
        return ProjectGlobal.MENU

    def get_menu_data_by_target(self, target: str) -> List[Dict]:
        """根据目标类型获取菜单数据（返回深拷贝，避免视图误改内存树）"""
        menu_data = []
        for menu in ProjectGlobal.MENU.get('menuItems', []):
            if menu.get('name') == '不忙脚本盒子':
                for child in menu.get('submenu', []) or []:
                    if target in (child.get('target', []) or []):
                        menu_data.append(child)
            elif (target in (menu.get('target', []) or [])
                  and 'scriptId' in menu and not menu.get('submenu')):
                menu_data.append(menu)

        result = copy.deepcopy(menu_data)
        for item in result:
            item['iconPath'] = self._resolve_icon_path(item.get('iconPath'))
        return result

    @staticmethod
    def _resolve_icon_path(icon_path: str) -> str:
        """相对路径以 BmContext 目录为基准解析为绝对路径（DLL 同规则），供 QIcon 使用"""
        if not icon_path or os.path.isabs(icon_path):
            return icon_path
        base = BmTools.get_root_path() / "BmContext"
        return os.path.normpath(os.path.join(str(base), icon_path))

    def modify_menu_status(self, script_id: str, status: bool, target: str = None) -> None:
        """修改菜单状态"""
        self.menu_manager.modify_menu_status(script_id, status, target)
        self.load_menu_data()

    def move_menu_item(self, script_id: str, direction: str, target: str) -> str:
        """移动菜单项，返回 ok | first | last | boundary | not_found"""
        result = self.menu_manager.move_menu_item(script_id, direction, target)
        if result == 'ok':
            self.load_menu_data()
        return result

    def change_menu_level(self, script_id: str, new_level: int, target: str) -> bool:
        """改变菜单级别"""
        success = self.menu_manager.change_menu_level(script_id, new_level, target)
        if success:
            self.load_menu_data()
        return success

    def get_target_by_index(self, index: int) -> str:
        """根据索引获取目标类型"""
        return self.index_map.get(index, 'files')
