"""
Copyright (c) 2026 綦恒智
Email: bmscriptsbox@163.com
SPDX-License-Identifier: AGPL-3.0
"""
from typing import Dict, List

from app.data import ProjectGlobal
from app.utils import BM_LOG
from app.servers.context import ContextManager


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
        """根据目标类型获取菜单数据"""
        menu_data = []
        for parent_menu in ProjectGlobal.MENU.get('menuItems', []):
            if target in parent_menu.get('target', []):
                if not parent_menu.get('submenu') and parent_menu.get('name') != '不忙脚本盒子':
                    menu_data.append(parent_menu)
                else:
                    menu_data.extend(parent_menu.get('submenu', []))
        return menu_data

    def modify_menu_status(self, script_id: str, status: bool) -> None:
        """修改菜单状态"""
        self.menu_manager.modify_menu_status(script_id, status)

    def move_menu_item(self, current_index: int, direction: str, target: str) -> bool:
        """移动菜单项"""
        menu_data = self.get_menu_data_by_target(target)

        if direction == 'up' and current_index > 0:
            menu_data[current_index], menu_data[current_index - 1] = menu_data[current_index - 1], menu_data[current_index]
        elif direction == 'down' and current_index < len(menu_data) - 1:
            menu_data[current_index], menu_data[current_index + 1] = menu_data[current_index + 1], menu_data[current_index]
        else:
            return False

        return self._update_menu_config(menu_data, target)

    def change_menu_level(self, current_index: int, new_level: int, target: str) -> bool:
        """改变菜单级别"""
        menu_data = self.get_menu_data_by_target(target)
        data = menu_data[current_index]

        data['level'] = new_level
        if new_level == 1:
            data['father'] = "无"
        else:
            data['father'] = "不忙脚本盒子"
            if 'target' not in data:
                data['target'] = [target]

        return self._update_menu_config(menu_data, target)

    def search_menu_items(self, target: str, search_text: str) -> List[Dict]:
        """搜索菜单项"""
        menu_data = self.get_menu_data_by_target(target)
        if not search_text:
            return menu_data
        return [item for item in menu_data if search_text.lower() in item['name'].lower()]

    def get_target_by_index(self, index: int) -> str:
        """根据索引获取目标类型"""
        return self.index_map.get(index, 'files')

    def _update_menu_config(self, updated_data: List[Dict], target: str) -> bool:
        """更新菜单配置"""
        try:
            all_menus = ProjectGlobal.MENU.get("menuItems", [])
            promoted_ids = {item.get('scriptId') for item in updated_data if item.get('level') == 1}
            new_menus = []

            for menu in all_menus:
                if menu.get('name') == '不忙脚本盒子':
                    if promoted_ids:
                        sub = menu.get("submenu", [])
                        menu["submenu"] = [x for x in sub if x.get('scriptId') not in promoted_ids]
                    new_menus.append(menu)
                elif target in menu.get("target", []):
                    if menu.get('level') == 1:
                        for updated_item in updated_data:
                            if (updated_item.get('name') == menu.get('name') and
                                updated_item.get('level') == 1 and
                                target in updated_item.get("target", [])):
                                menu.update(updated_item)
                                new_menus.append(menu)
                                break
                        else:
                            new_menus.append(menu)
                    else:
                        new_menus.append(menu)
                else:
                    new_menus.append(menu)

            for updated_item in updated_data:
                if (updated_item.get('level') == 1 and
                    target in updated_item.get("target", []) and
                    updated_item.get('name') != '不忙脚本盒子'):
                    exists = any(m.get('name') == updated_item.get('name') and target in m.get("target", []) and m.get('level') == 1 for m in new_menus)
                    if not exists:
                        new_menus.append(updated_item)

            ProjectGlobal.MENU["menuItems"] = new_menus
            self.menu_manager.save_config(ProjectGlobal.MENU)
            return True
        except Exception as e:
            BM_LOG.error(f"更新菜单配置失败: {e}")
            return False
