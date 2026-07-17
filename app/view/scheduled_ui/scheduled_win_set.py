"""
Copyright (c) 2026 綦恒智
Email: bmscriptsbox@163.com
SPDX-License-Identifier: AGPL-3.0
"""
from PySide2.QtCore import Qt, Signal, QTime
from PySide2.QtWidgets import QWidget, QHBoxLayout, QVBoxLayout, QGridLayout, QButtonGroup, QStackedWidget
from xsideui import XSpinBox, XPushButton, XLabel, XComboBox, XTimeEdit, XTextEdit, XButtonVariant, \
    XColor, XDialog, XRadioButton, tr
from xsideui.widgets.divider import XTextDivider
from app.data import ProjectGlobal, ScriptDatabase, TaskDatabase
from app.utils.tools import BmTools
from .scheduled_mode import TimeMode, WeekMode


class ScheduledSetWidget(XDialog):
    """定时任务设置窗口"""
    add_finish = Signal(dict)
    edit_finish = Signal(dict)

    def __init__(self, parent=None):
        super().__init__(parent=parent)
        self.task = None
        self.scripts_model = {}
        self._param_widget = None
        self._param_inputs = {}
        self._setup_ui()
        self._connect_signals()
        self.setModal(True)

    def update_task_name(self):
        if not ProjectGlobal.SCRIPTS:
            ProjectGlobal.SCRIPTS = ScriptDatabase.get_all_scripts()
        scripts = ProjectGlobal.SCRIPTS
        data = []
        for script in scripts:
            self.scripts_model[script.name] = {
                "script_id": script.id,
                "icon": script.icon,
                "script_language": script.language,
                "inputs_schema": script.inputs_schema,
            }
            data.append(script.name)
        self.task_name.clear()
        self.task_name.addItems(data)
        self.param_stacked.setCurrentIndex(0)
        self._fixed_radio.setChecked(True)

    def _setup_ui(self):
        self.set_title(tr('Scheduled Scripts'))
        self.set_logo(BmTools.get_logo_path())
        self.hide_maximize_button()
        self.resize(420, 380)

        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(11)

        # ── 脚本 ──
        combo_row = QHBoxLayout()
        combo_row.setSpacing(11)
        combo_row.addWidget(XLabel(tr('Name')), 0)
        self.task_name = XComboBox()
        combo_row.addWidget(self.task_name, 1)
        combo_row.addStretch()
        layout.addLayout(combo_row)
        layout.addWidget(XTextDivider(tr('Script Params'), align=Qt.AlignLeft))

        # ── 参数 ──
        self.param_stacked = QStackedWidget()
        layout.addWidget(self.param_stacked)

        # ── 时间设置 ──
        time_divider = XTextDivider(tr('Scheduled Strategy'), align=Qt.AlignLeft)
        grid = QGridLayout()
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setHorizontalSpacing(8)
        grid.setVerticalSpacing(6)

        self._time_group = QButtonGroup(self)

        row = 0
        self._fixed_radio = XRadioButton(tr("Fixed Interval"))
        self._time_group.addButton(self._fixed_radio, 0)
        self.repeat_minute = XSpinBox(suffix=" 分钟")
        self.repeat_minute.setFixedWidth(130)
        grid.addWidget(self._fixed_radio, row, 0)
        grid.addWidget(self.repeat_minute, row, 1)
        row += 1

        self._random_radio = XRadioButton(tr("Random Interval"))
        self._time_group.addButton(self._random_radio, 1)
        self.random_mini_minute = XSpinBox(prefix='最小', suffix=" 分钟")
        self.random_mini_minute.setFixedWidth(130)
        self.random_max_minute = XSpinBox(prefix='最大', suffix=" 分钟")
        self.random_max_minute.setFixedWidth(130)
        grid.addWidget(self._random_radio, row, 0)
        grid.addWidget(self.random_mini_minute, row, 1)
        grid.addWidget(self.random_max_minute, row, 2)
        row += 1

        self._countdown_radio = XRadioButton(tr("Countdown"))
        self._time_group.addButton(self._countdown_radio, 2)
        self.countdown_minute = XSpinBox(suffix=" 分钟")
        self.countdown_minute.setFixedWidth(130)
        grid.addWidget(self._countdown_radio, row, 0)
        grid.addWidget(self.countdown_minute, row, 1)
        row += 1

        self._daily_radio = XRadioButton(tr("Daily"))
        self._time_group.addButton(self._daily_radio, 3)
        self.daily_time = XTimeEdit()
        self.daily_time.setFixedWidth(130)
        grid.addWidget(self._daily_radio, row, 0)
        grid.addWidget(self.daily_time, row, 1)
        row += 1

        self._weekly_radio = XRadioButton(tr("Weekly"))
        self._time_group.addButton(self._weekly_radio, 4)
        self.week_combobox = XComboBox()
        self.week_combobox.addItems([mode.value for mode in WeekMode])
        self.week_combobox.setFixedWidth(130)
        self.weekly_time = XTimeEdit()
        self.weekly_time.setFixedWidth(130)
        grid.addWidget(self._weekly_radio, row, 0)
        grid.addWidget(self.week_combobox, row, 1)
        grid.addWidget(self.weekly_time, row, 2)
        row += 1

        grid.setColumnStretch(0, 0)
        grid.setColumnStretch(1, 0)
        grid.setColumnStretch(2, 0)
        grid.setColumnStretch(3, 1)

        layout.addWidget(time_divider)
        layout.addLayout(grid)

        # ── 按键 ──
        btn_row = QHBoxLayout()
        btn_row.addStretch()
        self.cancel_btn = XPushButton(
            text=tr('Cancel'), variant=XButtonVariant.OUTLINED, color=XColor.TERTIARY
        )
        self.ok_btn = XPushButton(text=tr("OK"), variant=XButtonVariant.FILLED)
        btn_row.addWidget(self.cancel_btn)
        btn_row.addWidget(self.ok_btn)
        layout.addLayout(btn_row)

        self.addWidget(widget)

    def _connect_signals(self):
        self.task_name.currentTextChanged.connect(self._on_script_changed)
        self.ok_btn.clicked.connect(self.on_ok_btn_clicked)
        self.cancel_btn.clicked.connect(self.close)

    def _on_script_changed(self, script_name):
        script_info = self.scripts_model.get(script_name)
        if not script_info:
            return
        self._rebuild_params_ui(script_info.get('inputs_schema', []))

    def _rebuild_params_ui(self, inputs_schema: list):
        if self._param_widget:
            self.param_stacked.removeWidget(self._param_widget)
            self._param_widget.deleteLater()
            self._param_widget = None

        self._param_inputs = {}

        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        placeholder_map = {
            'paths': ['文件路径', '请输入路径参数 一行一个'],
            'text': ['文本内容', '请输入文本参数'],
        }

        for idx, inp in enumerate(inputs_schema):
            name = inp.get('name', '')
            ptype = inp.get('type', '')
            desc = inp.get('description', '')
            exts = inp.get('exts', [])

            if not ptype or not name:
                layout.addWidget(XLabel(tr('No arguments required')), alignment=Qt.AlignCenter)
                return

            ptype = ptype.lower()
            type_info = placeholder_map.get(ptype, '')
            ph = type_info[1] if type_info else '请输入参数'
            if exts:
                ph += f"（{' '.join(exts)}）"

            self.edit = XTextEdit(placeholder=ph)
            self.edit.setMaximumHeight(100)
            self._param_inputs[idx] = {'widget': self.edit, 'type': 'text' if ptype == 'text' else 'paths'}

            layout.addWidget(XLabel(f"脚本参数：{name}"))
            layout.addWidget(self.edit)
            layout.addWidget(XLabel(f"参数类别：{type_info[0] if type_info else '未知'}").set_color(XColor.TERTIARY).set_font_size(12))
            if desc:
                layout.addWidget(XLabel(f"参数描述：{desc}").set_color(XColor.TERTIARY).set_font_size(12))

        if not self._param_inputs:
            layout.addWidget(XLabel(tr('No arguments required')), alignment=Qt.AlignCenter)

        self._param_widget = widget
        self.param_stacked.addWidget(widget)
        self.param_stacked.setCurrentWidget(widget)

    # ── 时间模式 ──

    def _get_selected_mode(self) -> TimeMode:
        idx = self._time_group.checkedId()
        mapping = {
            0: TimeMode.FIXED_INTERVAL,
            1: TimeMode.RANDOM_INTERVAL,
            2: TimeMode.COUNTDOWN,
            3: TimeMode.DAILY,
            4: TimeMode.WEEKLY,
        }
        return mapping.get(idx, TimeMode.FIXED_INTERVAL)

    def _set_mode_by_type(self, task_type: str):
        mapping = {
            'fixed_interval': 0,
            'random_interval': 1,
            'countdown': 2,
            'daily': 3,
            'weekly': 4,
        }
        idx = mapping.get(task_type)
        btn = self._time_group.button(idx)
        if btn:
            btn.setChecked(True)

    # ── 参数读取与填充 ──

    def get_current_settings(self) -> dict:
        current_mode = self._get_selected_mode()
        settings = {
            "task_name": self.task_name.currentText(),
            "is_active": True,
        }

        if current_mode == TimeMode.FIXED_INTERVAL:
            settings.update({
                "interval_minutes": self.repeat_minute.value(),
                'task_type': 'fixed_interval'
            })
        elif current_mode == TimeMode.RANDOM_INTERVAL:
            settings.update({
                "min_interval_minutes": self.random_mini_minute.value(),
                "max_interval_minutes": self.random_max_minute.value(),
                'task_type': 'random_interval'
            })
        elif current_mode == TimeMode.COUNTDOWN:
            settings.update({
                "delay_minutes": self.countdown_minute.value(),
                'task_type': 'countdown'
            })
        elif current_mode == TimeMode.DAILY:
            settings.update({
                "daily_time": self.daily_time.time().toString(),
                'task_type': 'daily'
            })
        elif current_mode == TimeMode.WEEKLY:
            idx = self.week_combobox.currentIndex()
            weekday = list(WeekMode)[idx].value
            settings.update({
                "weekly_weekday": weekday,
                "weekly_time": self.weekly_time.time().toString(),
                'task_type': 'weekly'
            })

        param_type = ''
        param_value = ''
        for idx in sorted(self._param_inputs.keys()):
            pinfo = self._param_inputs[idx]
            text = pinfo['widget'].toPlainText().strip()
            if not text:
                continue
            if pinfo['type'] == 'text':
                param_type = 'text'
                param_value = text
            else:
                lines = [line.strip() for line in text.splitlines() if line.strip()]
                param_type = 'path'
                param_value = lines
            break

        settings.update({
            "task_parameter_type": param_type,
            "task_parameter": param_value
        })

        return settings

    def update_task_data(self, tasks):
        self.task = tasks
        if not self.scripts_model:
            self.update_task_name()
        task_type = tasks.get('task_type')

        self._set_mode_by_type(task_type)

        if task_type == 'fixed_interval':
            self.repeat_minute.setValue(tasks.get('interval_minutes'))
        elif task_type == 'random_interval':
            self.random_mini_minute.setValue(tasks.get('min_interval_minutes'))
            self.random_max_minute.setValue(tasks.get('max_interval_minutes'))
        elif task_type == 'countdown':
            self.countdown_minute.setValue(tasks.get('delay_minutes'))
        elif task_type == 'daily':
            self.daily_time.setTime(QTime.fromString(tasks.get('daily_time')))
        elif task_type == 'weekly':
            weekday_val = tasks.get('weekly_weekday')
            modes = list(WeekMode)
            for i, m in enumerate(modes):
                if m.value.lower() == weekday_val.lower():
                    self.week_combobox.setCurrentIndex(i)
                    break
            self.weekly_time.setTime(QTime.fromString(tasks.get('weekly_time')))

        script_info = self.scripts_model.get(tasks.get('task_name'))
        if script_info:
            self._rebuild_params_ui(script_info.get('inputs_schema', []))
            param_type = tasks.get('task_parameter_type', '')
            param_val = tasks.get('task_parameter')
            if param_val:
                for idx in sorted(self._param_inputs.keys()):
                    pinfo = self._param_inputs[idx]
                    if pinfo['type'] == 'paths' and param_type == 'path' and isinstance(param_val, list):
                        for p in param_val:
                            pinfo['widget'].append(p)
                        break
                    elif pinfo['type'] == 'text' and param_type == 'text' and isinstance(param_val, str):
                        pinfo['widget'].setPlainText(param_val)
                        break

        self.task_name.blockSignals(True)
        self.task_name.clear()
        self.task_name.addItem(tasks.get('task_name'))
        self.task_name.blockSignals(False)

    def closeEvent(self, event):
        super().closeEvent(event)
        self.task = None

    def on_ok_btn_clicked(self):
        if self.task:
            task_data = TaskDatabase().update_task(self.task.get('task_id'), self.get_current_settings())
            self.edit_finish.emit(task_data)
        else:
            result = self.get_current_settings()
            data = self.scripts_model.get(result.get("task_name"))
            result.update({"script_id": data.get("script_id")})
            icon = data.get("icon")
            if not icon:
                icon = BmTools.get_language_icon_path(data.get('script_language', 'bat'))
            result.update({"icon": icon})
            task_data = TaskDatabase().create_task(result)
            self.add_finish.emit(task_data)
        self.close()
