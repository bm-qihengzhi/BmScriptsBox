"""
Copyright (c) 2026 綦恒智
Email: bmscriptsbox@163.com
SPDX-License-Identifier: MIT
SPDX-License-Identifier: LicenseRef-Commons-Clause
"""
import sys

from PySide6.QtCore import QTimer, QSize
from PySide6.QtGui import Qt, QIcon
from PySide6.QtWidgets import QWidget, QVBoxLayout, QTableWidgetItem, QApplication, QHBoxLayout

from typing import Optional
from xsideui import XTableWidget, XSwitch, XComboBox, XMenu, XLabel, XPushButtonDropdown, \
    XSize, IconName, XButtonVariant, XColor, XIcon, XNotif, XDivider, tr, XCard, XI18N
from .context_pr import MenuPresenter


class ContextWidget(QWidget):
    """右键菜单视图 - 负责 UI 渲染"""

    COLUMN_MAP = ["name", "father", "level", "state"]

    def __init__(self):
        super().__init__()
        self.presenter = MenuPresenter()
        self._last_menu_script_id = None
        self._setup_ui()
        self._init_presenter_signals()

    def showEvent(self, event):
        super().showEvent(event)
        QTimer.singleShot(100, self.presenter.initialize)

    def _setup_ui(self):
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(11, 11, 11, 11)
        self.main_layout.setSpacing(11)

        title_layout = QHBoxLayout()
        title = XLabel(tr('Context Menu Manager'), style=XLabel.Style.H3)
        self.search_combox = XComboBox(size=XSize.SMALL)
        self.search_combox.addItems([tr("File Menu"), tr("Folder Menu"), tr('Background Menu')])
        self.search_combox.currentIndexChanged.connect(self.presenter.on_search_type_changed)

        self.more_btn = XPushButtonDropdown(
            text=tr("Menu Actions"),
            variant=XButtonVariant.FILLED,
            size=XSize.SMALL,
            icon=IconName.LIST,
            # XPushButtonDropdown 用原生 QMenu.addAction，不走 xsideui 的自动查表，
            # 菜单项必须显式 x_tr，否则 tr() 只是一句标记、运行时原样显示英文
            menu_items=[
                {"text": XI18N.x_tr("Register menu"), "value": "register"},
                {"text": XI18N.x_tr("Unregister menu"), "value": "uninstall"},
                {"text": XI18N.x_tr("Switch menu style"), "value": "Switch"},
            ],
        )
        self.more_btn.menuTriggered.connect(self.presenter.on_menu_action_triggered)

        title_layout.addWidget(title,1)
        title_layout.addWidget(self.search_combox,0)
        title_layout.addWidget(self.more_btn,0)
        self.main_layout.addLayout(title_layout)

        self.table_widget = XTableWidget(style=XTableWidget.Style.DEFAULT, select_mode="row", hover_mode="row")
        self.table_widget.setIconSize(QSize(24, 24))
        self.table_widget.set_headers([tr("Name"), tr('Parent'), tr('Level'), tr('Status')])
        self.table_widget.set_column_widths([-1, 120, 100, 60])
        self.table_widget.setContextMenuPolicy(Qt.CustomContextMenu)
        self.table_widget.customContextMenuRequested.connect(self._on_context_menu_requested)

        table_card = XCard()
        table_card.addWidget(self.table_widget)
        self.main_layout.addWidget(table_card)

    def _init_presenter_signals(self):
        self.presenter.data_loaded.connect(self._on_data_loaded)
        self.presenter.notification.connect(self._on_notification)
        self.presenter.show_context_menu.connect(self._on_show_context_menu)
        self.presenter.action_completed.connect(self._on_action_completed)

    def _on_data_loaded(self, data: list, level_map: dict):
        self._render_table(data, level_map)

    def _render_table(self, data: list, level_map: dict):
        self.table_widget.setRowCount(0)
        self.table_widget.setRowCount(len(data))
        for row, item_data in enumerate(data):
            for col, key in enumerate(self.COLUMN_MAP):
                if key == "state":
                    self._add_switch_cell(row, col, item_data)
                elif key == "level":
                    text = level_map.get(item_data.get(key), tr('Unknown'))
                    item = QTableWidgetItem(text)
                    item.setData(Qt.UserRole, item_data.get('level'))
                    self.table_widget.setItem(row, col, item)
                else:
                    val = str(item_data.get(key, ""))
                    item = QTableWidgetItem(val)
                    if key == "name":
                        item.setData(Qt.UserRole, item_data.get("scriptId"))
                        if "iconPath" in item_data:
                            item.setIcon(QIcon(item_data["iconPath"]))
                    self.table_widget.setItem(row, col, item)

    def _add_switch_cell(self, row: int, col: int, data: dict):
        switch = XSwitch(size=XSize.SMALL, checked=data.get('state', False), text_on='', text_off='')
        switch.clicked.connect(lambda state, sid=data.get('scriptId'): self.presenter.on_status_changed(sid, state))
        self.table_widget.setCellWidget(row, col, switch)

    def _on_context_menu_requested(self, pos):
        item = self.table_widget.itemAt(pos)
        if not item:
            return
        row = item.row()
        row_data = self._get_row_data(row)
        if row_data:
            self.presenter.on_context_menu_requested(pos, row_data)

    def _get_row_data(self, row: int) -> Optional[dict]:
        if row < 0 or row >= self.table_widget.rowCount():
            return None
        name_item = self.table_widget.item(row, 0)
        if not name_item:
            return None
        return {
            'name': name_item.text(),
            'row': row,
            'scriptId': name_item.data(Qt.UserRole),
        }

    def _on_show_context_menu(self, pos, row_data: dict):
        menu = XMenu(parent=self)
        script_id = row_data.get('scriptId')
        row = row_data.get('row', 0)
        self._last_menu_script_id = script_id

        menu.add_action(
            text=tr("Move to Top"),
            icon=XIcon.get(name=IconName.TO_TOP, color=XColor.TERTIARY).icon(),
            triggered=lambda: self.presenter.on_move_top(script_id),
        )
        menu.add_action(
            text=tr("Move Up"),
            icon=XIcon.get(name=IconName.UP_ARROW, color=XColor.TERTIARY).icon(),
            triggered=lambda: self.presenter.on_move_up(script_id),
        )
        menu.add_action(
            text=tr('Move Down'),
            icon=XIcon.get(name=IconName.DOWN_ARROW, color=XColor.TERTIARY).icon(),
            triggered=lambda: self.presenter.on_move_down(script_id),
        )
        menu.add_action(
            text=tr('Move to Bottom'),
            icon=XIcon.get(name=IconName.TO_BOTTOM, color=XColor.TERTIARY).icon(),
            triggered=lambda: self.presenter.on_move_bottom(script_id),
        )

        item = self.table_widget.item(row, 2)
        level = item.data(Qt.UserRole) if item else 2
        if level == 1:
            menu.add_action(
                text=tr('Move to Level 2'),
                icon=XIcon.get(name=IconName.DOWN_DOUBLE, color=XColor.TERTIARY).icon(),
                triggered=lambda: self.presenter.on_change_level(script_id, 2)
            )
        else:
            menu.add_action(
                text=tr('Move to Level 1'),
                icon=XIcon.get(name=IconName.UP_DOUBLE, color=XColor.TERTIARY).icon(),
                triggered=lambda: self.presenter.on_change_level(script_id, 1)
            )

        menu.exec(self.table_widget.viewport().mapToGlobal(pos))

    def _on_action_completed(self, action: str, success: bool, direction: str):
        if success and action == "move":
            row = self._find_row_by_script_id(self._last_menu_script_id)
            if row >= 0:
                self.table_widget.selectRow(row)

    def _find_row_by_script_id(self, script_id: str) -> int:
        if not script_id:
            return -1
        for row in range(self.table_widget.rowCount()):
            item = self.table_widget.item(row, 0)
            if item and item.data(Qt.UserRole) == script_id:
                return row
        return -1

    def _on_notification(self, message: str, msg_type: str):
        position = XNotif.Pos.CENTER
        if msg_type == "error":
            XNotif.error(message, position=position, parent=self)
        elif msg_type == "warning":
            XNotif.warning(message, position=position, parent=self)
        elif msg_type == "success":
            XNotif.success(message, position=position, parent=self)
        else:
            XNotif.info(message, position=position, parent=self)


if __name__ == '__main__':
    app = QApplication(sys.argv)
    view = ContextWidget()
    view.show()
    sys.exit(app.exec())
