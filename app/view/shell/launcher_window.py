"""
Copyright (c) 2026 綦恒智
Email: bmscriptsbox@163.com
SPDX-License-Identifier: MIT
SPDX-License-Identifier: LicenseRef-Commons-Clause

启动器窗口：独立普通窗口，占任务栏。
"""
from PySide6.QtCore import QEvent, Qt, Signal
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import (QAbstractSpinBox, QApplication, QComboBox,
                               QLineEdit, QPlainTextEdit, QTextEdit)

from xsideui import XWidget, tr

from app.utils import BmTools
from app.view.launcher.launcher_view import LauncherView


class LauncherWindow(XWidget):
    navigate_requested = Signal(str)
    switch_window_requested = Signal()

    def __init__(self, script_presenter, shell, size, market_catalog=None,
                 parent=None):
        super().__init__(
            title=tr('BmScriptsBox'),
            parent=parent,
            show_animation=True,
            show_duration=220,
            show_offset=8,
            auto_size_on_first_show=False,
            center_on_first_show=True,
        )
        self._shell = shell
        self.set_logo(BmTools.get_logo_path())
        self.hide_maximize_button()
        self.hide_title_bar()

        self.launcher = LauncherView(script_presenter, market_catalog)
        self.addWidget(self.launcher)
        self.launcher.navigate_requested.connect(
            self.navigate_requested.emit)

        self.resize(size)

        app = QApplication.instance()
        if app is not None:
            app.installEventFilter(self)
        self.search_shortcut = QShortcut(QKeySequence("Ctrl+F"), self)
        self.search_shortcut.activated.connect(self._focus_search)
        self.switch_shortcut = QShortcut(QKeySequence(Qt.Key_Tab), self)
        self.switch_shortcut.setContext(Qt.WindowShortcut)
        self.switch_shortcut.setAutoRepeat(False)
        self.switch_shortcut.setEnabled(False)
        self.switch_shortcut.activated.connect(
            self.switch_window_requested.emit)

    def showEvent(self, event):
        super().showEvent(event)
        self.switch_shortcut.setEnabled(True)

    def hideEvent(self, event):
        self.switch_shortcut.setEnabled(False)
        super().hideEvent(event)

    def present(self, query="", focus=True):
        self.bring_to_front()
        self.launcher.activate(query, focus=focus)

    def bring_to_front(self):
        if self._shell is not None:
            self._shell.bring_to_front(self)
            return
        if self.isMinimized():
            self.showNormal()
        self.show()
        self.raise_()
        self.activateWindow()

    def activate(self, query="", focus=True):
        self.launcher.activate(query, focus=focus)

    def focus_search(self):
        self.launcher.focus_search()

    def _focus_search(self):
        self.bring_to_front()
        self.focus_search()

    def eventFilter(self, obj, event):
        if (event.type() == QEvent.KeyPress
                and self._should_route_typing(event)):
            if self._focus_with_text(event.text()):
                return True
        return super().eventFilter(obj, event)

    def _should_route_typing(self, event):
        if not self.isVisible() or not self.isActiveWindow():
            return False
        if QApplication.activeModalWidget() or QApplication.activePopupWidget():
            return False
        if event.modifiers() & (Qt.ControlModifier | Qt.AltModifier
                                | Qt.MetaModifier):
            return False
        focus = QApplication.focusWidget()
        if focus is None:
            return False
        if isinstance(focus, (QLineEdit, QTextEdit, QPlainTextEdit,
                              QAbstractSpinBox)):
            return False
        if isinstance(focus, QComboBox) and focus.isEditable():
            return False
        text = event.text()
        return bool(text) and text.isprintable() and bool(text.strip())

    def _focus_with_text(self, text=""):
        if (QApplication.activeModalWidget()
                or QApplication.activePopupWidget()):
            return False
        self.launcher.activate(text)
        self.launcher.focus_search()
        return True

    def shutdown(self):
        app = QApplication.instance()
        if app is not None:
            app.removeEventFilter(self)
        self.search_shortcut.setEnabled(False)
        self.launcher.shutdown()
