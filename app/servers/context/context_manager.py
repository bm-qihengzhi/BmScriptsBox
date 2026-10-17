"""
Copyright (c) 2026 綦恒智
Email: bmscriptsbox@163.com
SPDX-License-Identifier: MIT
SPDX-License-Identifier: LicenseRef-Commons-Clause
"""
import json
import os
import tempfile
import threading
import time
from pathlib import Path
from typing import Dict, List, Optional

from app.data.toml_schemas import ContextMenuConfig
from app.utils import BmTools, BM_LOG

# 容器父项名称（一级菜单）
_CONTAINER_NAME = "不忙脚本盒子"

# 支持的右键目标类型（顺序固定）
_ALL_TARGETS = ["files", "directory", "background"]

# 当前配置结构版本；升级时用于驱动迁移
_SCHEMA_VERSION = 2

# 跨实例共享的配置读写锁（ContextManager 会被频繁新建）
_CONFIG_LOCK = threading.RLock()


class ContextManager:
    def __init__(self):
        self.config_path = BmTools.get_root_path() / "BmContext" / "BmContext.json"
        self._ensure_config_file()

    # --- 文件读写 ---

    def _ensure_config_file(self):
        """确保配置文件存在；已存在时按 schemaVersion 迁移旧结构"""
        with _CONFIG_LOCK:
            try:
                if not self.config_path.exists():
                    initial_config = {
                        "schemaVersion": _SCHEMA_VERSION,
                        "menuItems": [
                            {
                                "name": _CONTAINER_NAME,
                                "father": "无",
                                "level": 1,
                                "target": list(_ALL_TARGETS),
                                "iconPath": "ico\\logo.png",
                                "submenu": []
                            }
                        ]
                    }
                    self._atomic_write(initial_config)
                    return

                try:
                    config = self.load_config(strict=True)
                except Exception as e:
                    BM_LOG.critical(f"跳过菜单结构迁移（配置不可读）: {e}")
                    return
                if self._migrate_config(config):
                    self._atomic_write(config)
            except Exception as e:
                BM_LOG.error(f"Error ensuring config file: {e}")

    def _migrate_config(self, config: Dict) -> bool:
        """按 schemaVersion 迁移配置结构；发生变更返回 True。

        历史结构：三个同名父项，各绑定单个 target。
        目标结构：单一父项（target 为并集），子项各自携带 target。
        """
        version = config.get("schemaVersion", 1)
        if not isinstance(version, int):
            version = 1
        if version >= _SCHEMA_VERSION:
            return False

        menu_items = config.setdefault("menuItems", [])
        containers = [m for m in menu_items if m.get("name") == _CONTAINER_NAME]

        if containers:
            base = containers[0]
            base.setdefault("submenu", [])

            # 容器必须覆盖全部支持的目标（保证父项始终可命中），附加未知目标值
            known = list(_ALL_TARGETS)
            extra: List[str] = []
            for container in containers:
                for t in container.get("target", []) or []:
                    if t not in known and t not in extra:
                        extra.append(t)
            base["target"] = known + extra

            # submenu 顺序拼接并按 (scriptId, target) 去重
            merged: List[Dict] = []
            seen = set()
            for container in containers:
                for child in container.get("submenu", []) or []:
                    key = (str(child.get("scriptId")),
                           tuple(child.get("target", []) or []))
                    if key in seen:
                        continue
                    seen.add(key)
                    merged.append(child)
            base["submenu"] = merged

            removed = {id(c) for c in containers[1:]}
            config["menuItems"] = [m for m in menu_items if id(m) not in removed]

        config["schemaVersion"] = _SCHEMA_VERSION
        return True

    def load_config(self, strict: bool = False) -> Dict:
        """加载菜单配置。

        strict=False（读路径）：文件损坏时记录日志并返回空配置，不修改原文件。
        strict=True（写路径）：文件损坏时抛出异常，避免把损坏文件覆盖为空白。
        """
        with _CONFIG_LOCK:
            try:
                with open(self.config_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                if not isinstance(data, dict) or not isinstance(data.get("menuItems"), list):
                    raise ValueError("菜单配置结构非法（缺少 menuItems 列表）")
                return data
            except Exception as e:
                if strict:
                    raise RuntimeError(f"BmContext.json 已损坏，已阻止写入以防覆盖: {e}")
                BM_LOG.critical(f"加载菜单配置失败（返回空配置，未覆盖文件）: {e}")
                return {"menuItems": []}

    def save_config(self, config: Dict) -> bool:
        """保存菜单配置（原子替换）"""
        with _CONFIG_LOCK:
            try:
                config.setdefault("schemaVersion", _SCHEMA_VERSION)
                self._atomic_write(config)
                return True
            except Exception as e:
                BM_LOG.error(f"保存菜单配置失败: {e}")
                return False

    def _atomic_write(self, config: Dict):
        """写同目录临时文件后原子替换，避免写入中断损坏配置"""
        self.config_path.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp_path = tempfile.mkstemp(
            prefix=".BmContext_", suffix=".tmp", dir=str(self.config_path.parent))
        try:
            with os.fdopen(fd, 'w', encoding='utf-8') as f:
                json.dump(config, f, indent=4, ensure_ascii=False)
            last_err = None
            for attempt in range(5):
                try:
                    os.replace(tmp_path, self.config_path)
                    return
                except PermissionError as e:  # 可能被 DLL 短暂占用
                    last_err = e
                    time.sleep(0.1 * (attempt + 1))
            raise last_err if last_err else OSError("写入配置失败")
        finally:
            if os.path.exists(tmp_path):
                try:
                    os.remove(tmp_path)
                except OSError:
                    pass

    # --- 树结构辅助 ---

    @staticmethod
    def _find_container(config: Dict) -> Optional[Dict]:
        """查找唯一的容器父项（不忙脚本盒子）"""
        for menu in config.get("menuItems", []):
            if menu.get("name") == _CONTAINER_NAME:
                menu.setdefault("submenu", [])
                return menu
        return None

    @staticmethod
    def _make_container() -> Dict:
        return {
            "name": _CONTAINER_NAME,
            "father": "无",
            "level": 1,
            "target": list(_ALL_TARGETS),
            "iconPath": "ico\\logo.png",
            "submenu": []
        }

    @staticmethod
    def _is_top_item(menu: Dict) -> bool:
        """顶层提升项：有 scriptId、非容器、无 submenu"""
        return ("scriptId" in menu
                and menu.get("name") != _CONTAINER_NAME
                and not menu.get("submenu"))

    @classmethod
    def _visible_refs(cls, config: Dict, target: str) -> List[Dict]:
        """按可见顺序产出该 target 下的菜单项引用。

        与视图 get_menu_data_by_target 顺序一致：
        容器贡献其「自身 target 命中」的子项；顶层提升项贡献自身。
        """
        refs = []
        for top_index, menu in enumerate(config.get("menuItems", [])):
            if menu.get("name") == _CONTAINER_NAME:
                sub = menu.setdefault("submenu", [])
                for sub_index, item in enumerate(sub):
                    if target in (item.get("target", []) or []):
                        refs.append({
                            "group": "sub", "item": item,
                            "submenu": sub, "sub_index": sub_index,
                            "top_index": None,
                        })
            elif target in (menu.get("target", []) or []) and cls._is_top_item(menu):
                refs.append({
                    "group": "top", "item": menu,
                    "submenu": None, "sub_index": None,
                    "top_index": top_index,
                })
        return refs

    @staticmethod
    def _remove_everywhere(config: Dict, script_id: str):
        """清理该 scriptId 在所有 target/层级下的残留项"""
        script_id = str(script_id)
        config["menuItems"] = [
            m for m in config.get("menuItems", []) if m.get("scriptId") != script_id]
        for menu in config["menuItems"]:
            if isinstance(menu.get("submenu"), list):
                menu["submenu"] = [
                    x for x in menu["submenu"] if x.get("scriptId") != script_id]

    def _to_menu_icon(self, icon: str) -> str:
        """把绝对图标路径转为相对 BmContext 目录，便于整体迁移"""
        if not icon:
            return icon
        p = Path(icon)
        if not p.is_absolute():
            return icon
        try:
            return os.path.relpath(str(p), str(self.config_path.parent))
        except ValueError:  # 跨盘符无法取相对路径
            return icon

    # --- 增删改 ---

    def add_script_menu(self, script_id: str, name: str, icon: str, language: str,
                        context_data: ContextMenuConfig) -> bool:
        script_id = str(script_id)
        with _CONFIG_LOCK:
            try:
                config = self.load_config(strict=True)
                if not icon:
                    icon = BmTools.get_language_icon_path(language)
                icon_path = self._to_menu_icon(icon)

                # 先全量清理旧残留，避免改 target 后留下陈旧项
                self._remove_everywhere(config, script_id)

                for target in context_data.targets:
                    menu_item = {
                        "name": name,
                        "father": _CONTAINER_NAME,
                        "level": 2,
                        "scriptId": script_id,
                        "iconPath": icon_path,
                        "target": [target],
                        "state": True,
                        "fileTypes": context_data.filters or []
                    }
                    container = self._find_container(config)
                    if container is None:
                        container = self._make_container()
                        config.setdefault("menuItems", []).append(container)
                    container.setdefault("submenu", []).append(menu_item)

                return self.save_config(config)
            except Exception as e:
                raise Exception(f"同步右键菜单失败: {str(e)}")

    def remove_script_menu(self, script_id: str) -> bool:
        """删除脚本菜单项（所有 target/层级）"""
        with _CONFIG_LOCK:
            try:
                config = self.load_config(strict=True)
                self._remove_everywhere(config, script_id)
                return self.save_config(config)
            except Exception as e:
                raise Exception(f"删除脚本菜单失败:{e}")

    def modify_menu_status(self, script_id: str, status: bool,
                           target: Optional[str] = None) -> bool:
        """修改菜单状态；target 为 None 时更新该脚本的所有菜单项"""
        script_id = str(script_id)
        with _CONFIG_LOCK:
            try:
                config = self.load_config(strict=True)
            except Exception as e:
                raise ValueError(f"修改菜单状态失败: {e}")

            candidates = []
            for menu in config.get("menuItems", []):
                if menu.get("scriptId") == script_id and (
                        target is None or target in menu.get("target", [])):
                    candidates.append(menu)
                for sub in menu.get("submenu", []) or []:
                    if sub.get("scriptId") == script_id and (
                            target is None or target in sub.get("target", [])):
                        candidates.append(sub)

            if not candidates:
                raise ValueError(f"未找到脚本菜单项: {script_id}")

            for item in candidates:
                item["state"] = status

            if not self.save_config(config):
                raise ValueError("修改菜单状态失败: 保存配置失败")
            return True

    def move_menu_item(self, script_id: str, direction: str, target: str) -> str:
        """移动菜单项。

        返回：ok | first | last | boundary | not_found
        boundary 表示相邻项属于不同分组（一级提升项 vs 二级子项），拒绝移动。
        """
        script_id = str(script_id)
        with _CONFIG_LOCK:
            config = self.load_config(strict=True)
            refs = self._visible_refs(config, target)
            index = next(
                (i for i, r in enumerate(refs) if r["item"].get("scriptId") == script_id),
                None)
            if index is None:
                return "not_found"

            if direction == "up":
                if index == 0:
                    return "first"
                cur, neighbor = refs[index], refs[index - 1]
            elif direction == "down":
                if index == len(refs) - 1:
                    return "last"
                cur, neighbor = refs[index], refs[index + 1]
            else:
                return "not_found"

            if cur["group"] != neighbor["group"]:
                return "boundary"

            if cur["group"] == "sub":
                sub = cur["submenu"]
                i, j = cur["sub_index"], neighbor["sub_index"]
                sub[i], sub[j] = sub[j], sub[i]
            else:
                self._swap_top_slots(config, target, cur["item"], neighbor["item"])

            self.save_config(config)
            return "ok"

    @staticmethod
    def _swap_top_slots(config: Dict, target: str, item_a: Dict, item_b: Dict):
        """在顶层提升项之间交换顺序，保持容器及其它项位置不变"""
        slots = [i for i, m in enumerate(config.get("menuItems", []))
                 if ContextManager._is_top_item(m) and target in (m.get("target", []) or [])]
        items = [config["menuItems"][i] for i in slots]
        try:
            ia = items.index(item_a)
            ib = items.index(item_b)
        except ValueError:
            return
        items[ia], items[ib] = items[ib], items[ia]
        for slot, menu in zip(slots, items):
            config["menuItems"][slot] = menu

    def change_menu_level(self, script_id: str, new_level: int, target: str) -> bool:
        """改变菜单级别：2→1 提升为顶层项；1→2 回挂到容器子项"""
        script_id = str(script_id)
        with _CONFIG_LOCK:
            config = self.load_config(strict=True)
            refs = self._visible_refs(config, target)
            ref = next(
                (r for r in refs if r["item"].get("scriptId") == script_id),
                None)
            if ref is None:
                raise ValueError(f"未找到菜单项: {script_id}")

            item = ref["item"]

            if new_level == 1:
                if ref["group"] == "top":
                    return True
                ref["submenu"].pop(ref["sub_index"])
                item["level"] = 1
                item["father"] = "无"
                item["target"] = item.get("target") or [target]
                container_index = next(
                    (i for i, m in enumerate(config.get("menuItems", []))
                     if m.get("name") == _CONTAINER_NAME),
                    None)
                if container_index is None:
                    config.setdefault("menuItems", []).append(item)
                else:
                    config["menuItems"].insert(container_index + 1, item)
            else:
                if ref["group"] == "sub":
                    return True
                config["menuItems"] = [
                    m for m in config.get("menuItems", []) if m is not item]
                container = self._find_container(config)
                if container is None:
                    container = self._make_container()
                    config.setdefault("menuItems", []).append(container)
                item["level"] = 2
                item["father"] = _CONTAINER_NAME
                item["target"] = [target]
                container.setdefault("submenu", []).append(item)

            self.save_config(config)
            return True
