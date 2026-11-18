"""
Copyright (c) 2026 綦恒智
Email: bmscriptsbox@163.com
SPDX-License-Identifier: MIT
SPDX-License-Identifier: LicenseRef-Commons-Clause
"""
import time

from PySide6.QtCore import Qt, Signal, QTimer, QEvent, QRect, QSize
from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QFrame, \
    QStackedLayout, QStackedWidget, QListWidgetItem, QAbstractItemView

from xsideui import XPushButton, XFlowLayout, XLineEdit, XCarousel, XLabel, XImage, IconName, XIcon, XColor, \
    XScrollArea, XListWidget, tr, theme_manager

from .script_actions import popup_script_menu
from .script_list_item import ScriptListItemWidget
from .script_win_card import ScriptCard
from .script_pr import ScriptPresenter


_CARD_BATCH = 32


class CardFlowLayout(XFlowLayout):
    TARGET_CARD_W = 180

    @classmethod
    def column_count(cls, available, spacing):
        if available <= 0:
            return 1
        max_cols = max(
            1, (available + spacing)
            // (ScriptCard.MIN_CARD_W + spacing))
        preferred = max(
            1, int((available + spacing)
                   / (cls.TARGET_CARD_W + spacing) + 0.5))
        return max(1, min(preferred, max_cols))

    def _do_layout(self, rect, test_only=False):
        items = self._items
        if not items:
            return 0

        margin = self.contentsMargins()
        available = (
            rect.width() - margin.left() - margin.right())
        spacing = self.spacing()
        cols = self.column_count(available, spacing)
        card_w = max(
            0, (available - (cols - 1) * spacing) // cols)
        card_h = max(item.sizeHint().height() for item in items)
        rows = (len(items) + cols - 1) // cols

        for index, item in enumerate(items):
            row = index // cols
            col = index % cols
            x = rect.x() + margin.left() + col * (card_w + spacing)
            y = rect.y() + margin.top() + row * (card_h + spacing)
            if not test_only:
                item.setGeometry(QRect(x, y, card_w, card_h))

        return (
            margin.top() + rows * card_h
            + max(0, rows - 1) * spacing + margin.bottom())


class ScriptsWidget(QWidget):
    """脚本展示视图 - 负责 UI 渲染和用户交互"""

    login_signal = Signal(bool)
    ScriptHub = Signal()
    global_search_requested = Signal(str)

    # Banner 图约定 2400x320（约 7.5:1，2x）；固定显示高度 160，配合 contain 保证完整显示
    BANNER_HEIGHT = 160

    def __init__(self, presenter=None, auto_load=True, connect_scripts=True):
        super().__init__()
        self.presenter = presenter or ScriptPresenter()
        self.db = None
        self._all_scripts = []
        self._last_sig = None
        self._cards = {}   # id -> ScriptCard（复用实例，避免整表重建）
        self._order = []   # 上次渲染的卡片顺序

        self._searching = False
        self._results = []
        self._active_id = None
        self._ime_composing = False
        self._ime_guard_until = 0.0

        self.info_widget = None
        self._preload_queue = []
        self._preload_order = []
        self._preload_sig = None
        self._init_ui()
        self._init_signals()
        self._init_presenter_signals(connect_scripts)

        self.search_timer = QTimer()
        self.search_timer.setSingleShot(True)
        self.search_timer.timeout.connect(self._do_filter)

        self._reflow_timer = QTimer(self)
        self._reflow_timer.setSingleShot(True)
        self._reflow_timer.timeout.connect(self._reflow_cards)

        self._preload_timer = QTimer(self)
        self._preload_timer.setSingleShot(True)
        self._preload_timer.timeout.connect(self._preload_next_batch)

        self._render_queue = []
        self._render_scroll_pos = 0
        self._render_timer = QTimer(self)
        self._render_timer.setSingleShot(True)
        self._render_timer.timeout.connect(self._append_render_batch)

        if auto_load:
            QTimer.singleShot(0, self.presenter.lazy_loading)

    def _init_ui(self):
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(11, 11, 11, 11)
        self.main_layout.setSpacing(11)

        self.banner = XCarousel(interval=3000, min_height=self.BANNER_HEIGHT)
        self.banner.setFixedHeight(self.BANNER_HEIGHT)
        # 宽度交给布局自适应（不设最大宽度、不加 alignment，否则会被压成 120 宽）
        self.main_layout.addWidget(self.banner)

        self.scripts_search_layout = QHBoxLayout()
        self.scripts_search_layout.setContentsMargins(0, 0, 0, 0)
        self.scripts_search_layout.setSpacing(5)
        self.search_bar = XLineEdit(placeholder=tr('Search scripts...'), prefix_icon=IconName.SEARCH)

        self.scripts_search_layout.addWidget(self.search_bar)
        self.btn_install = XPushButton(tr('Script Market'),
                                       icon=IconName.APPLICATION)

        self.scripts_search_layout.addWidget(self.btn_install)
        self.main_layout.addLayout(self.scripts_search_layout, 0)

        self.search_hint = XLabel(
            tr('↑↓ Select · Enter Run · Esc Clear'),
            style=XLabel.Style.SECONDARY)
        self.search_hint.set_color(XColor.TERTIARY)
        self.search_hint.setVisible(False)
        self.main_layout.addWidget(self.search_hint)

        self.scroll_area = XScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.set_scrollbar_visible(True, False)
        self.scroll_content = QFrame()
        self.stack_layout = QStackedLayout(self.scroll_content)

        self.list_container = QWidget()
        self.flow_layout = CardFlowLayout(self.list_container)
        self.flow_layout.setContentsMargins(0, 0, 0, 0)
        self.flow_layout.setSpacing(11)
        self.list_container.installEventFilter(self)
        self.stack_layout.addWidget(self.list_container)

        self.empty_container = self._create_empty_widget()
        self.stack_layout.addWidget(self.empty_container)

        self.scroll_content.installEventFilter(self)
        self.scroll_area.setWidget(self.scroll_content)

        self.results_list = XListWidget(show_border=False)
        self.results_list.setUniformItemSizes(True)
        self.results_list.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.results_list.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.results_list.setContextMenuPolicy(Qt.CustomContextMenu)

        self.content_stack = QStackedWidget()
        self.content_stack.addWidget(self.scroll_area)
        self.content_stack.addWidget(self.results_list)
        self.content_stack.setCurrentWidget(self.scroll_area)
        self.main_layout.addWidget(self.content_stack, 1)

        self.search_bar.installEventFilter(self)

    def _init_signals(self):
        self.search_bar.textChanged.connect(self._on_search_text_changed)
        self.btn_install.clicked.connect(lambda :self.ScriptHub.emit())
        self.banner.image_clicked.connect(self.presenter.on_banner_clicked)
        self.results_list.itemClicked.connect(self._on_result_clicked)
        self.results_list.currentItemChanged.connect(
            self._on_result_current_changed)
        self.results_list.customContextMenuRequested.connect(
            self._on_result_context_menu)


    def _init_presenter_signals(self, connect_scripts=True):
        """逻辑层信号"""
        if connect_scripts:
            self.presenter.scripts_loaded.connect(self._on_scripts_loaded)
        self.presenter.banner_loaded.connect(self._on_banner_loaded)

    def showEvent(self, event):
        super().showEvent(event)
        self.finish_preload()
        self.schedule_card_reflow()
        if not self.search_bar.hasFocus():
            QTimer.singleShot(0, self.search_bar.setFocus)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if hasattr(self, 'flow_layout'):
            self.schedule_card_reflow()

    def schedule_card_reflow(self):
        self._reflow_timer.start()

    def _reflow_cards(self):
        if not self._cards:
            return
        self.flow_layout.invalidate()
        self.list_container.updateGeometry()
        self.scroll_content.updateGeometry()
        self.stack_layout.activate()
        self.flow_layout.activate()
        self.scroll_area.updateGeometry()

    def focus_search(self, select_all=False):
        self.search_bar.setFocus(Qt.OtherFocusReason)
        if select_all:
            self.search_bar.selectAll()
        if self.search_bar.text().strip():
            self._ensure_search_active()

    def load_banner(self):
        self.presenter.load_banner()

    def set_scripts(self, scripts):
        self.cancel_preload()
        self._on_scripts_loaded(scripts or [])

    def preload_scripts(self, scripts):
        if self.isVisible():
            self.set_scripts(scripts)
            return

        self._cancel_render_batch()
        scripts_data = list(scripts or [])
        self._all_scripts = scripts_data
        sig = tuple(
            (s.id, s.pin, s.badge, s.name, s.icon, s.version)
            for s in scripts_data)
        if sig == self._last_sig and self._preload_sig is None:
            return
        if sig == self._preload_sig and self._preload_queue:
            return

        self._preload_timer.stop()
        new_ids = [s.id for s in scripts_data]
        new_set = set(new_ids)
        for sid in [k for k in self._cards if k not in new_set]:
            stale = self._cards.pop(sid)
            stale.hide()
            stale.deleteLater()

        queue = []
        for script in scripts_data:
            card = self._cards.get(script.id)
            if card is None:
                queue.append(script)
            else:
                card.update_data(script)

        self._preload_order = new_ids
        self._preload_sig = sig
        self._preload_queue = queue
        if queue:
            self._preload_timer.start(0)
        else:
            self._finish_preload()

    def finish_preload(self):
        if self._preload_sig is None and not self._preload_queue:
            return
        self._preload_timer.stop()
        self._preload_next_batch()

    def cancel_preload(self):
        self._preload_timer.stop()
        self._preload_queue = []
        self._preload_order = []
        self._preload_sig = None
        self._cancel_render_batch()

    def _preload_next_batch(self):
        if not self._preload_queue:
            self._finish_preload()
            return
        for script in self._preload_queue[:_CARD_BATCH]:
            self._ensure_card(script)
        del self._preload_queue[:_CARD_BATCH]
        if self.isVisible() and self._preload_order:
            self._order = list(self._preload_order)
            self._reorder(self._order)
            self.stack_layout.setCurrentWidget(self.list_container)
            self.schedule_card_reflow()
        if self._preload_queue:
            self._preload_timer.start(0)
        else:
            self._finish_preload()

    def _cancel_render_batch(self):
        self._render_timer.stop()
        self._render_queue = []

    def _append_render_batch(self):
        if not self._render_queue:
            return
        for script in self._render_queue[:_CARD_BATCH]:
            self._ensure_card(script)
        del self._render_queue[:_CARD_BATCH]
        if self._order:
            self._reorder(self._order)
            self.stack_layout.setCurrentWidget(self.list_container)
            self.schedule_card_reflow()
        if self._render_queue:
            self._render_timer.start(0)
        else:
            scroll_bar = self.scroll_area.verticalScrollBar()
            QTimer.singleShot(
                0, lambda pos=self._render_scroll_pos: scroll_bar.setValue(pos))

    def _finish_preload(self):
        sig = self._preload_sig
        order = list(self._preload_order)
        self._preload_queue = []
        self._preload_order = []
        self._preload_sig = None
        if sig is not None:
            self._last_sig = sig
        if order:
            self._reorder(order)
            self._order = order
            self.stack_layout.setCurrentWidget(self.list_container)
        else:
            self.stack_layout.setCurrentWidget(self.empty_container)
        if self.isVisible():
            self.schedule_card_reflow()

    def _ensure_card(self, script):
        card = self._cards.get(script.id)
        if card is None:
            card = ScriptCard(script)
            card.updated.connect(self._on_card_updated)
            card.uninstalled.connect(self._on_card_uninstall)
            card.started.connect(self._on_card_started)
            card.clicked.connect(card._start_script)
            self._cards[script.id] = card
        else:
            card.update_data(script)
        return card

    def _ensure_search_active(self):
        if not self.search_bar.text().strip():
            return False
        if self.search_timer.isActive() or not self._searching:
            self.search_timer.stop()
            self._do_filter(reset_active=True)
            return True
        return False

    def eventFilter(self, obj, event):
        if event.type() == QEvent.Resize and obj in (
                getattr(self, 'list_container', None),
                getattr(self, 'scroll_content', None)):
            self.schedule_card_reflow()
        if obj is self.search_bar:
            event_type = event.type()
            if event_type == QEvent.InputMethod:
                self._ime_composing = bool(event.preeditString())
                if event.commitString():
                    self._ime_guard_until = time.monotonic() + 0.05
            elif event_type == QEvent.FocusOut:
                self._ime_composing = False
                self._ime_guard_until = 0.0
            elif event_type == QEvent.KeyRelease:
                self._ime_guard_until = 0.0
            elif event_type == QEvent.KeyPress:
                if self._ime_composing or time.monotonic() < self._ime_guard_until:
                    return super().eventFilter(obj, event)
                key = event.key()
                if key in (Qt.Key_Up, Qt.Key_Down):
                    if self.search_bar.text().strip():
                        refiltered = self._ensure_search_active()
                        if refiltered:
                            if self._results:
                                index = 0 if key == Qt.Key_Down else len(self._results) - 1
                                self._set_active(index)
                        else:
                            self._move_active(-1 if key == Qt.Key_Up else 1)
                        return True
                elif key in (Qt.Key_Return, Qt.Key_Enter):
                    if self.search_bar.text().strip():
                        self._launch_active()
                        return True
                elif key == Qt.Key_Escape:
                    if self.search_bar.text():
                        self.search_bar.clear()
                        return True
                    self.window().hide()
                    return True
        return super().eventFilter(obj, event)

    def clear_search(self):
        self.search_timer.stop()
        if self.search_bar.text():
            self.search_bar.blockSignals(True)
            self.search_bar.clear()
            self.search_bar.blockSignals(False)
        self._searching = False
        self._results = []
        self._active_id = None
        self.search_hint.setVisible(False)
        self.content_stack.setCurrentWidget(self.scroll_area)
        self._clear_results()

    def _on_search_text_changed(self):
        text = self.search_bar.text().strip()
        if text:
            self.search_timer.stop()
            self.global_search_requested.emit(text)
            return
        self.search_timer.stop()
        self._do_filter()

    def _do_filter(self, reset_active=True):
        filter_text = self.search_bar.text().strip()
        filtered = self.presenter.filter_scripts(filter_text, self._all_scripts)
        if filter_text:
            self._searching = True
            self.search_hint.setVisible(True)
            self.content_stack.setCurrentWidget(self.results_list)
            self._render_results(filtered, reset_active)
            return

        self._searching = False
        self.search_hint.setVisible(False)
        self.empty_label.setText(tr('The script is empty.'))
        self.content_stack.setCurrentWidget(self.scroll_area)
        self._clear_results()
        self._active_id = None
        self._render_scripts(filtered)

    def _create_empty_widget(self):
        empty_widget = QWidget()
        layout = QVBoxLayout(empty_widget)
        layout.setSpacing(20)
        layout.setAlignment(Qt.AlignCenter)
        self._empty_image = XImage(
            source=XIcon.get(name=IconName.EMOTION_UNHAPPY,
                             color=XColor.TEXT_TERTIARY, size=32).pixmap(),
            min_size=32)
        layout.addWidget(self._empty_image)
        self.empty_label = XLabel(tr("The script is empty."))
        self.empty_label.set_color(XColor.TEXT_TERTIARY)
        layout.addWidget(self.empty_label, alignment=Qt.AlignCenter)
        theme_manager.theme_changed.connect(self._refresh_empty_icon)
        return empty_widget

    def _refresh_empty_icon(self, *args):
        if getattr(self, "_empty_image", None) is not None:
            self._empty_image.set_source(
                XIcon.get(name=IconName.EMOTION_UNHAPPY,
                          color=XColor.TEXT_TERTIARY, size=32).pixmap())
        if getattr(self, "empty_label", None) is not None:
            self.empty_label.set_color(XColor.TEXT_TERTIARY)


    def _on_scripts_loaded(self, scripts_data):
        self._all_scripts = scripts_data
        # 刷新后重新套用当前搜索词，并尽量保留当前选中项
        self._do_filter(reset_active=False)

    def _on_banner_loaded(self, banner_list):
        self.banner.clear()
        for banner in banner_list:
            # contain：窗口拉宽后图片仍完整显示，不裁切
            self.banner.add_image_page(banner, scale_mode="cover")

    def _render_scripts(self, scripts_data):
        sig = tuple((s.id, s.pin, s.badge, s.name, s.icon, s.version) for s in scripts_data)
        if sig == self._last_sig:
            if not scripts_data:
                self.stack_layout.setCurrentWidget(self.empty_container)
            else:
                self.stack_layout.setCurrentWidget(self.list_container)
                if self.isVisible():
                    self.schedule_card_reflow()
            return
        self._cancel_render_batch()
        self._last_sig = sig

        new_ids = [s.id for s in scripts_data]
        new_set = set(new_ids)
        for sid in [k for k in self._cards if k not in new_set]:
            stale = self._cards.pop(sid)
            stale.hide()
            stale.deleteLater()

        missing = []
        for script in scripts_data:
            card = self._cards.get(script.id)
            if card is None:
                missing.append(script)
            else:
                card.update_data(script)

        if not scripts_data:
            self._order = []
            self.stack_layout.setCurrentWidget(self.empty_container)
            return

        self._render_scroll_pos = self.scroll_area.verticalScrollBar().value()
        self._order = list(new_ids)
        self._render_queue = missing
        self._reorder(self._order)
        self.stack_layout.setCurrentWidget(self.list_container)
        self.list_container.updateGeometry()
        self.schedule_card_reflow()
        if self._render_queue:
            self._append_render_batch()
        else:
            QTimer.singleShot(
                0, lambda pos=self._render_scroll_pos:
                self.scroll_area.verticalScrollBar().setValue(pos))

    def _reorder(self, ordered_ids):
        """按 ordered_ids 重排卡片，复用同一批控件实例（不删除、不重建、不重载图）"""
        while self.flow_layout.count():
            self.flow_layout.takeAt(0)
        for sid in ordered_ids:
            card = self._cards.get(sid)
            if card is not None:
                self.flow_layout.addWidget(card)




    def _render_results(self, scripts, reset_active):
        previous_id = None if reset_active else self._active_id
        previous_row = 0 if reset_active else max(0, self.results_list.currentRow())
        self._clear_results()
        self._results = list(scripts)

        if not scripts:
            placeholder = QListWidgetItem(tr('No matching scripts.'))
            placeholder.setFlags(Qt.NoItemFlags)
            placeholder.setSizeHint(QSize(0, 48))
            self.results_list.addItem(placeholder)
            self.results_list.setCurrentRow(-1)
            self._active_id = None
            return

        for script in scripts:
            item = QListWidgetItem()
            item.setData(Qt.UserRole, script.id)
            item.setSizeHint(QSize(0, 48))
            item.setToolTip(script.name)
            self.results_list.addItem(item)
            self.results_list.setItemWidget(item, ScriptListItemWidget(script))

        ids = [script.id for script in scripts]
        if previous_id in ids:
            index = ids.index(previous_id)
        else:
            index = min(previous_row, len(ids) - 1)
        self._set_active(index)

    def _clear_results(self):
        self.results_list.clear()
        self._results = []
        self._active_id = None

    def _set_active(self, index, scroll=True):
        if index < 0 or index >= self.results_list.count():
            self.results_list.setCurrentRow(-1)
            self._active_id = None
            return

        self.results_list.setCurrentRow(index)
        item = self.results_list.item(index)
        if item is not None and not item.isSelected():
            item.setSelected(True)
        if 0 <= index < len(self._results):
            self._active_id = self._results[index].id
        if scroll and item is not None:
            self.results_list.scrollToItem(item, QAbstractItemView.EnsureVisible)

    def _move_active(self, delta):
        if not self._results:
            return
        current = self.results_list.currentRow()
        if current < 0:
            index = 0 if delta > 0 else len(self._results) - 1
        else:
            index = current + delta
            index = max(0, min(len(self._results) - 1, index))
        self._set_active(index)

    def _launch_active(self):
        self._ensure_search_active()
        if not self.search_bar.text().strip() or not self._results:
            return
        row = self.results_list.currentRow()
        if row < 0:
            self._set_active(0)
            row = 0
        item = self.results_list.item(row)
        script_id = item.data(Qt.UserRole) if item is not None else None
        if script_id:
            self._launch_script(script_id)

    def _find_script(self, script_id):
        for script in self._results:
            if script.id == script_id:
                return script
        return None

    def _on_result_current_changed(self, current, previous):
        if current is None:
            self._active_id = None
            return
        script_id = current.data(Qt.UserRole)
        self._active_id = script_id or None

    def _on_result_clicked(self, item):
        if item is None:
            return
        script_id = item.data(Qt.UserRole)
        if script_id:
            self._launch_script(script_id)

    def _on_result_context_menu(self, pos):
        try:
            item = self.results_list.itemAt(pos)
            if item is None:
                return
            script_id = item.data(Qt.UserRole)
            script = self._find_script(script_id) if script_id else None
            if not script:
                return
            popup_script_menu(
                self,
                script,
                self.results_list.viewport().mapToGlobal(pos),
                on_run=lambda: self._launch_script(script_id),
                on_uninstall=lambda: self.presenter.uninstall_script(script_id),
                on_changed=self.presenter.refresh_scripts,
            )
        except Exception as exc:
            BM_LOG.error("脚本搜索右键菜单失败: %s" % exc)

    def _launch_script(self, script_id):
        # 运行时立即隐藏主窗口（参数表单弹出期间也保持隐藏）
        self.window().hide()
        self.presenter.execute_script(script_id)

    def _on_card_started(self, script_id: str):
        self._launch_script(script_id)

    def _on_card_uninstall(self, script_id:str):
        self.presenter.uninstall_script(script_id)

    def _on_card_updated(self, msg: dict):
        self.presenter.refresh_scripts()


