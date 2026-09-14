"""
Copyright (c) 2026 綦恒智
Email: bmscriptsbox@163.com
SPDX-License-Identifier: MIT
SPDX-License-Identifier: LicenseRef-Commons-Clause

参数化启动对话框：脚本声明 [bmscriptsbox.params_form] 后，
交互式运行时先弹出此表单，收集 params 覆盖值再启动。
表单布局：一行一个参数，左侧为「参数名（必填 *）+ 描述」标签列。
"""
from typing import Any, Dict, List

from PySide2.QtCore import Qt
from PySide2.QtWidgets import (QVBoxLayout, QHBoxLayout, QWidget)

from xsideui import (XPushButton, XButtonVariant, XColor, tr, XDialog, XHeaderCard,
                     XSize, XUpload, XListWidget, XMenu, XIcon, IconName)

from app.view.params_ui import (build_param_widget, read_param_widget, write_param_widget,
                                make_label_cell, make_header_row,
                                field_signal, FieldLinker)
from app.utils.tools import BmTools



class ParamsPromptDialog(XDialog):
    """按脚本 params_schema 自动生成参数设置表单（一行一参数，联动隐藏整行收起）"""

    def __init__(self, script_data, parent=None, default_data=None, prefill_params=None):
        super().__init__(parent)
        self.script = script_data
        self._widgets: Dict[str, Any] = {}  # name -> (widget, ptype) 运行参数
        self._inputs_widgets: Dict[str, Any] = {}  # name -> (widget, ptype) 数据参数
        self._linker = FieldLinker()  # 运行参数联动显隐
        self._pick_upload = None
        self._pick_edit = None
        self._pick_text_row = None

        self._setup_ui()
        if default_data:
            self.set_default_data(default_data)
        if prefill_params:
            self.set_prefill_params(prefill_params)

    def _setup_ui(self):
        self.set_title(f"{self.script.name} - {self.script.version}")
        icon = self.script.icon
        if not icon:
            icon = BmTools.get_language_icon_path(self.script.language)
        self.set_logo(icon)

        # 内容体（滚动区唯一的内容容器）
        body = QWidget()
        self.addWidget(body)
        inputs = list(self.script.inputs_schema or [])
        help_btn = XPushButton(icon=IconName.HELP , variant=XButtonVariant.TEXT,
                               color=XColor.SECONDARY, size=XSize.SMALL)
        help_btn.setToolTip(tr('查看脚本详情'))
        help_btn.clicked.connect(self._open_detail)
        if any(i.get('pick') for i in inputs):
            self.setMinimumHeight(720)
            # 左右布局：左侧 XUpload（选中后切 textedit），右侧 参数/非 pick 输入
            hlay = QHBoxLayout(body)
            hlay.setContentsMargins(20, 20, 20, 11)
            hlay.setSpacing(16)
            pick_inp = next(i for i in inputs if i.get('pick'))
            hlay.addWidget(self._build_pick_panel(pick_inp), 1)

            input_card = XHeaderCard(title="执行参数", header_padding=(11, 6, 11, 6))
            input_card.addWidget(self._build_params_form([i for i in inputs if not i.get('pick')]))
            input_card.addWidget(help_btn, target=XHeaderCard.CardPosition.HEADER)
            hlay.addWidget(input_card, 0)
        else:
            # 垂直堆叠：数据输入 + 运行参数
            self.title_bar.add_widget(help_btn)
            self.setMinimumWidth(380)
            vlay = QVBoxLayout(body)
            vlay.setContentsMargins(20, 20, 20, 11)
            vlay.setSpacing(20)
            vlay.addWidget(self._build_params_form(inputs))
            vlay.addStretch()

        # 后台触发（热键/右键）时盒子非前台应用，置顶防被其它程序遮挡
        self.setWindowFlag(Qt.WindowStaysOnTopHint, True)
        self.raise_()

    def _build_params_form(self, nonpick_inputs: List[Dict]) -> QWidget:
        """参数区：非 pick 的 inputs（堆叠）+ 运行参数（VBox 行 + 联动，隐藏时整行收起）"""

        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(16)


        if nonpick_inputs:
            lay.addWidget(self._build_nonpick_inputs(nonpick_inputs))

        if self.script.params_schema:
            form_box = QVBoxLayout()
            form_box.setContentsMargins(0, 0, 0, 0)
            form_box.setSpacing(6)
            for param in self.script.params_schema or []:
                name = param.get('name', '')
                if not name:
                    continue
                ptype = str(param.get('type', 'str')).lower()
                wg = build_param_widget(param)
                if ptype == 'bool':
                    wg.setText('')  # 标签列已展示参数名，去掉开关自带文本避免重复
                self._widgets[name] = (wg, ptype)
                label_cell = self._make_label_cell(
                    name, param.get('label', '') or '', bool(param.get('required', False)))
                label_cell.setMinimumWidth(100)  # 对齐标签列
                row = QWidget()
                rl = QHBoxLayout(row)
                rl.setContentsMargins(0, 0, 0, 0)
                rl.setSpacing(8)
                rl.addWidget(label_cell, 0, Qt.AlignTop)
                rl.addWidget(wg, 1)
                form_box.addWidget(row)
                # row 让联动隐藏时整行收起（QFormLayout 会留空行，VBox 行容器不会）
                self._linker.add(name, param, label_cell, wg, field_signal(wg), row=row)
            lay.addLayout(form_box)
        lay.addStretch()

        btn_row = QHBoxLayout()
        btn_row.addStretch()
        cancel_btn = XPushButton(text=tr('Cancel'),variant=XButtonVariant.OUTLINED, color=XColor.SECONDARY)
        cancel_btn.clicked.connect(self.reject)
        btn_row.addWidget(cancel_btn)
        run_btn = XPushButton(text=tr('Run'))
        run_btn.clicked.connect(self.accept)
        btn_row.addWidget(run_btn)
        lay.addLayout(btn_row, 0)

        self._linker.wire()
        self._linker.apply()
        return w

    def _build_nonpick_inputs(self, inputs: List[Dict]) -> QWidget:
        """非 pick 的 inputs：堆叠（标签行在上、字段整行在下）"""
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(8)
        for inp in inputs:
            name = inp.get('name', '')
            ptype = str(inp.get('type', 'str')).lower()
            ilabel = inp.get('label', '') or ''
            if not name or not ptype:
                continue
            edit = build_param_widget(inp)
            self._inputs_widgets[name] = (edit, ptype)
            lay.addWidget(self._make_header_row(name, ilabel))
            lay.addWidget(edit)
        return w

    def _build_pick_panel(self, inp: Dict) -> QWidget:
        """左侧取件面板：外层 XHeaderCard；XUpload 选文件（无边框）；选中后切 XListWidget（无边框）展示"""
        name = inp.get('name', '')
        pick = inp.get('pick')
        ilabel = inp.get('label', '') or ''
        mode_map = {'files': XUpload.MODE_FILES, 'folders': XUpload.MODE_FOLDERS,
                    'both': XUpload.MODE_BOTH}
        mode = mode_map.get(pick, XUpload.MODE_FILES)

        list_w = XListWidget(show_border=False)
        list_w.setMinimumHeight(180)
        self._inputs_widgets[name] = (list_w, 'list')
        self._pick_edit = list_w
        self._pick_text_row = list_w
        # 右键菜单：上移 / 下移 / 删除
        list_w.setContextMenuPolicy(Qt.CustomContextMenu)
        list_w.customContextMenuRequested.connect(self._show_pick_menu)

        upload = XUpload(mode=mode, accept_types=inp.get('exts') or ['*'],
                         mini_height=180, show_border=False)
        upload.files_processed.connect(lambda paths, nm=name: self._on_pick_paths(nm, paths))
        self._pick_upload = upload

        content = QWidget()
        content.setMinimumWidth(600)
        lay = QVBoxLayout(content)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(8)
        lay.addWidget(upload)
        lay.addWidget(list_w)
        list_w.setVisible(False)

        card = XHeaderCard(title=ilabel or name, header_padding=(11, 6, 11, 6)).addWidget(content)

        reselect_btn = XPushButton(icon=IconName.REDO, variant=XButtonVariant.TEXT, size=XSize.SMALL)
        reselect_btn.setToolTip("重新选择")
        reselect_btn.clicked.connect(lambda: self._show_pick_mode(True))
        card.addWidget(reselect_btn, target=XHeaderCard.CardPosition.HEADER)

        return card

    def _show_pick_mode(self, show_upload: bool):
        """True=显示 XUpload；False=显示 textedit（重新选择）"""
        if self._pick_upload is not None:
            self._pick_upload.setVisible(show_upload)
        if self._pick_text_row is not None:
            self._pick_text_row.setVisible(not show_upload)

    def _on_pick_paths(self, name: str, paths: list):
        lw = self._pick_edit
        if lw is None:
            return
        existing = {lw.item(i).text() for i in range(lw.count())}
        for p in paths:
            if p and p not in existing:
                lw.addItem(str(p))
                existing.add(p)
        self._show_pick_mode(False)

    def _show_pick_menu(self, pos):
        """列表项右键菜单：上移/下移/置顶/置底/删除/清空全部"""
        lw = self._pick_edit
        if lw is None:
            return
        item = lw.itemAt(pos)
        if item is None:
            return
        row = lw.row(item)
        menu = XMenu(parent=lw)
        menu.add_action(text=tr('上移'),
                        icon=XIcon.get(IconName.UP_ARROW, color=XColor.PRIMARY).icon(),
                        triggered=lambda: self._move_pick_item(row, -1))
        menu.add_action(text=tr('下移'),
                        icon=XIcon.get(IconName.DOWN_ARROW, color=XColor.PRIMARY).icon(),
                        triggered=lambda: self._move_pick_item(row, 1))
        menu.add_action(text=tr('置顶'),
                        icon=XIcon.get(IconName.TO_TOP, color=XColor.PRIMARY).icon(),
                        triggered=lambda: self._move_pick_top(row))
        menu.add_action(text=tr('置底'),
                        icon=XIcon.get(IconName.TO_BOTTOM, color=XColor.PRIMARY).icon(),
                        triggered=lambda: self._move_pick_bottom(row))
        menu.add_action(text=tr('删除'),
                        icon=XIcon.get(IconName.DELETE, color=XColor.DANGER).icon(),
                        triggered=lambda: self._delete_pick_item(row))
        menu.add_action(text=tr('清空全部'),
                        icon=XIcon.get(IconName.MINUS_CIRCLE, color=XColor.DANGER).icon(),
                        triggered=self._clear_pick_list)
        menu.exec_(lw.viewport().mapToGlobal(pos))

    def _move_pick_item(self, row: int, delta: int):
        """上移(-1)/下移(+1)某行，选中跟随"""
        lw = self._pick_edit
        new = row + delta
        if lw is None or row < 0 or new < 0 or new >= lw.count():
            return
        item = lw.takeItem(row)
        lw.insertItem(new, item)
        lw.setCurrentRow(new)

    def _move_pick_top(self, row: int):
        """把某行置顶"""
        lw = self._pick_edit
        if lw is None or row <= 0:
            return
        item = lw.takeItem(row)
        lw.insertItem(0, item)
        lw.setCurrentRow(0)

    def _move_pick_bottom(self, row: int):
        """把某行置底"""
        lw = self._pick_edit
        if lw is None or row < 0 or row >= lw.count() - 1:
            return
        item = lw.takeItem(row)
        lw.addItem(item)
        lw.setCurrentRow(lw.count() - 1)

    def _delete_pick_item(self, row: int):
        """删除某行；删空后切回 XUpload"""
        lw = self._pick_edit
        if lw is not None and row >= 0:
            lw.takeItem(row)
            if lw.count() == 0:
                self._show_pick_mode(True)

    def _clear_pick_list(self):
        """清空全部列表项，并切回 XUpload 取件模式"""
        lw = self._pick_edit
        if lw is not None:
            lw.clear()
        self._show_pick_mode(True)

    def _open_detail(self):
        """打开该脚本的社区详情页；本地安装的脚本无详情页，点击无反应"""
        if self.script.badge == '本地':
            return
        import webbrowser
        from app.data import ProjectGlobal
        webbrowser.open_new_tab(f"{ProjectGlobal.API_GATEWAY}/detail/{self.script.id}")

    def _make_header_row(self, name: str, label: str, trailing=None) -> QWidget:
        """水平标题行（复用共享实现）"""
        return make_header_row(name, label, trailing)

    def _make_label_cell(self, name: str, label: str, required: bool) -> QWidget:
        """表单标签列（复用共享实现）"""
        return make_label_cell(name, label, required)

    def set_default_data(self, default_data: List[str]):
        """把触发携带的数据预填进「数据输入」（str→文本、XTextEdit→逐行、XListWidget→逐项）"""
        if not default_data:
            return
        for name, (widget, ptype) in self._inputs_widgets.items():
            if ptype == 'str':
                text = default_data[0] if default_data else ''
                if hasattr(widget, 'setText'):
                    widget.setText(str(text))
            elif isinstance(widget, XListWidget):  # pick 输入：逐项加入
                widget.clear()
                for x in default_data:
                    widget.addItem(str(x))
            else:  # list → 每行一条路径
                if hasattr(widget, 'setPlainText'):
                    widget.setPlainText('\n'.join(str(x) for x in default_data))
            break  # inputs 最多 1 条
        self._show_pick_mode(False)  # 预填后若为 pick 输入，直接展示列表（隐藏 XUpload）

    def set_prefill_params(self, prefill: Dict[str, Any]):
        """把上次确认的 params 记忆值回填到运行参数控件（记忆优先，回退 toml 默认）"""
        for name, (widget, ptype) in self._widgets.items():
            if name in prefill:
                write_param_widget(widget, ptype, prefill.get(name))

    def get_inputs_value(self) -> List[str]:
        """收集数据参数（inputs；str→单元素数组，list→路径数组，pick→路径模型）"""
        for name, (widget, ptype) in self._inputs_widgets.items():
            if ptype == 'str':
                val = read_param_widget(widget, ptype)
                return [val] if val else []
            if isinstance(widget, XListWidget):  # pick 输入：列出各项
                return [widget.item(i).text() for i in range(widget.count())]
            val = read_param_widget(widget, ptype)
            return val or []
        return []

    def get_params_overrides(self) -> Dict[str, Any]:
        """收集 params 覆盖值（空值、当前隐藏字段不收集）"""
        overrides = {}
        for name, (widget, ptype) in self._widgets.items():
            if not self._linker.is_visible(name):  # 联动隐藏字段不注入
                continue
            val = read_param_widget(widget, ptype)
            if val is not None:
                overrides[name] = val
        return overrides