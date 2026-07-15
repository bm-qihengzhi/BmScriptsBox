"""
Copyright (c) 2026 綦恒智
Email: bmscriptsbox@163.com
SPDX-License-Identifier: AGPL-3.0
"""
import ctypes
import importlib.util
from PySide2.QtCore import QTimer, QObject, Signal, QPoint, QEvent
from PySide2.QtGui import QIcon, Qt
from PySide2.QtWidgets import QApplication, QHBoxLayout, QStackedWidget, QSystemTrayIcon, QFrame, QWidget, QVBoxLayout
from xsideui import XMenu, XNavSimple, IconName, XIcon, XWidget, tr, XColor, XIconBadge, XPushButton, XButtonVariant, \
    XSize, XImage, XDialog, XLabel

from app.utils import BmTools, BmNotify
from app.view.index_ui.index_pr import MainPresenter

HAS_MARKET = importlib.util.find_spec('app.cloud.view.market_ui.market_win') is not None
HAS_USER = importlib.util.find_spec('app.cloud.view.user_win') is not None
HAS_SCRIPT_UPDATE = importlib.util.find_spec('app.cloud.view.update_win') is not None


class MouseSignals(QObject):
    click_outside = Signal()


class MainView(XWidget):
    """程序主窗口"""

    def __init__(self, initial_args=None):
        super().__init__()
        self.args = initial_args
        self.presenter = MainPresenter()
        self.mouse_signals = None
        self.mouse_listener = None
        self.is_listening = False
        self.presenter.start()
        self._setup_ui()
        QTimer.singleShot(0, self._init_stack_pages)
        self._init_presenter_signals()


    def _setup_ui(self):
        """初始化界面"""
        screen = QApplication.primaryScreen().availableGeometry()
        width = int(min(screen.width() * 0.3, 560))
        height = int(width * 1.2)
        self.resize(width, height)
        self.set_title(tr('BmScriptsBox'))
        self.hide_maximize_button()
        self._create_qr_button()
        self.set_logo(BmTools.get_logo_path())

        self.home_widget = QFrame()
        self.layout = QHBoxLayout(self.home_widget)
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.layout.setSpacing(0)

        self.nav_bar = XNavSimple()
        self._init_nav_items()

        self.stack = QStackedWidget()
        self.stack.setObjectName("stack")

        self.layout.addWidget(self.nav_bar, 0)
        self.layout.addWidget(self.stack, 1)
        self.addWidget(self.home_widget)

    def eventFilter(self, obj, event):
        if obj in (self.create_qr_button, self._qr_dialog):
            if event.type() == QEvent.Enter:
                self._qr_timer.start(200)
            elif event.type() == QEvent.Leave:
                self._qr_timer.stop()
                self._hide_qr_hover()
        return super().eventFilter(obj, event)


    def _create_qr_button(self):
        self.create_qr_button = XPushButton(variant=XButtonVariant.TEXT, icon=IconName.TWO_DIMENSIONAL_CODE, color=XColor.SECONDARY, size=XSize.SMALL)

        self._qr_dialog = QrDialog(self)
        self._qr_timer = QTimer(self)
        self._qr_timer.setSingleShot(True)
        self._qr_timer.timeout.connect(self._show_qr_hover)

        self.create_qr_button.installEventFilter(self)
        self._qr_dialog.installEventFilter(self)

        self.add_title_bar_widget(self.create_qr_button)

    def _show_qr_hover(self):
        self._qr_dialog.show()

    def _hide_qr_hover(self):
        self._qr_dialog.hide()

    def _init_nav_items(self):
        """初始化导航项"""
        self.nav_bar.add_item("code", IconName.CODE, tr('Scripts'))
        self.nav_bar.add_item("mouse", IconName.MOUSE, tr("Context Menu Trigger"))
        self.nav_bar.add_item("keyboard", IconName.KEYBOARD, tr("Hotkey Trigger"))
        self.nav_bar.add_item("copy", IconName.CLIPBOARD, tr("Quick Copy Trigger"))
        self.nav_bar.add_item("time", IconName.HISTORY, tr("Scheduler"))

        if HAS_MARKET or HAS_SCRIPT_UPDATE:
            self.nav_bar.add_item("market", IconName.APPLICATION, tr("Market"), "bottom")
        self.nav_bar.add_item("setting", IconName.SETTING, tr("Settings"), "bottom")
        if HAS_USER:
            self.nav_bar.add_item("me", IconName.ME, tr("User"), "bottom")
        self.nav_bar.set_current_item("code")

    def _init_stack_pages(self):
        """初始化页面栈"""
        from ..script_ui import ScriptsWidget
        self.scripts_widget = ScriptsWidget()
        self.scripts_widget.ScriptHub.connect(self._show_market)
        self.stack.insertWidget(0, self.scripts_widget)
        QTimer.singleShot(100, self._load_lazy_pages)

    def _show_market(self):
        if HAS_MARKET:
            from app.cloud.view.market_ui.market_win import MarketWidget
            if MarketWidget:
                self.stack.setCurrentIndex(7)
                self.nav_bar.set_current_item("market")
                return
        from ..script_ui.script_win_inst import InstallScriptWindow
        dlg = InstallScriptWindow(parent=self)
        dlg.success_signal.connect(self.on_install_finished)
        dlg.exec_()

    def _load_lazy_pages(self):
        """延迟加载页面"""
        from ..context_ui import ContextWidget
        from ..hotkey_ui import HotkeyWidget
        from ..fast_text_ui import FastTextWidget
        from ..scheduled_ui import ScheduledWidget
        from ..setting_ui import SettingWidget

        self.stack.insertWidget(1, ContextWidget())
        self.stack.insertWidget(2, HotkeyWidget())
        self.stack.insertWidget(3, FastTextWidget())
        self.scheduled_widget = ScheduledWidget()
        self.stack.insertWidget(4, self.scheduled_widget)
        self.settings_widget = SettingWidget()
        if HAS_USER:
            self.settings_widget.LoginBadge.connect(self.on_login_badge)
        self.settings_widget.InstallFinished.connect(self.on_install_finished)
        self.stack.insertWidget(6, self.settings_widget)
        if HAS_MARKET:
            from app.cloud.view.market_ui.market_win import MarketWidget
            self.market_widget = MarketWidget()
            self.market_widget.install_finished.connect(self.on_install_finished)
            self.stack.insertWidget(7, self.market_widget)
        else:
            self.stack.insertWidget(7, QWidget())
        if HAS_USER:
            from app.cloud.view.user_win import UserWidget
            self.user_widget = UserWidget()
            self.stack.insertWidget(5, self.user_widget)
        else:
            self.stack.insertWidget(5, QWidget())
        self.stack.setCurrentIndex(0)
        self._create_system_tray()
        BmNotify.initialize(self)

    def _create_system_tray(self):
        """创建系统托盘"""
        self.tray = QSystemTrayIcon(self)
        self.tray.setIcon(QIcon(BmTools.get_logo_path()))
        self.tray.setToolTip(tr('BmScriptsBox'))

        menu = XMenu(self)
        menu.add_action(tr('View'), XIcon.get(name=IconName.EYE_ON).icon(), self._on_show_window)
        menu.add_action(tr('Quit'), XIcon.get(name=IconName.POWER).icon(), self.close_app)
        self.tray.setContextMenu(menu)
        self.tray.activated.connect(self.presenter.on_tray_activated)
        self.tray.show()

    def _init_presenter_signals(self):
        """连接 Presenter 信号"""
        self.presenter.show_window.connect(self._on_show_window)
        self.presenter.hide_window.connect(self.hide)
        self.presenter.switch_page.connect(self._on_switch_page)
        self.presenter.request_notify.connect(self._on_request_notify)
        self.presenter.show_login.connect(self._on_show_login)
        self.presenter.stop_login.connect(self._on_stop_login)
        self.presenter.show_update.connect(self._on_show_update)
        self.presenter.login_window.connect(self._on_login_window)

        self.nav_bar.changed.connect(self.presenter.on_nav_changed)

    def on_install_finished(self, data: dict):
        if data.get('state'):
            self.scripts_widget.presenter.refresh_scripts()

    def _on_login_window(self):
        """用户登陆页面"""

        if not HAS_USER:
            return
        self.stack.setCurrentIndex(6)
        if hasattr(self.settings_widget, 'tabs'):
            self.settings_widget.tabs.setCurrentIndex(2)

    def on_login_badge(self, status):
        """未登录状态徽章管理"""
        item = self.nav_bar.get_item('me')
        if status:
            XIconBadge(item, icon_name=IconName.DOT, color=XColor.DANGER, size=14, offset=QPoint(-8, 8))
        else:
            XIconBadge.remove_all_from(item)

    def _on_show_window(self):
        """显示/唤醒窗口"""
        modal = QApplication.activeModalWidget()
        target_widget = modal if (modal and modal != self) else self

        try:
            hwnd = int(target_widget.winId())
        except (TypeError, ValueError):
            hwnd = ctypes.c_void_p(int(target_widget.winId())).value

        if not hwnd:
            return

        if target_widget == self:
            if self.isMinimized() or not self.isVisible():
                self.showNormal()
            self.show()
            self.raise_()
            self.activateWindow()
        else:
            if target_widget.isMinimized():
                ctypes.windll.user32.ShowWindow(hwnd, 9)  # SW_RESTORE

        user32 = ctypes.windll.user32
        SW_SHOW = 5

        user32.keybd_event(0x12, 0, 0, 0)
        user32.SetForegroundWindow(hwnd)
        user32.keybd_event(0x12, 0, 2, 0)

        user32.ShowWindow(hwnd, SW_SHOW)
        user32.SetActiveWindow(hwnd)

    def _on_switch_page(self, index: int):
        """切换页面"""
        self.stack.setCurrentIndex(index)
        if hasattr(self, 'settings_widget'):
            self.settings_widget.tabs.setCurrentIndex(0)

    def _on_request_notify(self, data: tuple):
        """显示通知"""
        try:
            notify_type, message, duration, show_close = data
            notify_map = {
                'success': BmNotify().show_success_notify,
                'error': BmNotify().show_error_notify,
                'warning': BmNotify().show_warning_notify,
                'info': BmNotify().show_info_notify,
            }
            notify_func = notify_map.get(notify_type, BmNotify().show_info_notify)
            notify_func(content=message, duration=duration, show_close=show_close)
        except Exception as e:
            BmNotify().show_error_notify(content=tr("Notify Failed"))

    def _on_show_login(self):
        """显示登录"""
        self.stack.setCurrentIndex(6)
        self.nav_bar.set_current_item("me")
        if hasattr(self, 'login_widget'):
            QTimer.singleShot(100, self.login_widget.start_login)

    def _on_stop_login(self):
        """停止登录"""
        if hasattr(self, 'login_widget'):
            QTimer.singleShot(100, self.login_widget.stop)

    def _on_show_update(self, data: dict):
        """显示更新"""
        if data.get("has_updates"):
            from ..update_ui import UpdateWidget
            update_window = UpdateWidget(
                data.get("remote_version"),
                data.get("diff"),
                self.window()
            )
            update_window.completed_single.connect(self._on_update_completed)
            update_window.exec_()

    def _on_update_completed(self, save_dir: str):
        """更新完成"""
        self.presenter.start_update(save_dir)

    def close_app(self):
        """关闭应用"""
        self.hide()
        if hasattr(self, 'tray'):
            self.tray.hide()
        self.presenter.shutdown()
        if self.scheduled_widget:
            self.scheduled_widget.presenter.scheduled_work.stop()
        from app.servers.scripts import ScriptRunner
        ScriptRunner.terminate_all()
        QApplication.quit()


class QrDialog(XDialog):
    def __init__(self, parent=None):
        super(QrDialog, self).__init__(parent=parent)
        self.setModal(False)
        self._init_ui()


    def _init_ui(self):
        self.hide_title_bar()
        context_widget = QWidget()
        self.addWidget(context_widget)
        layout = QVBoxLayout(context_widget)
        layout.setContentsMargins(20,20,20,20)
        qr_path = BmTools.get_resources_path() / 'imgs' / 'wechat_qr.jpg'
        img_label = XImage(source=str(qr_path),min_size=200)
        layout.addWidget(img_label)
        layout.addWidget(XLabel('不忙官方公众号'), alignment=Qt.AlignCenter)
