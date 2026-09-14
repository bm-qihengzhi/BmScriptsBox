"""
Copyright (c) 2026 綦恒智
Email: bmscriptsbox@163.com
SPDX-License-Identifier: MIT
SPDX-License-Identifier: LicenseRef-Commons-Clause
"""
import json
from typing import Any, Dict

from PySide2.QtCore import Qt
from PySide2.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QFileDialog

from xsideui import XCheckBox, XDoubleSpinBox, XSpinBox, XComboBox, XLineEdit, XTextEdit, XLabel


def make_header_row(name: str, label: str, trailing=None) -> QWidget:
    """水平标题行：主标签 = label（缺省回退 name）；trailing（如「浏览…」）贴最右"""
    row = QWidget()
    lay = QHBoxLayout(row)
    lay.setContentsMargins(0, 0, 0, 0)
    lay.setSpacing(8)
    display = label or name
    main = XLabel(display)
    main.setWordWrap(True)
    lay.addWidget(main, 1)
    if trailing is not None:
        lay.addWidget(trailing)
    return row


def browse_append_to_edit(parent: QWidget, edit: QWidget, pick: str, exts: list):
    """打开原生文件/文件夹选择器，把所选路径追加成多行框新行（显式实例+显式模态+同步 exec_）"""
    dialog = QFileDialog(parent)
    dialog.setWindowModality(Qt.WindowModal)  # 显式模态，保证 Qt 焦点系统正常
    if pick == 'folders':
        dialog.setFileMode(QFileDialog.Directory)
        dialog.setOption(QFileDialog.ShowDirsOnly, True)
    else:
        dialog.setFileMode(QFileDialog.ExistingFiles)
        if exts:
            dialog.setNameFilter('Supported (' + ' '.join(f'*{e}' for e in exts) + ')')

    if not dialog.exec_():
        return
    paths = dialog.selectedFiles()
    if not paths:
        return

    existing = edit.toPlainText()
    lines = [l for l in existing.splitlines() if l.strip()]
    seen = set(lines)
    for p in paths:
        if p not in seen:
            lines.append(p)
            seen.add(p)
    edit.setPlainText('\n'.join(lines))


def condition_met(rule: Dict, ref_value) -> bool:
    """判定字段联动的 when 条件：无 when → True；eq 精确匹配；in 命中列表"""
    when = (rule or {}).get('when')
    if not when:
        return True
    s = str(ref_value)
    if 'eq' in when:
        return s == str(when['eq'])
    if 'in' in when:
        return s in [str(x) for x in when['in']]
    return True


def field_signal(widget):
    """取控件「值变化」信号，供字段联动监听"""
    if isinstance(widget, XCheckBox):
        return widget.toggled
    if isinstance(widget, XComboBox):
        return widget.currentTextChanged
    if isinstance(widget, (XDoubleSpinBox, XSpinBox)):
        return widget.valueChanged
    if isinstance(widget, (XLineEdit, XTextEdit)):
        return widget.textChanged
    return None


class FieldLinker:
    """FormCreate 式字段联动：带 when 的字段，按被依赖字段当前值整体显隐"""

    def __init__(self):
        self._rows = {}   # name -> {'rule':..., 'label':..., 'field':..., 'signal':...}
        self._wired = False

    def add(self, name: str, rule: Dict, label_widget, field_widget, signal=None, row=None):
        self._rows[name] = {
            'rule': rule, 'label': label_widget, 'field': field_widget,
            'signal': signal, 'row': row,
        }

    def _ptype(self, rule) -> str:
        return str((rule or {}).get('type', 'str')).lower()

    def _read_ref(self, name):
        row = self._rows.get(name)
        if not row:
            return None
        try:
            return read_param_widget(row['field'], self._ptype(row['rule']))
        except Exception:
            return None

    def wire(self):
        """把每个带 when 的字段，接到其 when.field 控件的值变化信号"""
        if self._wired:
            return
        for row in self._rows.values():
            when = (row['rule'] or {}).get('when')
            if not when:
                continue
            ref = self._rows.get(when.get('field'))
            if ref and ref.get('signal'):
                ref['signal'].connect(lambda *a: self.apply())
        self._wired = True

    def apply(self):
        """按当前依赖值 + 父字段可见性，重算每个字段的显隐（有 row 则整行收起，避免占位）"""
        for name in list(self._rows.keys()):
            r = self._rows[name]
            v = self._parent_visible(name)
            if r.get('row') is not None:
                r['row'].setVisible(v)
            else:
                r['label'].setVisible(v)
                r['field'].setVisible(v)

    def is_visible(self, name: str) -> bool:
        """某字段当前是否可见（收集时跳过不可见字段用）"""
        return self._parent_visible(name)

    def _parent_visible(self, name: str, _seen=None) -> bool:
        """最终可见性 = 自身 when 取值条件 且 被依赖字段可见（递归级联，_seen 防环）"""
        row = self._rows.get(name)
        if not row:
            return True
        rule = row['rule'] or {}
        when = rule.get('when')
        if not when:
            return True
        ref = when.get('field')
        # 取值条件：如 {field=X, eq=V} / {field, in=[..]}
        if not condition_met(rule, self._read_ref(ref)):
            return False
        if ref not in self._rows:
            return True
        if _seen is None:
            _seen = set()
        if name in _seen:
            return True
        _seen.add(name)
        return self._parent_visible(ref, _seen)


def make_label_cell(name: str, label: str, required: bool) -> QWidget:
    """参数标签列：主标签 = label（缺省回退 name），必填加 *"""
    cell = QWidget()
    lay = QVBoxLayout(cell)
    lay.setContentsMargins(0, 0, 8, 0)
    lay.setSpacing(2)

    display = label or name
    main = XLabel(f"{display} *" if required else display)
    main.setWordWrap(True)
    lay.addWidget(main)

    lay.addStretch()
    return cell


def build_param_widget(pd: Dict) -> QWidget:
    """按 params_schema 声明类型生成参数输入控件"""
    ptype = str(pd.get('type', 'str')).lower()
    default = pd.get('default')
    choices = pd.get('choices') or []
    choice_labels = pd.get('choice_labels') or {}
    desc = pd.get('description', '') or ''
    secret = pd.get('secret', False)

    if ptype == 'bool':
        return XCheckBox(pd.get('name', ''), checked=bool(default))

    if ptype in ('int', 'float'):
        if ptype == 'int':
            w = XSpinBox()
            w.setRange(-2 ** 31, 2 ** 31 - 1)
        else:
            w = XDoubleSpinBox()
            w.setDecimals(6)
            w.setRange(-1e10, 1e10)
        if isinstance(default, (int, float)) and not isinstance(default, bool):
            try:
                w.setValue(float(default))
            except Exception:
                pass
        return w

    if ptype == 'str' and choices:
        w = XComboBox(searchable=True if len(choices) > 10 else False)
        for c in choices:  # 显示显示名（无则取值本身），携带 userData=取值
            w.addItem(text=str(choice_labels.get(c, c)), userData=str(c))
        if default is not None and str(default) in [str(c) for c in choices]:
            idx = w.findData(str(default))  # 按取值预选，而非按显示文本
            if idx >= 0:
                w.setCurrentIndex(idx)
        return w

    if ptype == 'list':
        w = XTextEdit(placeholder='每行一条，回车分隔')
        w.setMaximumHeight(80)
        if isinstance(default, list):
            w.setPlainText('\n'.join(str(x) for x in default))
        return w

    if ptype == 'dict':
        w = XTextEdit(placeholder='JSON 格式，如 {"key": "value"}')
        w.setMaximumHeight(80)
        if isinstance(default, dict):
            try:
                w.setPlainText(json.dumps(default, ensure_ascii=False, indent=2))
            except Exception:
                pass
        return w

    w = XLineEdit(placeholder=desc, show_password=bool(secret))
    if default is not None:
        w.setText(str(default))
    return w


def write_param_widget(w: QWidget, ptype: str, value: Any) -> None:
    """把记忆/默认值回填进参数控件（read_param_widget 的镜子）；value 为 None 跳过"""
    if value is None:
        return
    if isinstance(w, XCheckBox):
        w.setChecked(bool(value))
    elif isinstance(w, XComboBox):
        idx = w.findData(str(value))   # 按取值（userData）选中
        if idx >= 0:
            w.setCurrentIndex(idx)
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
        if ptype == 'list' and isinstance(value, (list, tuple)):
            w.setPlainText('\n'.join(str(x) for x in value))
        elif ptype == 'dict' and isinstance(value, dict):
            try:
                w.setPlainText(json.dumps(value, ensure_ascii=False, indent=2))
            except Exception:
                pass
        else:
            w.setPlainText(str(value))


def read_param_widget(w: QWidget, ptype: str) -> Any:
    """从参数控件读取值；空值返回 None 表示不覆盖"""
    if isinstance(w, XCheckBox):
        return w.isChecked()
    if isinstance(w, XComboBox):
        data = w.currentData()   # 优先取携带的取值；无 userData 则回退显示文本
        return data if data is not None else w.currentText()
    if isinstance(w, XDoubleSpinBox):
        return w.value()
    if isinstance(w, XSpinBox):
        return w.value()
    if isinstance(w, XLineEdit):
        text = w.text().strip()
        return text if text else None
    if isinstance(w, XTextEdit):
        text = w.toPlainText().strip()
        if not text:
            return None
        if ptype == 'list':
            return [line.strip() for line in text.splitlines() if line.strip()]
        if ptype == 'dict':
            try:
                return json.loads(text)
            except Exception:
                return text
        return text
    return None