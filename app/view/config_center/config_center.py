"""
Copyright (c) 2026 綦恒智
Email: bmscriptsbox@163.com
SPDX-License-Identifier: MIT
SPDX-License-Identifier: LicenseRef-Commons-Clause

配置中心：XNavTree 导航 + 懒加载页面栈。
"""
import json

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (QFrame, QHBoxLayout, QLabel, QStackedWidget,
                               QVBoxLayout, QWidget)

from xsideui import XI18N, XDivider, XNavTree

from app.utils import BM_LOG, BmTools

from .nav_spec import (ACTION_NAV_IDS, DEFAULT_NAV_ID, NavId, build_tree)


class ConfigCenter(QWidget):
    navigate_requested = Signal(str)
    launcher_requested = Signal()
    language_changed = Signal()

    TREE_WIDTH = 200

    def __init__(self, page_factories=None, action_handler=None, parent=None):
        super().__init__(parent)
        self._factories = dict(page_factories or {})
        self._action_handler = action_handler
        self._pages = {}
        self._visible_ids = None
        self._current_nav = None
        self._last_nav = self._load_last_nav()
        self._account_status = None
        self._script_updates = False
        self._badges = {}
        self._suppress_changed = False
        self._build_ui()
        self._build_tree()

    # ---------- UI ----------

    def _build_ui(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        nav_frame = QFrame()
        nav_frame.setObjectName("configNavFrame")
        nav_frame.setFixedWidth(self.TREE_WIDTH)
        nav_layout = QVBoxLayout(nav_frame)
        nav_layout.setContentsMargins(0,0,0,0)
        nav_layout.setSpacing(0)

        self.tree = XNavTree(indent=14, icon_size=18, text_size=13,
                             item_height=40)
        self.tree.changed.connect(self._on_tree_changed)
        nav_layout.addWidget(self.tree, 1)

        self.stack = QStackedWidget()
        self.stack.setObjectName("configPageStack")

        layout.addWidget(nav_frame, 0)
        layout.addWidget(self.stack, 1)

    def _build_tree(self):
        self._visible_ids = self._available_ids()
        nodes = build_tree(self._visible_ids)
        state = self.tree.save_state()
        self._suppress_changed = True
        try:
            self.tree.add_item_batch(nodes, preserve_state=True)
            if state.get("current"):
                self.tree.set_current_id(state["current"])
            if self._account_status:
                self.tree.set_status(NavId.SYS_ACCOUNT, self._account_status)
            if self._script_updates:
                self.tree.set_status(NavId.SCRIPTS_UPDATE, 'warning')
            for nav_id, badge in self._badges.items():
                self.tree.set_badge(nav_id, badge)
        finally:
            self._suppress_changed = False

    def _available_ids(self):
        ids = set()
        for nav_id in self._factories:
            ids.add(nav_id)
        if self._action_handler is not None:
            ids.update(ACTION_NAV_IDS)
        else:
            ids.difference_update(ACTION_NAV_IDS)
        return ids

    # ---------- navigation ----------

    def show_page(self, nav_id=None):
        self._last_nav = self._last_nav or DEFAULT_NAV_ID
        target = nav_id or self._last_nav
        if target == NavId.CONFIG:
            target = self._last_nav
        if target in ACTION_NAV_IDS:
            self._run_action(target)
            return
        if target not in self._factories:
            target = DEFAULT_NAV_ID if DEFAULT_NAV_ID in self._factories else next(
                iter(self._factories), None)
        if target is None:
            return
        page = self._ensure_page(target)
        if page is None:
            return
        self.stack.setCurrentWidget(page)
        self._current_nav = target
        self._last_nav = target
        self._suppress_changed = True
        try:
            self.tree.set_current_id(target)
        finally:
            self._suppress_changed = False
        self._save_last_nav(target)

    def _on_tree_changed(self, nav_id):
        if self._suppress_changed:
            return
        if nav_id in ACTION_NAV_IDS:
            self._run_action(nav_id)
            self._restore_tree_selection()
            return
        self.show_page(nav_id)

    def _run_action(self, nav_id):
        if self._action_handler is None:
            return
        try:
            self._action_handler(nav_id)
        except Exception as exc:
            BM_LOG.error("配置中心动作执行失败 %s: %s" % (nav_id, exc))

    def _restore_tree_selection(self):
        if self._current_nav is None:
            self.show_page(self._last_nav or DEFAULT_NAV_ID)
            return
        self._suppress_changed = True
        try:
            self.tree.set_current_id(self._current_nav)
        finally:
            self._suppress_changed = False

    def _ensure_page(self, nav_id):
        page = self._pages.get(nav_id)
        if page is not None:
            return page
        factory = self._factories.get(nav_id)
        if factory is None:
            return None
        try:
            page = factory()
        except Exception as exc:
            BM_LOG.error("配置页面创建失败 %s: %s" % (nav_id, exc))
            page = self._error_page(str(exc))
        if page is None:
            page = self._error_page(
                XI18N.x_tr("Page unavailable", context='BmscriptsBox'))
        self._pages[nav_id] = page
        self.stack.addWidget(page)
        return page

    @staticmethod
    def _error_page(message):
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(24, 24, 24, 24)
        label = QLabel(
            XI18N.x_tr("Page load failed", context='BmscriptsBox')
            + "\n\n" + message)
        label.setWordWrap(True)
        label.setAlignment(Qt.AlignCenter)
        layout.addWidget(label)
        return widget

    # ---------- public API ----------

    def current_nav_id(self):
        return self._current_nav

    def last_nav_id(self):
        return self._last_nav or DEFAULT_NAV_ID

    def page_for(self, nav_id):
        return self._ensure_page(nav_id)

    def set_account_status(self, status):
        self._account_status = status
        self.tree.set_status(NavId.SYS_ACCOUNT, status)

    def set_script_updates(self, has_updates):
        """脚本存在可用更新时，在「脚本更新」项显示圆点。"""
        self._script_updates = bool(has_updates)
        self.tree.set_status(NavId.SCRIPTS_UPDATE,
                             'warning' if has_updates else None)

    def set_badge(self, nav_id, badge):
        if badge is None:
            self._badges.pop(nav_id, None)
        else:
            self._badges[nav_id] = badge
        self.tree.set_badge(nav_id, badge)

    def refresh_scripts(self):
        page = self._pages.get(NavId.SCRIPTS_INSTALLED)
        if page is not None and hasattr(page, "refresh"):
            page.refresh()

    def retranslate(self):
        state = self.tree.save_state()
        self.tree.add_item_batch(build_tree(self._visible_ids),
                                 preserve_state=True)
        if state.get("current"):
            self.tree.set_current_id(state["current"])
        if self._account_status:
            self.tree.set_status(NavId.SYS_ACCOUNT, self._account_status)
        if self._script_updates:
            self.tree.set_status(NavId.SCRIPTS_UPDATE, 'warning')
        for nav_id, badge in self._badges.items():
            self.tree.set_badge(nav_id, badge)
        self.language_changed.emit()

    def save_state(self):
        return {
            "current": self._current_nav or self._last_nav,
            "tree": self.tree.save_state(),
        }

    def restore_state(self, state):
        if not isinstance(state, dict):
            return
        tree_state = state.get("tree")
        if isinstance(tree_state, dict):
            self.tree.restore_state(tree_state)
        target = state.get("current")
        if target:
            self.show_page(target)

    def shutdown(self):
        for page in list(self._pages.values()):
            shutdown = getattr(page, "shutdown", None)
            if callable(shutdown):
                try:
                    shutdown()
                except Exception as exc:
                    BM_LOG.error("配置页面关闭失败: %s" % exc)
        self._pages.clear()

    # ---------- state ----------

    @staticmethod
    def _state_path():
        return BmTools.get_root_path() / "BmCache" / "ui_state.json"

    def _load_last_nav(self):
        try:
            path = self._state_path()
            if not path.exists():
                return None
            data = json.loads(path.read_text(encoding="utf-8"))
            value = data.get("config_nav")
            return value if isinstance(value, str) and value else None
        except Exception:
            return None

    def _save_last_nav(self, nav_id):
        if not nav_id:
            return
        path = self._state_path()
        data = {}
        try:
            if path.exists():
                data = json.loads(path.read_text(encoding="utf-8"))
                if not isinstance(data, dict):
                    data = {}
            data["config_nav"] = nav_id
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(data, ensure_ascii=False, indent=2),
                            encoding="utf-8")
        except Exception as exc:
            BM_LOG.warning("保存配置中心状态失败: %s" % exc)
