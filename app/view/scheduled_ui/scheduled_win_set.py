
"""
Copyright (c) 2026 綦恒智
Email: bmscriptsbox@163.com
SPDX-License-Identifier: MIT
SPDX-License-Identifier: LicenseRef-Commons-Clause
"""
import json
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass, field

from PySide2.QtCore import Qt, Signal, QTime, QTimer
from PySide2.QtWidgets import (
    QWidget, QHBoxLayout, QVBoxLayout, QGridLayout, QFormLayout,
    QButtonGroup, QStackedWidget
)
from xsideui import (
    XSpinBox, XPushButton, XLabel, XComboBox, XTimeEdit,
    XTextEdit, XButtonVariant, XColor, XDialog, XRadioButton,
    XCheckBox, XDoubleSpinBox, XLineEdit, XScrollArea, tr, XSize, XSwitch
)
from xsideui.widgets.divider import XTextDivider, XDivider
from app.data import ProjectGlobal, ScriptDatabase, TaskDatabase
from app.utils.tools import BmTools
from .scheduled_mode import TimeMode, WeekMode
from app.view.params_ui import build_param_widget as _shared_build_param_widget, \
    read_param_widget as _shared_read_param_widget, make_label_cell, make_header_row, \
    browse_append_to_edit, field_signal as _shared_field_signal, FieldLinker

try:
    from app.servers.wechat_push import WechatPushService
    HAS_WECHAT_PUSH = True
except Exception:
    HAS_WECHAT_PUSH = False
    WechatPushService = None


# task_type 存储规范：DB/调度/展示统一用英文码；中文仅为 TimeMode 的展示值，不入库
_TASK_TYPE_CODE = {
    TimeMode.FIXED_INTERVAL: 'fixed_interval',
    TimeMode.COUNTDOWN: 'countdown',
    TimeMode.DAILY: 'daily',
    TimeMode.WEEKLY: 'weekly',
    TimeMode.MONTHLY: 'monthly',
}

# 别名保留 random_interval（已废弃），供旧任务识别与回填时透明近似为固定+扰动
_TASK_TYPE_ALIASES = {
    'fixed_interval': 'fixed_interval', '固定间隔执行': 'fixed_interval',
    'random_interval': 'random_interval', '随机间隔执行': 'random_interval',
    'countdown': 'countdown', '倒计时执行': 'countdown',
    'daily': 'daily', '每天执行': 'daily',
    'weekly': 'weekly', '每周执行': 'weekly',
    'monthly': 'monthly', '每月执行': 'monthly',
}


def _normalize_task_type(task_type):
    """兼容早期版本误存的中文 task_type，统一为英文码"""
    return _TASK_TYPE_ALIASES.get(task_type, task_type)


@dataclass
class ParamField:
    """参数字段的数据结构"""
    name: str
    widget: QWidget
    ptype: str
    schema: Dict[str, Any]


class ScheduledSetWidget(XDialog):
    """定时任务设置窗口"""
    add_finish = Signal(dict)
    edit_finish = Signal(dict)

    def __init__(self, parent=None):
        super().__init__(parent=parent)
        self.task = None
        self.scripts_model = {}
        self._param_widget = None
        self._param_inputs: Dict[str, ParamField] = {}
        self._param_override_widgets: Dict[str, ParamField] = {}
        self._rebuild_timer = None
        self._run_data_divider = None

        self._setup_ui()
        self._connect_signals()
        self.setModal(True)

    # ==================== UI 初始化 ====================

    def _setup_ui(self):
        """初始化UI"""
        self.set_title(tr('Scheduled Scripts'))
        self.set_logo(BmTools.get_logo_path())
        self.hide_maximize_button()
        self.resize(800, 560)

        widget = QWidget()
        layout = QHBoxLayout(widget)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(11)

        self.left_layout = QVBoxLayout()
        right_layout = QVBoxLayout()
        layout.addLayout(self.left_layout, stretch=1)
        layout.addWidget(XDivider(vertical=True))
        layout.addLayout(right_layout, stretch=1)

        # ── 脚本 ──
        script_divider = XTextDivider(tr('Script Name'), align=Qt.AlignLeft)
        self.task_name = XComboBox(searchable=True)
        self.left_layout.addWidget(script_divider)
        self.left_layout.addWidget(self.task_name)

        # ── 运行数据 ──
        self._run_data_divider = XTextDivider(tr('Run data'), align=Qt.AlignLeft)
        self.left_layout.addWidget(self._run_data_divider)
        self.param_stacked = QStackedWidget()
        self.left_layout.addWidget(self.param_stacked)
        self.left_layout.addStretch()

        # ── 时间设置 ──
        self._setup_time_settings(right_layout)

        # ── 按键 ──
        self._setup_buttons(right_layout)

        self.addWidget(widget)

    def _setup_time_settings(self, parent_layout: QVBoxLayout):
        """设置时间选择控件"""
        time_divider = XTextDivider(tr('Scheduled Strategy'), align=Qt.AlignLeft)
        grid = QGridLayout()
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setHorizontalSpacing(8)
        grid.setVerticalSpacing(6)

        self._time_group = QButtonGroup(self)
        row = 0

        # 固定间隔（可带 ± 秒扰动）
        self._fixed_radio = XRadioButton(tr("Fixed Interval"))
        self._time_group.addButton(self._fixed_radio, 0)
        self.repeat_second = XSpinBox(suffix=" 秒")
        self.repeat_second.setRange(0, 99999)
        self.repeat_second.setFixedWidth(130)
        self.jitter_second = XSpinBox(prefix='± 秒')
        self.jitter_second.setRange(0, 99999)
        self.jitter_second.setFixedWidth(130)
        self.jitter_second.setToolTip("在固定间隔上叠加 ± 秒的随机扰动，0=纯固定")
        grid.addWidget(self._fixed_radio, row, 0)
        grid.addWidget(self.repeat_second, row, 1)
        grid.addWidget(self.jitter_second, row, 2)
        row += 1

        # 倒计时
        self._countdown_radio = XRadioButton(tr("Countdown"))
        self._time_group.addButton(self._countdown_radio, 1)
        self.countdown_second = XSpinBox(suffix=" 秒")
        self.countdown_second.setRange(0, 99999)
        self.countdown_second.setFixedWidth(130)
        grid.addWidget(self._countdown_radio, row, 0)
        grid.addWidget(self.countdown_second, row, 1)
        row += 1

        # 每天
        self._daily_radio = XRadioButton(tr("Daily"))
        self._time_group.addButton(self._daily_radio, 2)
        self.daily_time = XTimeEdit()
        self.daily_time.setFixedWidth(130)
        grid.addWidget(self._daily_radio, row, 0)
        grid.addWidget(self.daily_time, row, 1)
        row += 1

        # 每周
        self._weekly_radio = XRadioButton(tr("Weekly"))
        self._time_group.addButton(self._weekly_radio, 3)
        self.week_combobox = XComboBox()
        self.week_combobox.addItems([mode.value for mode in WeekMode])
        self.week_combobox.setFixedWidth(130)
        self.weekly_time = XTimeEdit()
        self.weekly_time.setFixedWidth(130)
        grid.addWidget(self._weekly_radio, row, 0)
        grid.addWidget(self.week_combobox, row, 1)
        grid.addWidget(self.weekly_time, row, 2)
        row += 1

        # 每月
        self._monthly_radio = XRadioButton(tr("Monthly"))
        self._time_group.addButton(self._monthly_radio, 4)
        self.monthly_day = XSpinBox(prefix='每月', suffix=" 号")
        self.monthly_day.setRange(1, 31)
        self.monthly_day.setValue(1)
        self.monthly_day.setToolTip("29-31 号在较短月份回退到当月最后一天")
        self.monthly_day.setFixedWidth(130)
        self.monthly_time = XTimeEdit()
        self.monthly_time.setFixedWidth(130)
        grid.addWidget(self._monthly_radio, row, 0)
        grid.addWidget(self.monthly_day, row, 1)
        grid.addWidget(self.monthly_time, row, 2)
        row += 1

        # 最大间隔
        interval = XTextDivider(tr('运行次数'), align=Qt.AlignLeft)
        grid.addWidget(interval, row, 0, 1, -1)
        grid.addWidget(XLabel('最大次数：'), row+1, 0)
        self.repeat_count = XSpinBox(suffix=" 次")
        self.repeat_count.setRange(0, 9999)
        self.repeat_count.setToolTip("执行次数上限，0=不限")
        self.repeat_count.setFixedWidth(130)
        grid.addWidget(self.repeat_count, row+1, 1)
        grid.addWidget(XLabel('最大次数仅对固定间隔（含扰动）策略生效，0为不限制次数').set_color(XColor.TERTIARY).set_font_size(12), row+2, 0,1 ,-1)

        # 执行结果通知：推不推按任务勾选，收件人在设置-推送页扫码绑定
        if HAS_WECHAT_PUSH:
            grid.addWidget(XTextDivider('执行结果通知', align=Qt.AlignLeft), row+3, 0, 1, -1)
            grid.addWidget(XLabel('完成后推送微信：'), row+4, 0)
            self.wechat_push_switch = XSwitch(size=XSize.SMALL, text_on='', text_off='')
            grid.addWidget(self.wechat_push_switch, row+4, 1)
            self.wechat_bind_btn = XPushButton(
                text='保存并去绑定', size=XSize.SMALL,
                variant=XButtonVariant.OUTLINED, color=XColor.TERTIARY)
            grid.addWidget(self.wechat_bind_btn, row+4, 2)
            self.wechat_hint_label = XLabel('微信未连接：保存后去扫码绑定') \
                .set_color(XColor.TERTIARY).set_font_size(12)
            grid.addWidget(self.wechat_hint_label, row+5, 0, 1, -1)

        grid.setColumnStretch(0, 0)
        grid.setColumnStretch(1, 0)
        grid.setColumnStretch(2, 0)
        grid.setColumnStretch(3, 1)

        parent_layout.addWidget(time_divider)
        parent_layout.addLayout(grid)

    def _setup_buttons(self, parent_layout: QVBoxLayout):
        """设置底部按钮"""
        btn_row = QHBoxLayout()
        btn_row.addStretch()

        self.cancel_btn = XPushButton(
            text=tr('Cancel'), variant=XButtonVariant.OUTLINED, color=XColor.TERTIARY
        )
        self.ok_btn = XPushButton(text=tr("OK"), variant=XButtonVariant.FILLED)

        btn_row.addWidget(self.cancel_btn)
        btn_row.addWidget(self.ok_btn)

        parent_layout.addStretch()
        parent_layout.addLayout(btn_row)

    # ==================== 信号连接 ====================

    def _connect_signals(self):
        """连接信号"""
        self.task_name.currentTextChanged.connect(self._on_script_changed)
        self.ok_btn.clicked.connect(self.on_ok_btn_clicked)
        self.cancel_btn.clicked.connect(self.close)
        for btn in (self._fixed_radio, self._countdown_radio,
                    self._daily_radio, self._weekly_radio, self._monthly_radio):
            btn.toggled.connect(self._update_repeat_count_enabled)
        self._update_repeat_count_enabled()  # 初始默认固定间隔选中 → 最大次数可用
        if HAS_WECHAT_PUSH:
            self.wechat_push_switch.clicked.connect(self._refresh_wechat_hint)
            self.wechat_bind_btn.clicked.connect(self._goto_wechat_bind)
        self._refresh_wechat_hint()

    def _refresh_wechat_hint(self, *args):
        """未连接时给出提示与跳转按钮；判定只读内存快照，不发网络请求。"""
        if not HAS_WECHAT_PUSH:
            return
        try:
            connected = WechatPushService.instance().connection_status() == '已连接'
        except Exception:
            connected = False
        show = not connected and self.wechat_push_switch.isChecked()
        self.wechat_bind_btn.setVisible(show)
        self.wechat_hint_label.setVisible(show)

    # ==================== 脚本管理 ====================

    def update_task_name(self):
        """更新脚本名称列表"""
        scripts = ProjectGlobal.safe_get('SCRIPTS')
        if not scripts:
            scripts = ScriptDatabase.get_all_scripts()
            ProjectGlobal.safe_set('SCRIPTS', scripts)
        data = []
        for script in scripts:
            self.scripts_model[script.name] = {
                "script_id": script.id,
                "icon": script.icon,
                "script_language": script.language,
                "inputs_schema": script.inputs_schema,
                "params_schema": script.params_schema,
            }
            # 只把声明过可被定时调度的脚本放进选择列表（opt-in）
            if getattr(script, 'schedule_enabled', False):
                data.append(script.name)

        self.task_name.clear()
        self.task_name.addItems(data)
        self.param_stacked.setCurrentIndex(0)
        self._fixed_radio.setChecked(True)
        self._update_repeat_count_enabled()
        if HAS_WECHAT_PUSH:
            # 表单是共享单例，新增前必须清掉上次编辑留下的勾选
            self.wechat_push_switch.setChecked(False)
            self._refresh_wechat_hint()

    # ==================== 参数 UI 构建 ====================

    def _rebuild_params_ui(self, inputs_schema: List[Dict], params_schema: List[Dict]):
        """重建参数UI - 核心方法"""
        # 1. 清理旧UI
        self._cleanup_old_ui()

        # 2. 构建新UI
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 11, 0)
        layout.setSpacing(6)

        # 3. 构建 inputs 区域
        has_inputs = any(i.get('name') and i.get('type') for i in (inputs_schema or []))
        if self._run_data_divider is not None:
            self._run_data_divider.setVisible(has_inputs)  # 无输入数据时不显示 "Run data" 分割线
        inputs_widget = self._build_inputs_ui(inputs_schema)
        layout.addWidget(inputs_widget)

        # 4. 构建 params 区域
        if params_schema:
            layout.addWidget(XTextDivider(tr('Script Params'), align=Qt.AlignLeft))
            params_widget = self._build_params_ui(params_schema)
            layout.addWidget(params_widget)

        # 5. 添加弹性空间
        layout.addStretch()

        # 6. 判断是否需要滚动
        self._param_widget = self._wrap_with_scroll(container, inputs_schema, params_schema)
        self.param_stacked.addWidget(self._param_widget)
        self.param_stacked.setCurrentWidget(self._param_widget)

    def _cleanup_old_ui(self):
        """清理旧的UI控件"""
        if self._param_widget:
            self.param_stacked.removeWidget(self._param_widget)
            self._param_widget.deleteLater()
            self._param_widget = None

        self._param_inputs.clear()
        self._param_override_widgets.clear()

    def _build_inputs_ui(self, inputs_schema: List[Dict]) -> QWidget:
        """构建 inputs 参数UI（堆叠：名称+描述独行在上、输入控件整行在下，与启动弹窗一致）"""
        widget = QWidget()
        lay = QVBoxLayout(widget)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(6)

        for inp in inputs_schema:
            name = inp.get('name', '')
            ptype = inp.get('type', '').lower()
            if not name or not ptype:
                continue
            exts = inp.get('exts', [])
            pick = inp.get('pick')
            edit = self._create_input_widget(ptype, exts)
            self._param_inputs[name] = ParamField(
                name=name,
                widget=edit,
                ptype='str' if ptype == 'str' else 'list',
                schema=inp
            )
            if pick and ptype == 'list':
                browse = XPushButton(text=tr('Browse'), variant=XButtonVariant.FILLED, size=XSize.SMALL)
                browse.clicked.connect(
                    lambda e=edit, pk=pick, ex=exts: browse_append_to_edit(self, e, pk, ex))
                header = make_header_row(name, inp.get('label', '') or '', trailing=browse)
            else:
                header = make_header_row(name, inp.get('label', '') or '')
            lay.addWidget(header)
            lay.addWidget(edit)

        return widget

    def _create_input_widget(self, ptype: str, exts: List[str]) -> Optional[XTextEdit]:
        """根据类型创建输入控件"""
        placeholder_map = {
            'list': '请输入路径参数 一行一个',
            'str': '请输入文本参数',
        }

        placeholder = placeholder_map.get(ptype, '请输入参数')
        if exts:
            placeholder += f"（{' '.join(exts)}）"

        edit = XTextEdit(placeholder=placeholder)
        edit.setMaximumHeight(80)
        return edit

    def _build_params_ui(self, params_schema: List[Dict]) -> QWidget:
        """构建 params 参数UI（QFormLayout：名称+描述 标签列，无前缀）"""
        self._params_linker = FieldLinker()  # 每次重建重置，联动显隐
        widget = QWidget()
        form = QFormLayout(widget)
        form.setContentsMargins(0, 0, 0, 0)
        form.setSpacing(6)
        form.setLabelAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        form.setFieldGrowthPolicy(QFormLayout.AllNonFixedFieldsGrow)

        for param in params_schema:
            name = param.get('name', '')
            if not name:
                continue
            ptype = str(param.get('type', 'str')).lower()
            w = self._build_param_widget(param)
            if ptype == 'bool':
                w.setText('')  # 标签列已展示名字，去掉开关自带文本避免重复
            self._param_override_widgets[name] = ParamField(
                name=name,
                widget=w,
                ptype=ptype,
                schema=param
            )
            label = make_label_cell(name, param.get('label', '') or '',
                                    bool(param.get('required', False)))
            form.addRow(label, w)
            self._params_linker.add(name, param, label, w, _shared_field_signal(w))

        self._params_linker.wire()
        self._params_linker.apply()
        return widget

    def _build_param_widget(self, pd: Dict) -> QWidget:
        """按 params_schema 声明类型生成参数输入控件（复用共享实现）"""
        return _shared_build_param_widget(pd)

    def _wrap_with_scroll(self, widget: QWidget, inputs: List, params: List) -> QWidget:
        """根据内容高度决定是否使用滚动区域"""
        input_count = len([i for i in inputs if i.get('name') and i.get('type')])
        param_count = len([p for p in params if p.get('name')])
        total_fields = input_count + param_count

        if total_fields > 12:
            scroll = XScrollArea()
            scroll.setWidget(widget)
            scroll.setWidgetResizable(True)
            return scroll

        return widget

    # ==================== 数据读取 ====================

    def _collect_inputs_value(self) -> Tuple[str, Any]:
        """
        收集 inputs 参数值
        Returns:
            (param_type, param_value): 参数类型和值
        """
        if not self._param_inputs:
            return '', ''

        for name, field in self._param_inputs.items():
            widget = field.widget
            if isinstance(widget, XTextEdit):
                text = widget.toPlainText().strip()
                if text:
                    if field.ptype == 'str':
                        return 'text', text
                    else:
                        lines = [line.strip() for line in text.splitlines() if line.strip()]
                        return 'path', lines

        return '', ''

    def _collect_params_overrides(self) -> Dict[str, Any]:
        """收集 params 覆盖值（当前联动隐藏字段不收集）"""
        overrides = {}
        for name, field in self._param_override_widgets.items():
            if not self._params_linker.is_visible(name):  # 联动隐藏字段不注入
                continue
            val = self._read_param_widget(field.widget, field.ptype)
            if val is not None:
                overrides[name] = val
        return overrides

    def _read_param_widget(self, w: QWidget, ptype: str) -> Any:
        """从参数控件读取值；空值返回 None 表示不覆盖（复用共享实现）"""
        return _shared_read_param_widget(w, ptype)

    # ==================== 数据填充 ====================

    def _fill_inputs_value(self, param_type: str, param_value: Any):
        """填充 inputs 值（编辑时回填）"""
        if not param_value or not self._param_inputs:
            return

        for name, field in self._param_inputs.items():
            widget = field.widget
            if not isinstance(widget, XTextEdit):
                continue

            if field.ptype == 'list' and param_type == 'path' and isinstance(param_value, list):
                widget.setPlainText('\n'.join(str(p) for p in param_value))
                break
            elif field.ptype == 'str' and param_type == 'text' and isinstance(param_value, str):
                widget.setPlainText(param_value)
                break

    def _fill_param_widget(self, w: QWidget, value: Any, ptype: str):
        """编辑任务时回填参数覆盖值"""
        if isinstance(w, XCheckBox):
            w.setChecked(bool(value))
        elif isinstance(w, XComboBox):
            w.setCurrentText(str(value))
        elif isinstance(w, XDoubleSpinBox):
            try:
                w.setValue(float(value))
            except Exception:
                pass
        elif isinstance(w, XSpinBox):
            try:
                w.setValue(int(value))
            except Exception:
                pass
        elif isinstance(w, XLineEdit):
            w.setText(str(value))
        elif isinstance(w, XTextEdit):
            if ptype == 'list' and isinstance(value, list):
                w.setPlainText('\n'.join(str(x) for x in value))
            elif ptype == 'dict' and isinstance(value, dict):
                try:
                    w.setPlainText(json.dumps(value, ensure_ascii=False, indent=2))
                except Exception:
                    w.setPlainText(str(value))
            else:
                w.setPlainText(str(value))

    def _fill_params_overrides(self, task_params: Dict[str, Any]):
        """填充参数覆盖值"""
        for name, field in self._param_override_widgets.items():
            if name in task_params:
                self._fill_param_widget(field.widget, task_params[name], field.ptype)

    # ==================== 时间模式管理 ====================

    def _get_selected_mode(self) -> TimeMode:
        """获取选中的时间模式"""
        idx = self._time_group.checkedId()
        mapping = {
            0: TimeMode.FIXED_INTERVAL,
            1: TimeMode.COUNTDOWN,
            2: TimeMode.DAILY,
            3: TimeMode.WEEKLY,
            4: TimeMode.MONTHLY,
        }
        return mapping.get(idx, TimeMode.FIXED_INTERVAL)

    def _update_repeat_count_enabled(self):
        """最大次数仅固定间隔（含扰动）策略可用，其余策略禁用"""
        enabled = self._get_selected_mode() == TimeMode.FIXED_INTERVAL
        self.repeat_count.setEnabled(enabled)

    def _set_mode_by_type(self, task_type: str):
        """根据任务类型设置时间模式；已废弃的随机间隔回填为固定间隔"""
        code = _normalize_task_type(task_type)
        if code == 'random_interval':
            code = 'fixed_interval'
        mapping = {
            'fixed_interval': 0,
            'countdown': 1,
            'daily': 2,
            'weekly': 3,
            'monthly': 4,
        }
        idx = mapping.get(code)
        btn = self._time_group.button(idx)
        if btn:
            btn.setChecked(True)
        self._update_repeat_count_enabled()

    def _get_time_config(self, mode: TimeMode) -> Dict[str, Any]:
        """获取时间配置"""
        config = {"task_type": _TASK_TYPE_CODE[mode]}

        if mode == TimeMode.FIXED_INTERVAL:
            config["interval_seconds"] = self.repeat_second.value()
            config["jitter_seconds"] = self.jitter_second.value()
            config["max_run_count"] = self.repeat_count.value() or None
        elif mode == TimeMode.COUNTDOWN:
            config["delay_seconds"] = self.countdown_second.value()
        elif mode == TimeMode.DAILY:
            config["daily_time"] = self.daily_time.time().toString()
        elif mode == TimeMode.WEEKLY:
            idx = self.week_combobox.currentIndex()
            weekday = list(WeekMode)[idx].value
            config.update({
                "weekly_weekday": weekday,
                "weekly_time": self.weekly_time.time().toString(),
            })
        elif mode == TimeMode.MONTHLY:
            config.update({
                "monthly_day": self.monthly_day.value(),
                "monthly_time": self.monthly_time.time().toString(),
            })

        return config

    def _fill_time_values(self, tasks: Dict[str, Any]):
        """填充时间控件的值"""
        task_type = _normalize_task_type(tasks.get('task_type'))

        if task_type == 'fixed_interval':
            self.repeat_second.setValue(tasks.get('interval_seconds', 0))
            self.jitter_second.setValue(tasks.get('jitter_seconds') or 0)
            self.repeat_count.setValue(tasks.get('max_run_count') or 0)
        elif task_type == 'random_interval':
            # 旧随机任务：以区间均值作固定间隔、半幅作扰动回填（模式已由 _set_mode_by_type 切到固定）
            lo = tasks.get('min_interval_seconds') or 0
            hi = tasks.get('max_interval_seconds') or 0
            if lo > hi:
                lo, hi = hi, lo
            self.repeat_second.setValue((lo + hi) // 2)
            self.jitter_second.setValue((hi - lo) // 2)
            self.repeat_count.setValue(tasks.get('max_run_count') or 0)
        elif task_type == 'countdown':
            self.countdown_second.setValue(tasks.get('delay_seconds', 0))
        elif task_type == 'daily':
            time_str = tasks.get('daily_time')
            if time_str:
                self.daily_time.setTime(QTime.fromString(time_str))
        elif task_type == 'weekly':
            weekday_val = tasks.get('weekly_weekday', '')
            modes = list(WeekMode)
            for i, m in enumerate(modes):
                if m.value.lower() == weekday_val.lower():
                    self.week_combobox.setCurrentIndex(i)
                    break
            time_str = tasks.get('weekly_time')
            if time_str:
                self.weekly_time.setTime(QTime.fromString(time_str))
        elif task_type == 'monthly':
            self.monthly_day.setValue(tasks.get('monthly_day') or 1)
            time_str = tasks.get('monthly_time')
            if time_str:
                self.monthly_time.setTime(QTime.fromString(time_str))

    # ==================== 槽函数 ====================

    def _on_script_changed(self, script_name: str):
        """脚本切换事件 - 带防抖"""
        if not script_name:
            return

        script_info = self.scripts_model.get(script_name)
        if not script_info:
            return

        # 使用 QTimer 防抖
        if self._rebuild_timer is None:
            self._rebuild_timer = QTimer()
            self._rebuild_timer.setSingleShot(True)

        self._rebuild_timer.stop()
        # 保存当前脚本信息供定时器使用
        self._pending_script_info = script_info
        self._rebuild_timer.timeout.connect(self._do_rebuild_params)
        self._rebuild_timer.start(100)

    def _do_rebuild_params(self):
        """执行参数重建（防抖后的实际执行）"""
        if hasattr(self, '_pending_script_info') and self._pending_script_info:
            info = self._pending_script_info
            self._rebuild_params_ui(
                info.get('inputs_schema', []),
                info.get('params_schema', [])
            )
            self._pending_script_info = None

    def get_current_settings(self) -> Dict[str, Any]:
        """获取当前设置"""
        current_mode = self._get_selected_mode()
        settings = {
            "task_name": self.task_name.currentText(),
            "is_active": True,
        }

        # 时间设置
        time_config = self._get_time_config(current_mode)
        settings.update(time_config)

        # inputs 参数
        param_type, param_value = self._collect_inputs_value()
        settings.update({
            "task_parameter_type": param_type,
            "task_parameter": param_value
        })

        # params 覆盖
        settings["task_params"] = self._collect_params_overrides()

        if HAS_WECHAT_PUSH:
            settings["wechat_push"] = self.wechat_push_switch.isChecked()

        return settings

    def update_task_data(self, tasks: Dict[str, Any]):
        """更新任务数据（编辑模式）"""
        self.task = tasks

        if not self.scripts_model:
            self.update_task_name()

        if HAS_WECHAT_PUSH:
            self.wechat_push_switch.setChecked(bool(tasks.get('wechat_push')))
            self._refresh_wechat_hint()

        # 设置时间模式
        self._set_mode_by_type(tasks.get('task_type'))
        self._fill_time_values(tasks)

        # 获取脚本信息并重建 UI
        script_info = self.scripts_model.get(tasks.get('task_name'))
        if script_info:
            # 暂时断开信号，避免触发重建
            self.task_name.blockSignals(True)

            # 重建 UI
            self._rebuild_params_ui(
                script_info.get('inputs_schema', []),
                script_info.get('params_schema', [])
            )

            # 填充数据
            self._fill_inputs_value(
                tasks.get('task_parameter_type', ''),
                tasks.get('task_parameter')
            )

            self._fill_params_overrides(tasks.get('task_params') or {})

            # 恢复信号并设置当前项
            self.task_name.clear()
            self.task_name.addItem(tasks.get('task_name'))
            self.task_name.blockSignals(False)

    def _persist_task(self):
        """把当前表单落库并发出对应信号（编辑→update，新增→create），返回任务字典"""
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
        return task_data

    def on_ok_btn_clicked(self):
        """确认按钮点击事件"""
        self._persist_task()
        self.close()

    def _goto_wechat_bind(self):
        """本窗是模态，跳不了主窗，所以先保存再关窗，把用户送到推送页扫码绑定。"""
        self._persist_task()
        self.close()
        # QDialog 本身就是 window()，所以要从自己往上找带跳转能力的主窗
        widget = self
        while widget is not None and not hasattr(widget, 'open_wechat_push_page'):
            widget = widget.parentWidget()
        if widget is not None:
            widget.open_wechat_push_page()

    def closeEvent(self, event):
        """关闭事件"""
        super().closeEvent(event)
        self.task = None
        if self._rebuild_timer:
            self._rebuild_timer.stop()
