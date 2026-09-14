"""
Copyright (c) 2026 綦恒智
Email: bmscriptsbox@163.com
SPDX-License-Identifier: MIT
SPDX-License-Identifier: LicenseRef-Commons-Clause
"""

from typing import Dict, Optional

from PySide2.QtCore import QTimer, Qt, QSize
from PySide2.QtGui import QIcon, QColor
from PySide2.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QTableWidgetItem, QDialog

from xsideui import XTableWidget, XPushButton, XLabel, XSwitch, XMenu, \
    XIcon, IconName, XButtonVariant, XColor, XSize, XDivider, tr, XI18N, XDialog

from app.utils import BM_LOG, BmNotify
from .scheduled_pr import ScheduledPresenter
from .scheduled_win_set import ScheduledSetWidget


# 兼容早期版本误存的中文 task_type，统一为英文码
_TASK_TYPE_CODE = {
    '固定间隔执行': 'fixed_interval', '随机间隔执行': 'random_interval',
    '倒计时执行': 'countdown', '每天执行': 'daily', '每周执行': 'weekly',
}




class ScheduledWidget(QWidget):
    """定时任务窗口"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setup_window = None

        self._setup_ui()
        self._connect_signals()
        QTimer.singleShot(100, self.lazy_load_ui)
        self.presenter = ScheduledPresenter(self)

    def _setup_ui(self):
        """设置界面"""
        layout = QVBoxLayout(self)
        layout.setSpacing(11)
        layout.setContentsMargins(11, 11, 11, 11)
        title_layout = QHBoxLayout()
        title_layout.setContentsMargins(0, 0, 0, 0)
        title = XLabel(tr('Task Scheduler'), style=XLabel.Style.H4).set_font_size(18)
        desc = XLabel(tr('Automation execution policies can be set for scripts, supporting various strategies such as loop, interval, daily, and weekly.'),word_wrap=True)
        desc.set_font_size(13).set_color(XColor.TERTIARY)
        title_layout.addWidget(title)
        layout.addLayout(title_layout)
        layout.addWidget(desc)

        self.add_btn = XPushButton(
            text=tr("New Task"),
            icon="time",
            variant=XButtonVariant.FILLED,
            size=XSize.SMALL,
        )
        title_layout.addStretch()
        title_layout.addWidget(self.add_btn)
        layout.addWidget(XDivider())

        self.task_list = XTableWidget(row_height=48)
        self.task_list.setIconSize(QSize(24, 24))
        self.task_list.set_headers([tr("Name"), tr("Schedule Details"), tr("Status"), tr("Last Run")])
        self.task_list.set_column_widths([150, -1, 90, 130])

        # 启用右键菜单
        self.task_list.setContextMenuPolicy(Qt.CustomContextMenu)
        self.task_list.customContextMenuRequested.connect(self._show_context_menu)

        layout.addWidget(self.task_list)

    def _connect_signals(self):
        """连接信号"""
        self.add_btn.clicked.connect(lambda: self._on_add_btn_clicked())

    def lazy_load_ui(self):
        self.setup_window = ScheduledSetWidget(parent=self.window())
        self.setup_window.add_finish.connect(lambda _: self.presenter.get_tasks())
        self.setup_window.add_finish.connect(self.presenter.add_new_timing_work)
        self.setup_window.edit_finish.connect(self.presenter.edit_task)

    def _on_add_btn_clicked(self, task_data: Optional[Dict] = None):
        """新增按钮点击事件"""
        try:
            if not self.setup_window:
                self.setup_window = ScheduledSetWidget()

            if task_data:
                self.setup_window.update_task_data(task_data)
            else:
                self.setup_window.update_task_name()
            self.setup_window.exec_()
        except Exception as e:
            BM_LOG.error(e)
            BmNotify().show_error_notify(tr('Failed to open schedule configuration'), in_window=True)


    def update_tasks(self, task_list):
        # 更新表单
        if not task_list:
            self.task_list.setRowCount(0)
            return
        for row, data in enumerate(task_list):
            self.task_list.setRowCount(row + 1)
            item = QTableWidgetItem(data['task_name'])
            item.setData(Qt.UserRole, data['task_id'])
            icon = QIcon(data['icon'])
            item.setIcon(icon)
            self.task_list.setItem(row, 0, item)

            item_2 = QTableWidgetItem(self.timing_description(task_type=data['task_type'], data=data))
            self.task_list.setItem(row, 1, item_2)
            self._setup_status_switch(row, data)
            self._setup_last_run_cell(row, data['task_id'])

    def _setup_last_run_cell(self, row, task_id):
        """第 4 列：最近一次执行状态 + 时间"""
        run = self.presenter.get_latest_task_run(task_id)
        if not run:
            item = QTableWidgetItem(tr("Never"))
            self.task_list.setItem(row, 3, item)
            return
        from datetime import datetime
        time_str = ""
        try:
            time_str = datetime.fromisoformat(run['run_at']).strftime('%m-%d %H:%M')
        except Exception:
            pass
        label = ({
            'success': f"成功 {time_str}",
            'failed': f"失败 {time_str}",
            'completed': f"已执行 {time_str}",
        }).get(run['status'], f"{run['status']} {time_str}")
        item = QTableWidgetItem(label)
        if run['status'] == 'failed':
            item.setForeground(QColor(220, 80, 80))
        elif run['status'] == 'success':
            item.setForeground(QColor(70, 150, 90))
        self.task_list.setItem(row, 3, item)

    @staticmethod
    def _fmt_seconds(seconds) -> str:
        """秒数转可读时长：1800 -> 30分钟，95 -> 1分35秒，30 -> 30秒"""
        if not seconds:
            return '0'
        seconds = int(seconds)
        if seconds >= 60 and seconds % 60 == 0:
            return f"{seconds // 60}分钟"
        if seconds >= 60:
            return f"{seconds // 60}分{seconds % 60}秒"
        return f"{seconds}秒"

    def timing_description(self, task_type, data):
        description = tr("Unknown")
        # 兼容早期版本误存的中文 task_type
        task_type = _TASK_TYPE_CODE.get(task_type, task_type)
        if task_type == "fixed_interval":
            description = f"间隔:{self._fmt_seconds(data.get('interval_minutes'))}"
            if data.get('max_run_count'):
                description += f"（{data.get('executed_count', 0)}/{data['max_run_count']}次）"
        elif task_type == "random_interval":
            description = f"随机间隔:{self._fmt_seconds(data.get('min_interval_minutes'))}-{self._fmt_seconds(data.get('max_interval_minutes'))}"
            if data.get('max_run_count'):
                description += f"（{data.get('executed_count', 0)}/{data['max_run_count']}次）"
        elif task_type == "countdown":
            description = f"倒计时:{self._fmt_seconds(data.get('delay_minutes'))}"
        elif task_type == "daily":
            description = f"每日:{str(data['daily_time'])}"
        elif task_type == "weekly":
            description = f"每{data['weekly_weekday']}{data['weekly_time']}"
        return description

    def _setup_status_switch(self, row, data):
        """设置状态开关"""
        is_active = data.get('is_active', False)
        switch = XSwitch(checked=is_active, text_on='', text_off='', size=XSize.SMALL)
        switch.clicked.connect(
            lambda checked, sid=data['task_id']: self.presenter.on_switch_clicked(sid, checked)
        )
        self.task_list.setCellWidget(row, 2, switch)

    def _show_context_menu(self, pos):
        """显示右键菜单"""
        menu = XMenu(parent=self)

        # 获取点击位置对应的行
        index = self.task_list.indexAt(pos)
        if not index.isValid():  # 点击在非有效区域
            return
        row = index.row()
        item = self.task_list.item(row, 0)  # 获取第0列的item
        db_id = item.data(Qt.UserRole)  # 从item中拿到数据ID

        task_data = self.presenter.get_task(db_id)

        # 添加菜单项
        menu.add_action(
            text=tr("Edit"),
            icon=XIcon.get(IconName.EDIT, color=XColor.PRIMARY).icon(),
            triggered=lambda: self._on_add_btn_clicked(task_data)

        )
        if task_data.get('is_active'):
            menu.add_action(
                text=tr('Disable'),
                icon=XIcon.get(IconName.MINUS_CIRCLE, color=XColor.TERTIARY).icon(),
                triggered=lambda: self.presenter.on_switch_clicked(task_data['task_id'], False)
            )
        else:
            menu.add_action(
                text=tr('Enable'),
                icon=XIcon.get(IconName.POWER, color=XColor.PRIMARY).icon(),
                triggered=lambda: self.presenter.on_switch_clicked(task_data['task_id'], True)
            )

        menu.add_action(
            text=tr('Run History'),
            icon=XIcon.get(IconName.HISTORY, color=XColor.PRIMARY).icon(),
            triggered=lambda: self._open_run_history(task_data['task_id'], task_data.get('task_name', ''))
        )

        menu.add_action(
            text=tr('Delete'),
            icon=XIcon.get(IconName.DELETE, color=XColor.DANGER).icon(),
            triggered=lambda: self.presenter.delete_task(task_data['task_id'])
        )

        # 显示菜单
        menu.exec_(self.task_list.viewport().mapToGlobal(pos))

    def _open_run_history(self, task_id, task_name):
        """打开某任务的执行历史对话框"""
        try:
            from datetime import datetime
            runs = self.presenter.get_task_runs(task_id)
            dialog = XDialog(self.window())
            dialog.set_title(f"{task_name} -定时执行记录")
            dialog.resize(560, 420)
            history_widget = QWidget()
            dialog.addWidget(history_widget)
            lay = QVBoxLayout(history_widget)
            table = XTableWidget(row_height=34)
            table.set_headers([tr("Time"), tr("Status"), tr("Message")])
            table.set_column_widths([180, 80,-1])
            if runs:
                for row, r in enumerate(runs):
                    table.setRowCount(row + 1)
                    try:
                        t = datetime.fromisoformat(r['run_at']).strftime('%Y-%m-%d %H:%M:%S')
                    except Exception:
                        t = r.get('run_at') or ''
                    table.setItem(row, 0, QTableWidgetItem(t))
                    status_text = {'success': '成功', 'failed': '失败', 'completed': '已执行'}.get(r.get('status'), r.get('status'))
                    table.setItem(row, 1, QTableWidgetItem(status_text))
                    table.setItem(row, 2, QTableWidgetItem(str(r.get('msg') or '')))
            lay.addWidget(table)
            btn = XPushButton(text=tr('Close'))
            btn.clicked.connect(dialog.accept)
            lay.addWidget(btn, alignment=Qt.AlignRight)
            dialog.exec_()
        except Exception as e:
            BM_LOG.error(f"打开执行历史失败: {e}")
            BmNotify().show_error_notify(tr('Failed to open run history'), in_window=True)

    def showEvent(self, event):
        super().showEvent(event)
        self.presenter.get_tasks()





