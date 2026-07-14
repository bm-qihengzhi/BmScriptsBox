"""
Copyright (c) 2026 綦恒智
Email: bmscriptsbox@163.com
SPDX-License-Identifier: AGPL-3.0
"""

from PySide2.QtCore import Qt, QTimer, QSize
from PySide2.QtGui import QIcon
from PySide2.QtWidgets import QWidget, QVBoxLayout, QApplication, QTableWidgetItem

from xsideui import XLabel, XTableWidget, XMenu, XSwitch, \
    XLineEdit, IconName, XIcon, XColor, XSize, XDivider, tr

from app.data import ProjectGlobal, ScriptDatabase, ScriptEntity
from app.utils.tools import BmTools


class FastTextWidget(QWidget):
    """超级复制窗口"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._setup_ui()

    def _setup_ui(self):
        """设置界面"""
        layout = QVBoxLayout(self)
        layout.setSpacing(11)
        layout.setContentsMargins(11, 11, 11, 11)

        title = XLabel(tr('Quick Copy Trigger'), style=XLabel.Style.H4).set_font_size(18)
        desc = XLabel(tr('Select text, press Ctrl+C+C to open the "Super Copy" script list. Choose a script to run — the selected text will be passed as a parameter.'),word_wrap=True)
        desc.set_font_size(13).set_color(XColor.TERTIARY)
        layout.addWidget(title)
        layout.addWidget(desc)
        layout.addWidget(XDivider())

        self.search_bar = XLineEdit(placeholder=tr('Search scripts...'), prefix_icon=IconName.SEARCH)
        self.search_bar.textChanged.connect(self.filter_scripts)

        layout.addWidget(self.search_bar)

        # 定时任务列表
        self.test_widget_list = XTableWidget(row_height=48)
        self.test_widget_list.setIconSize(QSize(24, 24))
        self.test_widget_list.set_headers([tr('Script Name'), tr('Status')])
        self.test_widget_list.set_column_widths([-1, 100])

        # 启用右键菜单
        self.test_widget_list.setContextMenuPolicy(Qt.CustomContextMenu)
        self.test_widget_list.customContextMenuRequested.connect(self._show_context_menu)

        layout.addWidget(self.test_widget_list)

    def showEvent(self, event):
        super().showEvent(event)
        # 延迟显示数据
        QTimer.singleShot(100, lambda: self.update_table(ProjectGlobal.SCRIPTS))

    def filter_scripts(self):
        """搜索脚本"""
        search_text = self.search_bar.text().strip()
        filtered_scripts = []
        if not search_text:
            filtered_scripts = ProjectGlobal.SCRIPTS
        else:
            for script in ProjectGlobal.SCRIPTS:
                script_name = script.script_name
                if search_text in str(script_name).lower():
                    filtered_scripts.append(script)

        self.update_table(filtered_scripts)

    def update_table(self, data: list):
        """更新超级复制列表"""
        self.test_widget_list.setRowCount(0)
        # 计算符合条件的数据数量
        valid_scripts = [item for item in data if item.triggers_schema['quick_copy'].get('enabled', False)]

        # 设置表格行数
        self.test_widget_list.setRowCount(len(valid_scripts))
        # 填充数据
        for row, script_data in enumerate(valid_scripts):
            item = QTableWidgetItem(script_data.name)
            item.setData(Qt.UserRole, script_data.id)
            icon = script_data.icon
            if not icon:
                icon = BmTools.get_language_icon_path(script_data.language)
            item.setIcon(QIcon(icon))
            self.test_widget_list.setItem(row, 0, item)
            self._setup_status_switch(row, script_data)

    def _setup_status_switch(self, row, data):
        """设置状态开关"""
        quick_copy_active = data.quick_copy_active
        switch = XSwitch(checked=quick_copy_active, text_on='', text_off='', size=XSize.SMALL)
        switch.clicked.connect(
            lambda checked, sid=data.id: self._switch_script_active(sid, checked)
        )
        self.test_widget_list.setCellWidget(row, 1, switch)

    def _switch_script_active(self, sid, checked):
        """切换脚本显示状态"""
        ScriptDatabase().update_status(sid, 'quick_copy_active',checked)
        ProjectGlobal.SCRIPTS =ScriptDatabase().get_all_scripts()

    def _show_context_menu(self, pos):
        """显示右键菜单"""
        menu = XMenu(parent=self)

        # 获取点击位置对应的行
        index = self.test_widget_list.indexAt(pos)
        if not index.isValid():  # 点击在非有效区域
            return
        row = index.row()
        item = self.test_widget_list.item(row, 0)  # 获取第0列的item
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
        menu.exec_(self.test_widget_list.viewport().mapToGlobal(pos))

    def get_data(self, db_id):
        """获取任务数据"""
        for value in ProjectGlobal.SCRIPTS:
            if value.id == db_id:
                return value
        return None

    def _script_top(self, script_data):
        """添加脚本置顶"""
        all_scripts = ScriptDatabase().update_status(script_data.id, 'pin',True)
        ProjectGlobal.SCRIPTS = [ScriptEntity.model_validate(r) for r in all_scripts]
        self.update_table(ProjectGlobal.SCRIPTS)

    def _script_cancel_top(self, script_data):
        """取消脚本置顶"""
        all_scripts = ScriptDatabase().update_status(script_data.id, 'pin',False)
        ProjectGlobal.SCRIPTS = [ScriptEntity.model_validate(r) for r in all_scripts]
        self.update_table(ProjectGlobal.SCRIPTS)


if __name__ == '__main__':
    app = QApplication([])
    window = FastTextWidget()
    window.show()
    app.exec_()
