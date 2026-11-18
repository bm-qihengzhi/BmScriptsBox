"""
Copyright (c) 2026 綦恒智
Email: bmscriptsbox@163.com
SPDX-License-Identifier: MIT
SPDX-License-Identifier: LicenseRef-Commons-Clause
"""

from PySide6.QtCore import Qt, QTimer, QSize
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QWidget, QVBoxLayout, QApplication, QTableWidgetItem, QHBoxLayout

from xsideui import XLabel, XTableWidget, XMenu, XSwitch, \
    XLineEdit, IconName, XIcon, XColor, XSize, XDivider, tr, XCard

from app.data import ProjectGlobal, ScriptDatabase
from app.utils.tools import BmTools
from app.utils.pinyin_search import PinyinSearchIndex


class FastTextWidget(QWidget):
    """超级复制窗口"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._search_index = PinyinSearchIndex()
        self._setup_ui()

    def _setup_ui(self):
        """设置界面"""
        layout = QVBoxLayout(self)
        layout.setSpacing(11)
        layout.setContentsMargins(11, 11, 11, 11)


        title_layout = QHBoxLayout()
        title_layout.addWidget(XLabel(tr('Super Copy Trigger'), style=XLabel.Style.H3))
        self.search_bar = XLineEdit(placeholder=tr('Search scripts...'), prefix_icon=IconName.SEARCH)
        self.search_bar.textChanged.connect(self.filter_scripts)
        title_layout.addWidget(self.search_bar)
        layout.addLayout(title_layout)

        super_card = XCard()
        self.super_copy_list = XTableWidget(style=XTableWidget.Style.DEFAULT, select_mode="row", hover_mode="row")
        self.super_copy_list.setIconSize(QSize(24, 24))
        self.super_copy_list.set_headers([tr('Script Name'), tr('Status')])
        self.super_copy_list.set_column_widths([-1, 100])
        super_card.addWidget(self.super_copy_list)


        # 启用右键菜单
        self.super_copy_list.setContextMenuPolicy(Qt.CustomContextMenu)
        self.super_copy_list.customContextMenuRequested.connect(self._show_context_menu)

        layout.addWidget(super_card)

    def showEvent(self, event):
        super().showEvent(event)
        # 延迟显示数据，并重新套用当前搜索词
        QTimer.singleShot(100, self.filter_scripts)

    def filter_scripts(self):
        """搜索脚本：名称支持中文/全拼/首字母/拼音子串"""
        search_text = self.search_bar.text().strip()
        all_scripts = ProjectGlobal.safe_get('SCRIPTS') or []
        if not search_text:
            filtered_scripts = all_scripts
        else:
            filtered_scripts = [
                script for script in all_scripts
                if self._search_index.matches(script.name, search_text)
            ]

        self.update_table(filtered_scripts)

    def update_table(self, data: list):
        """更新超级复制列表"""
        data = data or []
        self.super_copy_list.setRowCount(0)
        # 计算符合条件的数据数量
        valid_scripts = [item for item in data if item.triggers_schema.get('quick_copy', {}).get('enabled', False)]

        # 设置表格行数
        self.super_copy_list.setRowCount(len(valid_scripts))
        # 填充数据
        for row, script_data in enumerate(valid_scripts):
            item = QTableWidgetItem(script_data.name)
            item.setData(Qt.UserRole, script_data.id)
            icon = script_data.icon
            if not icon:
                icon = BmTools.get_language_icon_path(script_data.language)
            item.setIcon(QIcon(icon))
            self.super_copy_list.setItem(row, 0, item)
            self._setup_status_switch(row, script_data)

    def _setup_status_switch(self, row, data):
        """设置状态开关"""
        quick_copy_active = data.quick_copy_active
        switch = XSwitch(checked=quick_copy_active, text_on='', text_off='', size=XSize.SMALL)
        switch.clicked.connect(
            lambda checked, sid=data.id: self._switch_script_active(sid, checked)
        )
        self.super_copy_list.setCellWidget(row, 1, switch)

    def _switch_script_active(self, sid, checked):
        """切换脚本显示状态"""
        ScriptDatabase().update_status(sid, 'quick_copy_active', checked)
        ProjectGlobal.safe_set('SCRIPTS', ScriptDatabase().get_all_scripts())

    def _show_context_menu(self, pos):
        """显示右键菜单"""
        menu = XMenu(parent=self)

        # 获取点击位置对应的行
        index = self.super_copy_list.indexAt(pos)
        if not index.isValid():  # 点击在非有效区域
            return
        row = index.row()
        item = self.super_copy_list.item(row, 0)  # 获取第0列的item
        db_id = item.data(Qt.UserRole)  # 从item中拿到数据ID

        script_data = self.get_data(db_id)
        if not script_data.pin:
            # 添加菜单项
            menu.add_action(
                text=tr("Pin"),
                icon=XIcon.get(name=IconName.PIN_FILL, color=XColor.TERTIARY).icon(),
                triggered=lambda: self._script_top(script_data)

            )
        else:
            menu.add_action(
                text=tr("Unpin"),
                triggered=lambda: self._script_cancel_top(script_data)
            )

        # 显示菜单
        menu.exec(self.super_copy_list.viewport().mapToGlobal(pos))

    def get_data(self, db_id):
        """获取任务数据"""
        for value in (ProjectGlobal.safe_get('SCRIPTS') or []):
            if value.id == db_id:
                return value
        return None

    def _script_top(self, script_data):
        """添加脚本置顶"""
        ScriptDatabase().update_status(script_data.id, 'pin', True)
        scripts = ScriptDatabase().get_all_scripts()
        ProjectGlobal.safe_set('SCRIPTS', scripts)
        self.filter_scripts()

    def _script_cancel_top(self, script_data):
        """取消脚本置顶"""
        ScriptDatabase().update_status(script_data.id, 'pin', False)
        scripts = ScriptDatabase().get_all_scripts()
        ProjectGlobal.safe_set('SCRIPTS', scripts)
        self.filter_scripts()


if __name__ == '__main__':
    app = QApplication([])
    window = FastTextWidget()
    window.show()
    app.exec()
