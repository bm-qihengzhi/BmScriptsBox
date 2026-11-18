"""
Copyright (c) 2026 綦恒智
Email: bmscriptsbox@163.com
SPDX-License-Identifier: MIT
SPDX-License-Identifier: LicenseRef-Commons-Clause

启动器容器：搜索面板 + 脚本数据桥接。
"""

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QApplication, QVBoxLayout, QWidget

from xsideui import XNotif, tr

from app.servers.launcher.service import LauncherService
from app.utils import BM_LOG, BmNotify
from app.view.palette_ui.search_panel import SearchPanel


class LauncherView(QWidget):
    navigate_requested = Signal(str)

    def __init__(self, script_presenter, market_catalog=None, parent=None):
        super().__init__(parent)
        self._script_presenter = script_presenter
        self._scripts_cache = []

        self.service = LauncherService(self)
        self.search_panel = SearchPanel(self.service, market_catalog)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(self.search_panel)

        self.search_panel.item_activated.connect(self._on_item_activated)
        self.search_panel.navigate_requested.connect(
            self.navigate_requested.emit)
        self.search_panel.script_uninstall_requested.connect(
            self._script_presenter.uninstall_script)
        self.search_panel.scripts_changed.connect(
            self._script_presenter.refresh_scripts)

        self._script_presenter.scripts_loaded.connect(self._on_scripts_loaded)

        self.service.start()
        self.search_panel.warm_icons(self.service.warmable_items())

    def activate(self, query="", focus=True):
        self.search_panel.activate(query, focus=focus)

    def focus_search(self):
        self.search_panel.focus_search()

    def set_scripts(self, scripts):
        self._scripts_cache = list(scripts or [])
        self.search_panel.set_scripts(self._scripts_cache)

    def _on_scripts_loaded(self, scripts):
        self.set_scripts(scripts)

    def _dismiss_launcher(self):
        window = self.window()
        if window is not None:
            window.hide()

    def _on_item_activated(self, item):
        try:
            if item.kind == "script":
                self._dismiss_launcher()
                self._script_presenter.execute_script(item.payload)
                return
            if item.kind == "script_input":
                payload = item.payload
                self._dismiss_launcher()
                self._script_presenter.execute_script(
                    payload["script_id"],
                    data=[payload["value"]],
                    source="search",
                )
                return
            if item.kind == "calculator":
                value = item.payload["value"]
                QApplication.clipboard().setText(value)
                BmNotify().show_success_notify(
                    content=tr("Result copied to clipboard: %s") % value,
                    duration=1500,
                    show_close=False,
                    in_window=True,
                )
                return
            error = self.service.launch(item)
            if error:
                self._notify_error(error)
                return
            self._dismiss_launcher()
        except Exception as exc:
            BM_LOG.error("启动器执行失败: %s" % exc)
            self._notify_error(str(exc))

    @staticmethod
    def _notify_error(message):
        try:
            XNotif.error(message)
        except Exception:
            BM_LOG.error(message)

    def shutdown(self):
        self.service.shutdown()
        self.search_panel.shutdown()
