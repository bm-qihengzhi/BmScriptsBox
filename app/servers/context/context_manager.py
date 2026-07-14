"""
Copyright (c) 2026 綦恒智
Email: bmscriptsbox@163.com
SPDX-License-Identifier: AGPL-3.0
"""
import json
from pathlib import Path
from typing import Dict

from app.data.toml_schemas import ContextMenuConfig
from app.utils import BmTools, BM_LOG


class ContextManager:
    def __init__(self):
        self.config_path = BmTools.get_root_path() / "BmContext" / "BmContext.json"
        self._ensure_config_file()

    def _ensure_config_file(self):
        """确保配置文件存在，如果不存在则创建初始配置"""
        try:
            if not self.config_path.exists():
                initial_config = {
                    "menuItems": [
                        {
                            "name": "不忙脚本盒子",
                            "father": "无",
                            "level": 1,
                            "target": ["files"],
                            "iconPath": "ico\\logo.png",
                            "submenu": []
                        },
                        {
                            "name": "不忙脚本盒子",
                            "father": "无",
                            "level": 1,
                            "target": ["directory"],
                            "iconPath": "ico\\logo.png",
                            "submenu": []
                        },
                        {
                            "name": "不忙脚本盒子",
                            "father": "无",
                            "level": 1,
                            "target": ["background"],
                            "iconPath": "ico\\logo.png",
                            "submenu": []
                        }
                    ]
                }
                with open(self.config_path, 'w', encoding='utf-8') as f:
                    json.dump(initial_config, f, indent=4, ensure_ascii=False)
        except Exception as e:
            BM_LOG.error(f"Error ensuring config file: {e}")

    def load_config(self) -> Dict:
        """加载菜单配置"""
        try:
            with open(self.config_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            BM_LOG.error(f"加载菜单配置失败: {e}")
            return {"menuItems": []}

    def save_config(self, config: Dict) -> bool:
        """保存菜单配置"""
        try:
            with open(self.config_path, 'w', encoding='utf-8') as f:
                json.dump(config, f, indent=4, ensure_ascii=False)
            return True
        except Exception as e:
            BM_LOG.error(f"保存菜单配置失败: {e}")
            return False

    def add_script_menu(self, script_id: str, name: str, icon: str, language: str,
                        context_data: ContextMenuConfig) -> bool:
        try:
            config = self.load_config()
            if not icon:
                icon = BmTools.get_language_icon_path(language)

            unmatched_targets = []

            config["menuItems"] = [x for x in config["menuItems"] if x.get("scriptId") != str(script_id)]

            for target in context_data.targets:
                menu_item = {
                    "name": name,
                    "father": '不忙脚本盒子',
                    "level": 2,
                    "scriptId": str(script_id),
                    "iconPath": icon,
                    "target": [target],
                    "state": True,
                    "fileTypes": context_data.filters or []
                }

                found_parent = False
                for parent_menu in config.get("menuItems", []):
                    # 匹配逻辑：target 是否在父菜单的支持列表里
                    if target in parent_menu.get("target", []):
                        parent_menu.setdefault("submenu", [])
                        # 高效去重并添加
                        parent_menu["submenu"] = [i for i in parent_menu["submenu"] if i.get("scriptId") != script_id]
                        parent_menu["submenu"].append(menu_item)
                        found_parent = True

                if not found_parent:
                    unmatched_targets.append(target)

            # 只要有任何 target 没匹配上，就在日志里记录，但不一定阻断流程
            if unmatched_targets:
                BM_LOG.warning(f"以下菜单目标未找到匹配父项: {unmatched_targets}")

            return self.save_config(config)

        except Exception as e:
            raise Exception(f"同步右键菜单失败: {str(e)}")


    def remove_script_menu(self, script_id: str) -> bool:
        """删除脚本菜单项"""
        try:
            config = self.load_config()
            for item in config["menuItems"]:
                if "submenu" in item:
                    item["submenu"] = [x for x in item["submenu"] if x.get("scriptId") != script_id]
            config["menuItems"] = [x for x in config["menuItems"] if x.get("scriptId") != script_id]
            return self.save_config(config)
        except Exception as e:
            raise Exception(f"删除脚本菜单失败:{e}")

    def modify_menu_status(self, script_id: str, status: bool) -> bool:
        """修改菜单状态"""
        try:
            config = self.load_config()
            for item in config["menuItems"]:
                if item.get("scriptId") == script_id:
                    item["state"] = status
                    return self.save_config(config)
                if "submenu" in item:
                    for subitem in item["submenu"]:
                        if subitem.get("scriptId") == script_id:
                            subitem["state"] = status
                            return self.save_config(config)
            raise Exception(f"没有找到脚本菜单项")
        except Exception as e:
            raise ValueError(f"修改菜单状态失败")



