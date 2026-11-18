"""
Copyright (c) 2026 綦恒智
Email: bmscriptsbox@163.com
SPDX-License-Identifier: MIT
SPDX-License-Identifier: LicenseRef-Commons-Clause

应用壳：共享服务、托盘、更新与两个独立窗口的协作。
"""
import ctypes
import importlib.util
import random

from PySide6.QtCore import QObject, QSize, QTimer
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication, QSystemTrayIcon

from xsideui import XIcon, tr

from app.utils import BM_LOG, BmNotify, BmTools
from app.view.config_center import NavId
from app.view.index_ui import custom_rc
from app.view.config_center.nav_spec import ACTION_NAV_IDS
from app.view.config_center.pages.scripts_page import ScriptsPage
from app.view.script_ui.script_pr import ScriptPresenter
from app.view.setting_ui import SettingsController

from .config_window import ConfigWindow
from .launcher_window import LauncherWindow
from .main_presenter import MainPresenter
from .tray_menu import build_tray_menu

XIcon.add_resource_path(':/custom/')

HAS_MARKET = importlib.util.find_spec(
    'app.cloud.view.market_ui.market_win') is not None
HAS_MARKET_CATALOG = importlib.util.find_spec(
    'app.cloud.market_catalog') is not None
if HAS_MARKET_CATALOG:
    from app.cloud.market_catalog import MarketCatalogService


class ApplicationShell(QObject):
    """应用级控制器：窗口、托盘与共享服务的唯一归属。"""

    def __init__(self, initial_args=None):
        super().__init__()
        self.args = initial_args
        self._tray_started = False
        self._closed = False
        self._pending_update = None
        self._update_window = None
        self._update_check = None
        self._scripts_cache = []
        self.scripts_page = None
        self.market_page = None
        self.scheduled_widget = None

        self.presenter = MainPresenter()
        self.market_catalog = (
            MarketCatalogService(self) if HAS_MARKET_CATALOG else None)
        self._script_presenter = ScriptPresenter()
        self._script_presenter.scripts_loaded.connect(self._on_scripts_loaded)
        self.settings_controller = SettingsController(self)

        self.launcher = LauncherWindow(
            self._script_presenter, self, self._launcher_size(),
            market_catalog=self.market_catalog)
        self.config = ConfigWindow(
            self._page_factories(), self._handle_nav_action, self,
            self._config_size())
        self._last_window = self.launcher

        try:
            from app.cloud.works.script_update_badge import ScriptUpdateBadgeChecker
            self._update_badge = ScriptUpdateBadgeChecker(self)
            self._update_badge.updates_available.connect(self._on_script_updates)
        except Exception:
            self._update_badge = None
        self.settings_controller.script_updates_changed.connect(
            self._on_script_updates)

        self.launcher.navigate_requested.connect(self.navigate)
        self.launcher.switch_window_requested.connect(self._switch_to_config)
        self.config.launcher_requested.connect(self.show_launcher)
        self.config.navigate_requested.connect(self.navigate)
        self.config.switch_window_requested.connect(self._switch_to_launcher)
        self.settings_controller.login_badge.connect(self.on_login_badge)
        self.settings_controller.language_changed.connect(self.config.retranslate)
        self.settings_controller.language_changed.connect(
            self._rebuild_tray_menu)
        self.settings_controller.install_finished.connect(
            self.on_install_finished)

        self._init_presenter_signals()
        self._create_system_tray()
        BmNotify.initialize(self.launcher)
        self.presenter.start()
        QTimer.singleShot(0, self._start_scripts)
        QTimer.singleShot(5000, self._refresh_script_updates)
        if self.market_catalog is not None:
            QTimer.singleShot(random.randint(3000, 30000),
                              self.market_catalog.sync_if_stale)

    # ---------- 启动 / 关闭 ----------

    def launch(self):
        from app.data.database import ConfigDatabase
        config = ConfigDatabase().get_all()
        if config.get('start_to_tray', False):
            self._tray_started = True
            BmNotify().show_success_notify(
                tr('BmScriptsBox is running in the system tray'), duration=3000,
                show_close=False)
            return
        self.show_launcher()

    def _start_scripts(self):
        self._script_presenter.load_scripts()

    def _on_scripts_loaded(self, scripts):
        self._scripts_cache = list(scripts or [])
        if self.scripts_page is not None:
            self.scripts_page.set_scripts(self._scripts_cache)

    def close_app(self):
        if self._closed:
            return
        self._closed = True
        if self._update_check is not None:
            try:
                self._update_check.stop()
            except Exception:
                pass
            self._update_check = None
        self.launcher.hide()
        self.config.hide()
        if self._update_window is not None:
            self._update_window.close()
            self._update_window = None
        if hasattr(self, 'tray'):
            self.tray.hide()
        if self.scheduled_widget is not None:
            try:
                self.scheduled_widget.presenter.scheduled_work.stop()
            except Exception as exc:
                BM_LOG.error("定时任务关闭失败: %s" % exc)
        self.config.shutdown()
        self.settings_controller.shutdown()
        self.launcher.shutdown()
        self._script_presenter.shutdown()
        self.presenter.shutdown()
        if self.market_catalog is not None:
            self.market_catalog.shutdown()
        from app.servers.scripts import ScriptRunner
        ScriptRunner.terminate_all()
        QApplication.quit()

    # ---------- 窗口切换 ----------

    def show_launcher(self, query="", focus=True):
        self.config.hide()
        self._last_window = self.launcher

        self._tray_started = False
        BmNotify.initialize(self.launcher)
        self.launcher.present(query, focus=focus)
        self._sync_update_visibility(self.launcher)
        self._flush_pending_update()

    def _switch_to_config(self):
        if QApplication.activeModalWidget() is not None:
            return
        self.show_config()

    def _switch_to_launcher(self):
        if QApplication.activeModalWidget() is not None:
            return
        self.show_launcher()

    def show_config(self, nav_id=None):
        self._refresh_script_updates()
        self.launcher.hide()
        self._last_window = self.config
        self._tray_started = False
        self.config.show_page(nav_id)
        BmNotify.initialize(self.config)
        self.config.present()
        self._sync_update_visibility(self.config)
        self._flush_pending_update()

    def navigate(self, nav_id):
        if not nav_id or nav_id == NavId.CONFIG:
            self.show_config()
            return
        if nav_id == NavId.SCRIPTS_MARKET and not HAS_MARKET:
            self.show_config(NavId.SCRIPTS_INSTALLED)
            return
        if nav_id in ACTION_NAV_IDS:
            self._handle_nav_action(nav_id)
            return
        self.show_config(nav_id)

    def _handle_nav_action(self, nav_id):
        if nav_id == NavId.SYS_CHECK_UPDATE:
            self._check_updates()

    def open_wechat_push_page(self):
        self.show_config(NavId.SYS_PUSH)

    # ---------- 页面工厂 ----------

    def _page_factories(self):
        factories = {
            NavId.SCRIPTS_INSTALLED: self._create_scripts_page,
            NavId.AUTO_CONTEXT: self._create_context_page,
            NavId.AUTO_HOTKEY: self._create_hotkey_page,
            NavId.AUTO_FAST_COPY: self._create_fast_copy_page,
            NavId.AUTO_SCHEDULER: self._create_scheduler_page,
            NavId.SYS_BASIC: lambda: self.settings_controller.page(
                NavId.SYS_BASIC),
        }
        if HAS_MARKET:
            factories[NavId.SCRIPTS_MARKET] = self._create_market_page
        for nav_id in self.settings_controller.available_ids():
            factories.setdefault(
                nav_id, lambda nid=nav_id: self.settings_controller.page(nid))
        return factories

    def _create_scripts_page(self):
        if self.scripts_page is None:
            self.scripts_page = ScriptsPage(self._script_presenter, self)
            self.scripts_page.set_scripts(self._scripts_cache)
        return self.scripts_page

    def _create_market_page(self):
        if self.market_page is None:
            from app.view.config_center.pages.market_page import MarketPage
            self.market_page = MarketPage(self.market_catalog)
            self.market_page.install_finished.connect(
                self.on_install_finished)
        return self.market_page

    @staticmethod
    def _create_context_page():
        from app.view.context_ui import ContextWidget
        return ContextWidget()

    @staticmethod
    def _create_hotkey_page():
        from app.view.hotkey_ui import HotkeyWidget
        return HotkeyWidget()

    @staticmethod
    def _create_fast_copy_page():
        from app.view.fast_text_ui import FastTextWidget
        return FastTextWidget()

    def _create_scheduler_page(self):
        if self.scheduled_widget is None:
            from app.view.scheduled_ui import ScheduledWidget
            self.scheduled_widget = ScheduledWidget()
        return self.scheduled_widget

    def on_install_finished(self, data: dict):
        if data.get('state'):
            self._script_presenter.refresh_scripts()

    def _refresh_script_updates(self):
        checker = getattr(self, '_update_badge', None)
        if checker is not None:
            checker.check()

    def _on_script_updates(self, count):
        self.config.set_script_updates(count > 0)

    def on_login_badge(self, needs_login):
        status = 'danger' if needs_login else 'success'
        self.config.set_account_status(status)

    # ---------- 窗口尺寸 ----------

    @staticmethod
    def _available_geometry():
        screen = QApplication.primaryScreen()
        return screen.availableGeometry()

    @classmethod
    def _launcher_size(cls):
        avail = cls._available_geometry()
        width = min(max(int(avail.width() * 0.12), 720), 860)
        height = min(max(int(avail.height() * 0.5), 440), 520)
        width = min(width, max(320, avail.width() - 40))
        height = min(height, max(320, avail.height() - 20))
        return QSize(width, height)

    @classmethod
    def _config_size(cls):
        avail = cls._available_geometry()
        width = min(max(int(avail.width() * 0.40), 1000), 1120)
        height = min(max(int(avail.height() * 0.72), 680), 860)
        width = min(width, max(320, avail.width() - 40))
        height = min(height, max(320, avail.height() - 20))
        return QSize(width, height)

    # ---------- 前台唤起 ----------

    def bring_to_front(self, widget):
        if widget is None:
            return
        if widget.isMinimized():
            widget.showNormal()
        widget.show()
        widget.raise_()
        widget.activateWindow()
        try:
            hwnd = int(widget.winId())
            user32 = ctypes.windll.user32
            user32.keybd_event(0x12, 0, 0, 0)
            user32.SetForegroundWindow(hwnd)
            user32.keybd_event(0x12, 0, 2, 0)
            user32.ShowWindow(hwnd, 5)
            user32.SetActiveWindow(hwnd)
        except Exception:
            pass
        if (not getattr(widget, 'is_show_animating', lambda: False)()
                and widget.isVisible() and widget.windowOpacity() < 0.999):
            widget.setWindowOpacity(1.0)

    # ---------- Presenter 信号 ----------

    def _init_presenter_signals(self):
        self.presenter.show_window.connect(self._on_show_window)
        self.presenter.activate_search.connect(self._on_activate_search)
        self.presenter.hide_window.connect(self._hide_windows)
        self.presenter.request_notify.connect(self._on_request_notify)
        self.presenter.show_login.connect(self._on_show_login)
        self.presenter.stop_login.connect(self._on_stop_login)
        self.presenter.show_update.connect(self._on_show_update)
        self.presenter.login_window.connect(self._on_login_window)

    def _on_activate_search(self):
        modal = QApplication.activeModalWidget()
        if modal is not None:
            self.bring_to_front(modal)
            return
        self.show_launcher()

    def _on_show_window(self):
        if self.config.isVisible():
            BmNotify.initialize(self.config)
            self.config.present()
            self._sync_update_visibility(self.config)
            return
        if self.launcher.isVisible():
            BmNotify.initialize(self.launcher)
            self.launcher.bring_to_front()
            self._sync_update_visibility(self.launcher)
            return
        if self._last_window is self.config:
            self.show_config(self.config.current_nav_id())
        else:
            self.show_launcher()

    def _hide_windows(self):
        self.launcher.hide()
        self.config.hide()

    def _on_request_notify(self, data: tuple):
        try:
            notify_type, message, duration, show_close = data
            notify_map = {
                'success': BmNotify().show_success_notify,
                'error': BmNotify().show_error_notify,
                'warning': BmNotify().show_warning_notify,
                'info': BmNotify().show_info_notify,
            }
            notify_func = notify_map.get(
                notify_type, BmNotify().show_info_notify)
            notify_func(content=message, duration=duration,
                        show_close=show_close)
        except Exception:
            BmNotify().show_error_notify(content=tr("Notification Failed"))

    def _on_show_login(self):
        self.show_config(NavId.SYS_ACCOUNT)

    def _on_stop_login(self):
        pass

    def _on_login_window(self):
        self.show_config(NavId.SYS_ACCOUNT)

    # ---------- 更新 ----------

    def _check_updates(self):
        if self._update_check is not None and self._update_check.isRunning():
            return
        try:
            from app.cloud.works import CheckUpdateWork
            self._update_check = CheckUpdateWork(self)
            self._update_check.update_signal.connect(self._on_update_checked)
            self._update_check.finished.connect(
                lambda: setattr(self, '_update_check', None))
            self._update_check.start()
        except Exception as exc:
            self._update_check = None
            BM_LOG.error("检查更新失败: %s" % exc)
            BmNotify().show_error_notify(str(exc))

    def _on_update_checked(self, data):
        if data.get('has_updates'):
            self._do_show_update(data)
        elif data.get('gate_reason'):
            # 跨运行时 / 版本跨度过大 / 清单过新：引导下载完整安装包
            BmNotify().show_warning_notify(
                data['gate_reason'], duration=6000, show_close=True,
                in_window=True)
        else:
            BmNotify().show_info_notify(
                tr('Already up to date'), duration=2500, show_close=False,
                in_window=True)

    def _on_show_update(self, data: dict):
        window = self._visible_window()
        if self._tray_started or window is None or window.isMinimized():
            self._pending_update = data
            return
        self._do_show_update(data, window)

    def _do_show_update(self, data: dict, parent=None):
        if not data.get("has_updates"):
            return
        if self._update_window is not None:
            self._sync_update_visibility(self._visible_window())
            return
        target = parent or self._visible_window() or self.launcher
        QTimer.singleShot(
            0, lambda d=data, p=target: self._present_update(d, p))

    def _present_update(self, data: dict, parent):
        if self._closed or not data.get("has_updates"):
            return
        if self._update_window is not None:
            self._sync_update_visibility(self._visible_window())
            return
        target = self._visible_window()
        if target is None:
            self._pending_update = data
            return
        from app.view.update_ui import UpdateWidget
        update_window = UpdateWidget(
            data.get("remote_version"),
            data.get("diff"),
            data.get("remote_details"),
            data.get("changelog"),
            data.get("local_version"),
            data.get("removed"),
            target,
        )
        self._update_window = update_window
        update_window.completed_single.connect(self._on_update_completed)
        update_window.finished.connect(
            lambda _=0, w=update_window: self._clear_update_window(w))
        update_window.destroyed.connect(
            lambda _=None, w=update_window: self._clear_update_window(w))
        update_window.show()
        update_window.raise_()
        update_window.activateWindow()

    def _clear_update_window(self, window):
        if self._update_window is window:
            self._update_window = None

    def _sync_update_visibility(self, target):
        window = self._update_window
        if window is None:
            return
        if target is not None and window.parent() is target:
            if not window.isVisible():
                window.show()
        elif window.isVisible():
            window.hide()

    def _on_update_completed(self, save_dir: str):
        self.presenter.start_update(save_dir)

    def _visible_window(self):
        if self.config.isVisible():
            return self.config
        if self.launcher.isVisible():
            return self.launcher
        return None

    def _flush_pending_update(self):
        if not self._pending_update:
            return
        window = self._visible_window()
        if window is None or window.isMinimized():
            return
        data = self._pending_update
        self._pending_update = None
        QTimer.singleShot(500, lambda: self._do_show_update(data, window))

    # ---------- 托盘 ----------

    def _create_system_tray(self):
        self.tray = QSystemTrayIcon(self)
        self.tray.setIcon(QIcon(BmTools.get_logo_path()))
        self.tray.setToolTip(tr('BmScriptsBox'))
        self._tray_menu = build_tray_menu(
            self.launcher, self._on_activate_search, self._on_config_menu,
            self.close_app)
        self.tray.setContextMenu(self._tray_menu)
        self.tray.activated.connect(self.presenter.on_tray_activated)
        self.tray.show()

    def _on_config_menu(self):
        self.show_config()

    def _rebuild_tray_menu(self):
        if not hasattr(self, 'tray'):
            return
        old_menu = getattr(self, '_tray_menu', None)
        self._tray_menu = build_tray_menu(
            self.launcher, self._on_activate_search, self._on_config_menu,
            self.close_app)
        self.tray.setContextMenu(self._tray_menu)
        if old_menu is not None:
            old_menu.deleteLater()
