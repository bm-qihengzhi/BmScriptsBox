"""
Copyright (c) 2026 綦恒智
Email: bmscriptsbox@163.com
SPDX-License-Identifier: MIT
SPDX-License-Identifier: LicenseRef-Commons-Clause

嵌入首页的统一搜索面板。
"""
import time

from PySide6.QtCore import (QEvent, QModelIndex, QPropertyAnimation, Qt,
                            QTimer, Signal)
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (QAbstractItemView, QFrame, QGraphicsOpacityEffect,
                               QHBoxLayout, QVBoxLayout, QWidget)

from xsideui import (IconName, XButtonVariant, XColor, XDivider, XImage,
                     XLabel, XLineEdit, XListView, XPushButton, XSize, tr,
                     theme_manager, XI18N)

from app.servers.launcher.calculator import find as find_calculator
from app.servers.launcher.models import SearchItem
from app.utils import BM_LOG
from app.utils.tools import BmTools
from app.view.config_center.nav_spec import NavId
from app.view.launcher import commands as nav_commands

from .market_controller import MarketController, should_recommend
from .market_install_controller import MarketInstallController
from .icon_cache import IconCache
from .script_search_controller import ScriptSearchController
from .search_result_model import SearchResultModel


_SUGGESTION_BATCH = 40


class DragHandle(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(12)
        self.setCursor(Qt.SizeAllCursor)
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self._dragging = False
        self._drag_offset = None

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._dragging = True
            self._drag_offset = event.globalPosition().toPoint() - self.window().pos()
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self._dragging and event.buttons() & Qt.LeftButton:
            self.window().move(event.globalPosition().toPoint() - self._drag_offset)
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._dragging = False
            self._drag_offset = None
            event.accept()
            return
        super().mouseReleaseEvent(event)


class SearchPanel(QWidget):
    item_activated = Signal(object)
    cards_requested = Signal()
    navigate_requested = Signal(str)
    script_uninstall_requested = Signal(str)
    scripts_changed = Signal()
    market_install_requested = Signal(object)

    def __init__(self, service, market_catalog=None, parent=None):
        super().__init__(parent)
        self._ime_composing = False
        self._ime_guard_until = 0.0
        self._icon_cache = IconCache(self)
        self._icon_cache.icon_ready.connect(self._on_icon_ready)
        self._scripts = ScriptSearchController(service, self)
        self._market = MarketController(market_catalog, self)
        self._last_local_items = []
        self._market_items = []
        if market_catalog is not None:
            market_catalog.updated.connect(self._on_market_updated)
        self._market_install = MarketInstallController(self)
        self._market_install.state_changed.connect(
            self._on_market_install_state)
        self._market_install.scripts_changed.connect(
            self.scripts_changed.emit)
        self.market_install_requested.connect(self._install_market_item)
        self._suggestion_queue = []
        self._suggestion_timer = QTimer(self)
        self._suggestion_timer.setSingleShot(True)
        self._suggestion_timer.timeout.connect(self._append_suggestion_batch)
        self._tip_index = 0
        self._tip_timer = QTimer(self)
        self._tip_timer.setInterval(4000)
        self._tip_timer.timeout.connect(self._rotate_tip)

        self._build_ui()
        self._search_timer = QTimer(self)
        self._search_timer.setSingleShot(True)
        self._search_timer.timeout.connect(self._do_search)
        self._scripts.index_updated.connect(self._on_index_updated)
        self._scripts.search_keys_updated.connect(self._on_search_keys_updated)

    def _build_ui(self):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        self.drag_handle = DragHandle(self)
        outer.addWidget(self.drag_handle)

        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setContentsMargins(0,0,0,0 )
        layout.setSpacing(10)

        self.search_bar = XLineEdit(
            placeholder=tr('BmScriptsBox · Superpowers for your PC'),
            border_visible=False,

        ).set_size("large")
        self.search_bar.installEventFilter(self)
        self.search_bar.textChanged.connect(self._on_search_text_changed)

        top_layout = QHBoxLayout()
        top_layout.setContentsMargins(11, 0, 11, 0)
        top_layout.setSpacing(10)
        top_layout.addWidget(XImage(source=BmTools.get_logo_path(), min_size=40))
        top_layout.addWidget(self.search_bar)
        layout.addLayout(top_layout)
        layout.addWidget(XDivider())

        self.results = XListView(show_border=False,
                                 separator_visible=True)
        self.results.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.results_model = SearchResultModel(
            self._icon_cache, self.results)
        self.results.setModel(self.results_model)
        self.results.setUniformItemSizes(False)
        self.results.set_icon_size(22, 22)
        self.results.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.results.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.results.setContextMenuPolicy(Qt.CustomContextMenu)
        self.results.clicked.connect(self._on_item_clicked)
        self.results.customContextMenuRequested.connect(
            self._on_result_context_menu)
        self.results.installEventFilter(self)
        layout.addWidget(self.results, 1)

        self.bottom_frame = QFrame()
        self.bottom_frame.setObjectName("searchBottomFrame")
        self.bottom_frame.setAttribute(Qt.WA_StyledBackground, True)
        bottom_layout = QHBoxLayout(self.bottom_frame)
        bottom_layout.setContentsMargins(11, 8, 11, 8)
        bottom_layout.setSpacing(10)
        layout.addWidget(self.bottom_frame)
        self._apply_bottom_frame_style()
        theme_manager.theme_changed.connect(self._apply_bottom_frame_style)

        self.tip_label = XLabel(
            text="", color=XColor.SECONDARY, elide_mode=True, size=12,
            alignment=Qt.AlignRight | Qt.AlignVCenter, selectable=False,
        )
        self.tip_label.setFixedWidth(300)
        self._tips = [
            tr('Middle-click or Ctrl×2 to open'),
            tr('Esc to hide the panel'),
            tr('↑↓ Select · Enter Run'),
            tr('Tab: switch Search / Config'),
        ]
        self.tip_label.setText(self._tips[0])
        self._tip_effect = QGraphicsOpacityEffect(self.tip_label)
        self._tip_effect.setOpacity(1.0)
        self.tip_label.setGraphicsEffect(self._tip_effect)
        self._tip_fade_out = QPropertyAnimation(self._tip_effect, b"opacity", self)
        self._tip_fade_out.setDuration(220)
        self._tip_fade_out.setStartValue(1.0)
        self._tip_fade_out.setEndValue(0.0)
        self._tip_fade_out.finished.connect(self._show_next_tip)
        self._tip_fade_in = QPropertyAnimation(self._tip_effect, b"opacity", self)
        self._tip_fade_in.setDuration(220)
        self._tip_fade_in.setStartValue(0.0)
        self._tip_fade_in.setEndValue(1.0)

        self.cards_button = XPushButton(
            tr('Config Center'),
            icon=IconName.LIST,
            variant=XButtonVariant.TEXT,
            color=XColor.SECONDARY,
            size=XSize.SMALL,
        )
        self.cards_button.clicked.connect(self._request_config)
        bottom_layout.addWidget(self.cards_button)
        bottom_layout.addStretch()
        bottom_layout.addWidget(self.tip_label)

        outer.addWidget(content, 1)
        self._show_placeholder()

    def showEvent(self, event):
        super().showEvent(event)
        self._tip_timer.start()
        QTimer.singleShot(0, self._focus_search_end)

    def hideEvent(self, event):
        self._tip_timer.stop()
        super().hideEvent(event)

    def _request_config(self):
        self.navigate_requested.emit(NavId.CONFIG)

    def _request_cards(self):
        self._request_config()

    def activate(self, query="", focus=True):
        self._market.refresh()
        self.search_bar.blockSignals(True)
        self.search_bar.setText(query or "")
        self.search_bar.blockSignals(False)
        if query and query.strip():
            self._do_search()
        else:
            self._show_placeholder()
        if focus:
            QTimer.singleShot(0, self._focus_search_end)

    def focus_search(self, select_all=False):
        self.search_bar.setFocus(Qt.OtherFocusReason)
        if select_all:
            self.search_bar.selectAll()
        else:
            self.search_bar.setCursorPosition(len(self.search_bar.text()))
        if self.search_bar.text().strip():
            self._search_timer.stop()
            self._do_search(preserve_selection=True)

    def _focus_search_end(self):
        self.focus_search(select_all=False)

    def set_scripts(self, scripts):
        self._scripts.set_scripts(scripts)
        query = self.search_bar.text()
        if not self.isVisible():
            return
        if query.strip():
            self._do_search(preserve_selection=True)
        else:
            self._show_placeholder()

    def _apply_bottom_frame_style(self, *_):
        fill = QColor(theme_manager.semantic_color("bg.surface"))
        fill.setAlphaF(0.20 if theme_manager.is_dark else 0.12)
        border = theme_manager.semantic_color("border.default")

        self.bottom_frame.setStyleSheet(
            "QFrame#searchBottomFrame {"
            f" background-color: rgba({fill.red()}, {fill.green()}, "
            f"{fill.blue()}, {fill.alpha()});"
            f" border-top: 1px solid {border};"
            " }"
        )

    def _rotate_tip(self):
        if not self._tips:
            return
        if self._tip_fade_out.state() == QPropertyAnimation.Running:
            return
        self._tip_fade_out.start()

    def _show_next_tip(self):
        if not self._tips:
            return
        self._tip_index = (self._tip_index + 1) % len(self._tips)
        self.tip_label.setText(self._tips[self._tip_index])
        self._tip_fade_in.start()

    def warm_icons(self, items):
        self._icon_cache.warm_items(items)

    def shutdown(self):
        try:
            theme_manager.theme_changed.disconnect(
                self._apply_bottom_frame_style)
        except (RuntimeError, TypeError):
            pass
        self._cancel_suggestion_batch()
        self._tip_timer.stop()
        self._tip_fade_out.stop()
        self._tip_fade_in.stop()
        self._icon_cache.shutdown()
        self._market_install.shutdown()

    # ---------- 搜索 ----------

    def _on_search_text_changed(self):
        if self.search_bar.text().strip():
            self._cancel_suggestion_batch()
            self._search_timer.start(120)
        else:
            self._search_timer.stop()
            self._do_search()

    def _do_search(self, preserve_selection=False):
        preserve_id = None
        if preserve_selection:
            current = self._current_item()
            if current is not None:
                preserve_id = current.id
        query = self.search_bar.text().strip()
        if not query:
            self._show_placeholder()
            return
        items = self._scripts.search(query)
        calc_item = find_calculator(query)
        market_items = []
        if calc_item is not None:
            items.insert(0, calc_item)
        else:
            input_items = self._scripts.input_suggestions(
                query, include_low=not items)
            if input_items:
                items = list(items) + list(input_items)
            if should_recommend(query, items):
                market_items = self._market.recommend(
                    query, self._scripts.installed_ids())
        self._last_local_items = list(items)
        self._market_items = market_items
        self._render_items(items, preserve_id, market_items)

    def _append_item(self, item):
        return self.results_model.append_item(item)

    def _append_placeholder(self, text):
        return self.results_model.append_placeholder(text)

    def _set_current_row(self, row):
        index = self.results_model.index_for_row(row)
        if index.isValid():
            self.results.setCurrentIndex(index)
            self.results.scrollTo(index, QAbstractItemView.EnsureVisible)
        else:
            self.results.setCurrentIndex(QModelIndex())
            self.results.clearSelection()

    def _add_nav_commands(self, query):
        items = (nav_commands.matching_commands(query)
                 if (query or "").strip()
                 else nav_commands.default_commands())
        first_row = None
        for item in items:
            row = self._append_item(item)
            if first_row is None:
                first_row = row
        return first_row

    def _add_script_suggestions(self):
        scripts = self._scripts.suggestions()
        if not scripts:
            return
        self._suggestion_queue = list(scripts)
        self._append_suggestion_batch()

    def _append_suggestion_batch(self):
        if not self._suggestion_queue:
            return
        batch = self._suggestion_queue[:_SUGGESTION_BATCH]
        del self._suggestion_queue[:_SUGGESTION_BATCH]
        self.results_model.append_items(batch)
        self._icon_cache.warm_items(batch)
        if self._suggestion_queue:
            self._suggestion_timer.start(0)

    def _cancel_suggestion_batch(self):
        self._suggestion_timer.stop()
        self._suggestion_queue = []

    def _show_placeholder(self, text=None):
        self._cancel_suggestion_batch()
        self.results_model.clear()
        raw = self.search_bar.text()
        nav_row = self._add_nav_commands(raw)
        if not raw.strip():
            self._add_script_suggestions()
        self._sync_empty_hint()
        self._set_current_row(nav_row if nav_row is not None else 0)

    def _sync_empty_hint(self):
        if self._scripts.loaded and not self._scripts.installed_ids():
            self.results.set_empty_texts(
                tr('Search scripts, local software, and system settings.'),
                tr('Enter a request to auto-match scripts. Install and use—try one now.'))
        else:
            self.results.set_empty_texts('', '')

    def _render_items(self, items, preserve_id=None, market_items=None):
        self._cancel_suggestion_batch()
        self.results_model.clear()
        raw = self.search_bar.text()
        market_items = list(market_items or [])

        if not items and not market_items:
            self._append_placeholder(tr('No matching results'))
            nav_row = self._add_nav_commands(raw)
            self._set_current_row(nav_row if nav_row is not None else 0)
            return

        if items:
            self.results_model.append_items(items)
            self._icon_cache.warm_items(items)

        if market_items:
            self._append_placeholder(tr('From the Market'))
            self.results_model.append_items(market_items)
            self._icon_cache.warm_items(market_items)

        preserve_row = self.results_model.row_for_id(preserve_id)
        if preserve_row is None:
            if items:
                preserve_row = 0
            elif market_items:
                preserve_row = self.results_model.row_for_id(
                    market_items[0].id)
        self._set_current_row(preserve_row)

    def _on_index_updated(self):
        self._icon_cache.warm_items(self._scripts.warmable_items())
        query = self.search_bar.text()
        if self.isVisible() and query.strip():
            self._do_search(preserve_selection=True)

    def _on_search_keys_updated(self):
        query = self.search_bar.text()
        if self.isVisible() and query.strip():
            self._do_search(preserve_selection=True)

    def _on_market_updated(self, _count=0):
        if not self.isVisible():
            return
        query = self.search_bar.text()
        if query.strip():
            self._do_search(preserve_selection=True)

    def _install_market_item(self, item):
        self._market_install.install(item, parent=self.window())

    def _on_market_install_state(self, item_id, state, detail=""):
        row = self.results_model.row_for_id(item_id)
        if row is None:
            return
        item = self.results_model.item_at(row)
        if item is None:
            return
        item.state = state
        # badge 由 SearchResultModel 统一 x_tr；这里的副标题是 delegate 直接绘制的文本，
        # 必须显式查表，否则中文界面会显示英文状态
        text = ""
        if state == "installed":
            item.badge = tr("Installed")
            text = XI18N.x_tr("Installed")
        elif state == "failed":
            item.badge = tr("Retry")
            text = (XI18N.x_tr("Install failed: %1").replace("%1", detail)
                    if detail else XI18N.x_tr("Install failed"))
        elif state == "installing":
            item.badge = tr("Installing")
            text = (XI18N.x_tr("Installing: %1").replace("%1", detail)
                    if detail else XI18N.x_tr("Installing…"))
        elif state == "invalid":
            item.badge = tr("Installable")
            text = XI18N.x_tr("Incomplete install info")
        elif state == "waiting":
            text = XI18N.x_tr("Waiting for the current install")
        else:
            item.badge = tr("Installable")
        self.results_model.set_item_status(item_id, text)

    def _on_icon_ready(self, _key):
        if self.results.viewport() is not None:
            self.results.viewport().update()

    # ---------- 键盘/鼠标 ----------

    def eventFilter(self, obj, event):
        search_bar = getattr(self, "search_bar", None)
        if search_bar is not None and obj is search_bar:
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
                    self._move_current(-1 if key == Qt.Key_Up else 1)
                    return True
                if key in (Qt.Key_Return, Qt.Key_Enter):
                    self._activate_current()
                    return True
                if key == Qt.Key_Escape:
                    return self._handle_escape()
        results = getattr(self, "results", None)
        if (results is not None and obj is results
                and event.type() == QEvent.KeyPress
                and event.key() == Qt.Key_Escape):
            return self._handle_escape()
        return super().eventFilter(obj, event)

    def _handle_escape(self):
        self._search_timer.stop()
        if self.search_bar.text():
            self.search_bar.clear()
            self.search_bar.setFocus(Qt.OtherFocusReason)
            return True
        self.window().hide()
        return True

    def _action_rows(self):
        rows = []
        for row in range(self.results_model.row_count()):
            index = self.results_model.index(row, 0)
            if (isinstance(index.data(Qt.UserRole), SearchItem)
                    and index.flags() & Qt.ItemIsSelectable):
                rows.append(row)
        return rows

    def _move_current(self, delta):
        pending = self._search_timer.isActive()
        if pending:
            self._search_timer.stop()
            self._do_search()
        rows = self._action_rows()
        if not rows:
            return
        current = self.results.currentIndex().row()
        if pending:
            row = rows[0] if delta > 0 else rows[-1]
        elif current in rows:
            position = rows.index(current)
            position = max(0, min(len(rows) - 1, position + delta))
            row = rows[position]
        else:
            row = rows[0] if delta > 0 else rows[-1]
        self._set_current_row(row)

    def _current_item(self):
        index = self.results.currentIndex()
        if not index.isValid():
            return None
        value = index.data(Qt.UserRole)
        return value if isinstance(value, SearchItem) else None

    def _activate_current(self):
        if self._search_timer.isActive():
            self._search_timer.stop()
            self._do_search()
        item = self._current_item()
        if item is not None:
            self._activate(item)

    def _on_item_clicked(self, index):
        if not index.isValid() or not (index.flags() & Qt.ItemIsEnabled):
            return
        item = index.data(Qt.UserRole)
        if isinstance(item, SearchItem):
            self._activate(item)

    def _on_result_context_menu(self, pos):
        try:
            index = self.results.indexAt(pos)
            if not index.isValid():
                return
            item = index.data(Qt.UserRole)
            if not isinstance(item, SearchItem):
                return
            self.results.setCurrentIndex(index)
            position = self.results.viewport().mapToGlobal(pos)
            if item.kind in ("script", "script_input"):
                self._scripts.popup_menu(
                    self,
                    item,
                    position,
                    on_run=lambda: self._activate(item),
                    on_uninstall=self.script_uninstall_requested.emit,
                    on_changed=self.scripts_changed.emit,
                )
        except Exception as exc:
            BM_LOG.error("搜索面板右键菜单失败: %s" % exc)

    def _activate(self, item):
        target = nav_commands.target_of(item)
        if target is not None:
            self.navigate_requested.emit(target)
            return
        if item.kind == "command":
            return
        if item.kind == "market_script":
            self.market_install_requested.emit(item)
            return
        self.item_activated.emit(item)
