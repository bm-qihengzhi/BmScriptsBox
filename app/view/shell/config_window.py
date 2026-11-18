"""
Copyright (c) 2026 綦恒智
Email: bmscriptsbox@163.com
SPDX-License-Identifier: MIT
SPDX-License-Identifier: LicenseRef-Commons-Clause

配置中心窗口：独立普通窗口，占任务栏。
"""
import webbrowser

from PySide6.QtCore import QEvent, Qt, Signal
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import QApplication

from xsideui import XButtonVariant, XPushButton, XSize, XWidget, tr

from app.utils import BmTools
from app.view.config_center import ConfigCenter, NavId


class ConfigWindow(XWidget):
    launcher_requested = Signal()
    navigate_requested = Signal(str)
    switch_window_requested = Signal()

    def __init__(self, page_factories, action_handler, shell, size,
                 parent=None):
        super().__init__(
            title=tr('BmScriptsBox Config Center'),
            parent=parent,
            show_animation=True,
            show_duration=220,
            show_offset=8,
            auto_size_on_first_show=False,
            center_on_first_show=True,
        )
        self._shell = shell
        self.set_title(tr('Config Center'))
        self.hide_maximize_button()
        self._create_donate()
        self.set_logo(BmTools.get_logo_path())

        self.config_center = ConfigCenter(page_factories, action_handler)
        self.addWidget(self.config_center)
        self.config_center.launcher_requested.connect(
            self.launcher_requested.emit)
        self.config_center.navigate_requested.connect(
            self.navigate_requested.emit)

        self.resize(size)

        app = QApplication.instance()
        if app is not None:
            app.installEventFilter(self)
        self.search_shortcut = QShortcut(QKeySequence("Ctrl+F"), self)
        self.search_shortcut.activated.connect(self.launcher_requested.emit)
        self.switch_shortcut = QShortcut(QKeySequence(Qt.Key_Tab), self)
        self.switch_shortcut.setContext(Qt.WindowShortcut)
        self.switch_shortcut.setAutoRepeat(False)
        self.switch_shortcut.setEnabled(False)
        self.switch_shortcut.activated.connect(
            self.switch_window_requested.emit)

    # ---------- 展示 ----------

    def showEvent(self, event):
        super().showEvent(event)
        self.switch_shortcut.setEnabled(True)

    def hideEvent(self, event):
        self.switch_shortcut.setEnabled(False)
        super().hideEvent(event)

    def present(self):
        self.bring_to_front()

    def bring_to_front(self):
        if self._shell is not None:
            self._shell.bring_to_front(self)
            return
        if self.isMinimized():
            self.showNormal()
        self.show()
        self.raise_()
        self.activateWindow()

    def show_page(self, nav_id=None):
        self.config_center.show_page(nav_id)

    def current_nav_id(self):
        return self.config_center.current_nav_id()

    def last_nav_id(self):
        return self.config_center.last_nav_id()

    def set_account_status(self, status):
        self.config_center.set_account_status(status)

    def set_script_updates(self, has_updates):
        self.config_center.set_script_updates(has_updates)

    def retranslate(self):
        self.config_center.retranslate()

    def refresh_scripts(self):
        self.config_center.refresh_scripts()

    def open_wechat_push_page(self):
        if self._shell is not None:
            self._shell.show_config(NavId.SYS_PUSH)
            return
        self.show_page(NavId.SYS_PUSH)
        self.present()

    # ---------- 事件 ----------

    def eventFilter(self, obj, event):
        if (event.type() == QEvent.KeyPress
                and event.key() == Qt.Key_Escape
                and self.isActiveWindow()
                and QApplication.activeModalWidget() is None
                and QApplication.activePopupWidget() is None):
            self.launcher_requested.emit()
            return True
        return super().eventFilter(obj, event)

    # ---------- 标题栏 ----------



    def _create_donate(self):
        self.donate_button = XPushButton(tr("Donate"),
            variant=XButtonVariant.TEXT,size=XSize.SMALL)
        self.donate_button.clicked.connect(
            lambda: webbrowser.open_new_tab('https://www.bm-box.cn/donate'))
        self.add_title_bar_widget(self.donate_button)

    def shutdown(self):
        app = QApplication.instance()
        if app is not None:
            app.removeEventFilter(self)
        self.search_shortcut.setEnabled(False)
        self.config_center.shutdown()
