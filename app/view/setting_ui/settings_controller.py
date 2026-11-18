"""
Copyright (c) 2026 綦恒智
Email: bmscriptsbox@163.com
SPDX-License-Identifier: MIT
SPDX-License-Identifier: LicenseRef-Commons-Clause

设置控制器：装配独立设置页，替代原来的 Tab 容器。
"""
from PySide6.QtCore import QObject, Signal

from app.utils import BM_LOG
from app.view.config_center.nav_spec import NavId

from .basic_settings_page import BasicSettingsPage
from .setting_pr import SettingPresenter

try:
    from .push_win_set import PushWidget
    HAS_WECHAT_PUSH = True
except Exception:
    HAS_WECHAT_PUSH = False
    PushWidget = None

try:
    from app.cloud.view.update_win import ScriptsUpdateWidget
    HAS_SCRIPT_UPDATE = True
except ImportError:
    HAS_SCRIPT_UPDATE = False
    ScriptsUpdateWidget = None

try:
    from app.cloud.view.user_win import UserWidget
    HAS_USER = True
except ImportError:
    HAS_USER = False
    UserWidget = None

try:
    from app.cloud.view.publish_win import PublishWidget
    HAS_PUBLISH = True
except ImportError:
    HAS_PUBLISH = False
    PublishWidget = None


class SettingsController(QObject):
    login_badge = Signal(bool)
    script_updates_changed = Signal(int)
    install_finished = Signal(dict)
    language_changed = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._pages = {}
        self._presenter = SettingPresenter(self)
        self.basic_page = BasicSettingsPage(self._presenter)
        self.basic_page.language_changed.connect(self.language_changed.emit)
        self._pages[NavId.SYS_BASIC] = self.basic_page

        if HAS_USER:
            self.page(NavId.SYS_ACCOUNT)

    @property
    def hotkey_combo(self):
        return self.basic_page.hotkey_combo

    def update_setting(self, config):
        page = getattr(self, "basic_page", None)
        if page is not None:
            page.update_setting(config)

    def available_ids(self):
        ids = {NavId.SYS_BASIC, NavId.SYS_ABOUT}
        if HAS_SCRIPT_UPDATE:
            ids.add(NavId.SCRIPTS_UPDATE)
        if HAS_WECHAT_PUSH:
            ids.add(NavId.SYS_PUSH)
        if HAS_USER:
            ids.add(NavId.SYS_ACCOUNT)
        if HAS_PUBLISH:
            ids.add(NavId.SCRIPTS_PUBLISH)
        return ids

    def page(self, nav_id):
        existing = self._pages.get(nav_id)
        if existing is not None:
            return existing
        page = self._create_page(nav_id)
        if page is not None:
            self._pages[nav_id] = page
        return page

    def _create_page(self, nav_id):
        try:
            if nav_id == NavId.SCRIPTS_UPDATE and HAS_SCRIPT_UPDATE:
                page = ScriptsUpdateWidget()
                page.updates_changed.connect(self.script_updates_changed.emit)
                return page
            if nav_id == NavId.SYS_PUSH and HAS_WECHAT_PUSH:
                return PushWidget()
            if nav_id == NavId.SYS_ACCOUNT and HAS_USER:
                page = UserWidget()
                page.LoginBadge.connect(self.login_badge.emit)
                return page
            if nav_id == NavId.SCRIPTS_PUBLISH and HAS_PUBLISH:
                return PublishWidget()
            if nav_id == NavId.SYS_ABOUT:
                from .about_win import AboutWidget
                return AboutWidget()
        except Exception as exc:
            BM_LOG.error("设置页面创建失败 %s: %s" % (nav_id, exc))
        return None

    def shutdown(self):
        for page in list(self._pages.values()):
            shutdown = getattr(page, "shutdown", None)
            if callable(shutdown):
                try:
                    shutdown()
                except Exception as exc:
                    BM_LOG.error("设置页面关闭失败: %s" % exc)
        self._pages.clear()
