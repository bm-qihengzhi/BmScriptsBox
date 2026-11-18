"""
Copyright (c) 2026 綦恒智
Email: bmscriptsbox@163.com
SPDX-License-Identifier: MIT
SPDX-License-Identifier: LicenseRef-Commons-Clause

搜索面板脚本索引、建议与右键菜单桥接。
"""
from PySide6.QtCore import QObject, Signal

from app.view.script_ui.script_actions import popup_script_menu


class ScriptSearchController(QObject):
    index_updated = Signal()
    search_keys_updated = Signal()

    def __init__(self, service, parent=None):
        super().__init__(parent)
        self._service = service
        self._script_map = {}
        self.loaded = False
        self._service.index_updated.connect(self.index_updated)
        self._service.search_keys_updated.connect(self.search_keys_updated)

    def set_scripts(self, scripts):
        script_list = list(scripts or [])
        self._script_map = {
            str(script.id): script for script in script_list}
        self.loaded = True
        self._service.refresh_scripts(script_list)

    def installed_ids(self):
        return set(self._script_map)

    def search(self, query):
        return self._service.search(query)

    def suggestions(self):
        return self._service.script_suggestions()

    def input_suggestions(self, query, include_low=True):
        return self._service.input_suggestions(
            query, include_low=include_low)

    def warmable_items(self):
        return self._service.warmable_items()

    def popup_menu(self, parent, item, position, on_run, on_uninstall,
                   on_changed):
        payload = item.payload
        if isinstance(payload, dict):
            script_id = payload.get("script_id")
        else:
            script_id = payload
        script = self._script_map.get(str(script_id))
        if script is None:
            return False
        popup_script_menu(
            parent,
            script,
            position,
            on_run=on_run,
            on_uninstall=lambda: on_uninstall(script.id),
            on_changed=on_changed,
        )
        return True
