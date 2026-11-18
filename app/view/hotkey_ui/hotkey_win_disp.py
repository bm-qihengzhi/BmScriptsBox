"""
Copyright (c) 2026 綦恒智
Email: bmscriptsbox@163.com
SPDX-License-Identifier: MIT
SPDX-License-Identifier: LicenseRef-Commons-Clause
"""
import sys
from pathlib import Path

from PySide6.QtCore import Qt, Signal, QTimer, QSize
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QWidget, QVBoxLayout, QTableWidgetItem, QApplication, QHBoxLayout

from xsideui import XTableWidget, XSwitch, XMenu, XLineEdit, XLabel, XIcon, \
    IconName, XColor, XNotif, XSize as XUISize, tr, XDivider, XCard, XI18N
from app.utils import BmTools
from app.data import ScriptEntity
from .hotkey_pr import HotkeyPresenter
from .hotkey_win_set import HotkeySettingWidget


class HotkeyWidget(QWidget):
    """热键设置视图 - 负责 UI 渲染"""

    def __init__(self):
        super().__init__()
        self.presenter = HotkeyPresenter()
        self._setup_ui()
        self._init_presenter_signals()

        self.search_timer = QTimer()
        self.search_timer.setSingleShot(True)
        self.search_timer.timeout.connect(self._do_search)

    def showEvent(self, event):
        super().showEvent(event)
        QTimer.singleShot(100, self.presenter.load_scripts)

    def _setup_ui(self):
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(11, 11, 11, 11)
        self.main_layout.setSpacing(11)

        header_container = QHBoxLayout()
        header_container.setSpacing(11)

        title = XLabel(tr('Global Hotkey Trigger'), style=XLabel.Style.H3)


        self.search_bar = XLineEdit(placeholder=tr('Search scripts...'), prefix_icon=IconName.SEARCH)
        self.search_bar.textChanged.connect(self._on_search_text_changed)
        header_container.addWidget(title,0)
        header_container.addWidget(self.search_bar,1)

        self.main_layout.addLayout(header_container)
        self.table_widget = XTableWidget(style=XTableWidget.Style.DEFAULT, select_mode="row", hover_mode="row")
        self.table_widget.set_headers([tr('Name'), tr('Hotkey'), tr('Status'), tr('Usage')])
        self.table_widget.set_column_widths([-1, 80, 60, 300])
        self.table_widget.setIconSize(QSize(24, 24))
        self.table_widget.setContextMenuPolicy(Qt.CustomContextMenu)
        self.table_widget.customContextMenuRequested.connect(self._show_context_menu)

        table_card = XCard()
        table_card.addWidget(self.table_widget)
        self.main_layout.addWidget(table_card)

    def _init_presenter_signals(self):
        self.presenter.scripts_loaded.connect(self._on_scripts_loaded)
        self.presenter.notification.connect(self._on_notification)
        self.presenter.open_hotkey_window.connect(self._on_open_hotkey_window)


    def _on_search_text_changed(self):
        self.search_timer.start(500)

    def _do_search(self):
        keyword = self.search_bar.text().strip()
        self.presenter.search_scripts(keyword)

    def _on_scripts_loaded(self, scripts):
        self._render_table(scripts)

    def _render_table(self, scripts):
        self.table_widget.setRowCount(0)
        self.table_widget.setRowCount(len(scripts))
        for row, script in enumerate(scripts):
            self._setup_table_row(row, script)

    def _setup_table_row(self, row: int, script: ScriptEntity):
        item_name = QTableWidgetItem(script.name)
        icon_path = script.icon or BmTools.get_language_icon_path(script.language)
        item_name.setIcon(QIcon(icon_path))
        self.table_widget.setItem(row, 0, item_name)
        # 原生 QTableWidgetItem / setToolTip 不会自动查表，必须显式 x_tr
        self.table_widget.setItem(row, 1, QTableWidgetItem(script.hotkey or XI18N.x_tr('None')))

        switch = XSwitch(checked=script.hotkey_active, text_on='', text_off='', size=XUISize.SMALL)
        switch.clicked.connect(lambda checked, sid=script.id: self.presenter.toggle_status(sid, checked))
        self.table_widget.setCellWidget(row, 2, switch)

        shortcut_type = script.triggers_schema['shortcut'].get('input_type','')
        if not shortcut_type:
            item_info = QTableWidgetItem(XI18N.x_tr('Run directly'))
            item_info.setIcon(XIcon.get(IconName.CHECK_CIRCLE, color=XColor.SUCCESS).icon())
        else:
            type_map = {
                'files': (XI18N.x_tr('Hotkey for selected files'), IconName.FILE, XI18N.x_tr('Run on selected file (auto pass path)')),
                'folders': (XI18N.x_tr('Hotkey for selected folders'), IconName.FOLDER,  XI18N.x_tr('Run on selected folder (auto pass path)')),
                'items': (XI18N.x_tr('Hotkey for selected files/folders'), IconName.CHECK_CIRCLE,  XI18N.x_tr('Run on selected file/folder (auto pass path)')),
                'active': (XI18N.x_tr('Hotkey inside File Explorer'), IconName.WINDOWS,  XI18N.x_tr('Run in File Explorer (auto pass path)')),
            }
            if shortcut_type in type_map:
                display_text, icon_name, tip = type_map[shortcut_type]
                item_info = QTableWidgetItem(display_text)
                item_info.setToolTip(tip)
                item_info.setIcon(
                    XIcon.get(
                        icon_name,
                        color=XColor.SECONDARY,
                    ).icon()
                )


            else:
                item_info = QTableWidgetItem(XI18N.x_tr('Run directly'))
                item_info.setIcon(XIcon.get(IconName.CHECK_CIRCLE, color=XColor.SUCCESS, size=18).icon())

        self.table_widget.setItem(row, 3, item_info)

    def _show_context_menu(self, pos):
        item = self.table_widget.itemAt(pos)
        if not item:
            return

        row = item.row()
        script = self.presenter.get_script_by_row(row)
        if not script:
            return

        menu = XMenu(parent=self)
        menu.add_action(
            text=tr('Edit'),
            icon=XIcon(name=IconName.EDIT, color=XColor.PRIMARY).icon(),
            triggered=lambda: self.presenter.edit_hotkey(script.id),
        )
        menu.add_action(
            text=tr('Clear'),
            icon=XIcon(name=IconName.DELETE, color=XColor.DANGER).icon(),
            triggered=lambda: self.presenter.remove_hotkey(script.id),
        )
        menu.exec(self.table_widget.viewport().mapToGlobal(pos))

    def _on_notification(self, message: str, is_success: bool):
        if is_success:
            XNotif.success(message, parent=self)
        else:
            XNotif.error(message, position=XNotif.Pos.CENTER, parent=self)

    def _on_open_hotkey_window(self, script_id: str, current_key: str, script_name: str):
        setup_window = HotkeySettingWidget(
            script_id, current_key, script_name,
            conflict_check_fn=lambda k: self.presenter.check_conflict(script_id, k),
            parent=self,
        )
        setup_window.handle_signal.connect(self._on_hotkey_saved)
        setup_window.exec()

    def _on_hotkey_saved(self, hotkey_info: tuple):
        script_id, hotkey_key = hotkey_info
        self.presenter.save_hotkey(script_id, hotkey_key)


if __name__ == '__main__':
    from app.utils import BmTools
    sys.path.insert(0, str(BmTools.get_root_path()))
    app = QApplication(sys.argv)
    window = HotkeyWidget()
    window.show()
    sys.exit(app.exec())
