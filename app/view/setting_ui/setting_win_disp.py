"""
Copyright (c) 2026 綦恒智
Email: bmscriptsbox@163.com
SPDX-License-Identifier: AGPL-3.0
"""
import sys
from pathlib import Path
from functools import partial
from pathlib import Path

from PySide2.QtCore import Signal
from PySide2.QtWidgets import QWidget, QVBoxLayout, QApplication, QFrame
from app.utils import BmTools
from xsideui import XGroupCard, XLabel, XLineEdit, XSwitch, XPushButton, XTabWidget, IconName, XButtonVariant, XSize, \
    tr, XComboBox, XColor, theme_manager, \
    XScrollArea
from app.data import ProjectGlobal
from .setting_pr import SettingPresenter
from .about_win import AboutWidget
from .proxy_win_set import ProxyWidget

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


class SettingWidget(QWidget):
    """软件设置"""
    Update = Signal(dict)
    HotKey = Signal()
    LoginBadge = Signal(bool)
    InstallFinished = Signal(dict)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.presenter = SettingPresenter(self)
        self._setup_ui()
        self._init_sigal()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(11, 11, 11, 11)
        layout.setSpacing(11)

        self.tabs = XTabWidget()
        layout.addWidget(self.tabs)

        self.tabs.addTab(self._basic_settings_card(), tr('Settings '))
        if HAS_SCRIPT_UPDATE and ScriptsUpdateWidget:
            self.tabs.addTab(ScriptsUpdateWidget(), tr('Script Update'))
        if HAS_USER and UserWidget:
            self.user_widget = UserWidget()
            self.tabs.addTab(self.user_widget, tr('Account '))
            self.user_widget.LoginBadge.connect(lambda x: self.LoginBadge.emit(x))
        if HAS_PUBLISH and PublishWidget:
            self.publish_widget = PublishWidget()
            self.tabs.addTab(self.publish_widget, tr('Developer'))
        self.tabs.addTab(AboutWidget(), tr('About'))

    def _init_sigal(self):
        self.middle_click_switch.clicked.connect(partial(self.presenter.update_setting, name='mouse_middle'))
        self.auto_start_switch.clicked.connect(self.presenter.add_to_startup)
        self.hotkey_combo.currentIndexChanged.connect(self.presenter.update_hotkey)
        self.check_log_btn.clicked.connect(self.presenter.check_log)
        self.clear_log_btn.clicked.connect(self.presenter.clear_log)
        self.clean_cache_btn.clicked.connect(self.presenter.clean_cache)
        self.proxy_btn.clicked.connect(self.open_proxy_win)
        self.language_combo.currentIndexChanged.connect(self.presenter.update_language)
        self.theme_combo.currentIndexChanged.connect(self.presenter.update_theme)

    def repost_no_login_signal(self, status):
        self.LoginBadge.emit(status)

    def open_proxy_win(self):
        proxy_win = ProxyWidget(parent=self)
        proxy_win.exec_()

    def update_setting(self, config):
        self.middle_click_switch.setChecked(config.get('mouse_middle'))
        self.auto_start_switch.setChecked(config.get('follow_start'))

        self.hotkey_combo.blockSignals(True)
        self.hotkey_combo.setCurrentText(config.get('shortcut_key_rouse')[0])
        self.hotkey_combo.blockSignals(False)

        self.language_combo.blockSignals(True)  # 暂时阻塞信号
        self.language_combo.setCurrentIndex(0 if ProjectGlobal.LANGUAGE == 'zh_CN' else 1)
        self.language_combo.blockSignals(False)  # 恢复信号

        self.theme_combo.blockSignals(True)
        self.theme_combo.setCurrentIndex(0 if theme_manager.theme_name == 'light' else 1)
        self.theme_combo.blockSignals(False)  # 恢复信号

    def _basic_settings_card(self):
        # 快捷键
        setting_area = XScrollArea()
        setting_area.setWidgetResizable(True)
        setting_area.set_scrollbar_visible(True, False)
        basic_frame = QFrame()
        setting_area.setWidget(basic_frame)
        basic_frame_layout = QVBoxLayout(basic_frame)
        basic_frame_layout.setContentsMargins(0, 0, 0, 0)
        self.basic_setting_card = XGroupCard(title=tr('Basic Config'))
        basic_frame_layout.addWidget(self.basic_setting_card)

        # 自启动
        start_group = self.basic_setting_card.add_group()
        self.basic_setting_card.addWidget(XLabel(tr('Launch on Startup')), group_index=start_group.index, stretch=1)
        self.auto_start_switch = XSwitch(size=XSize.SMALL, text_on='', text_off='')
        self.auto_start_switch.setObjectName('follow_start')
        self.basic_setting_card.addWidget(self.auto_start_switch, group_index=start_group.index, stretch=0)

        # 中键唤醒
        mouse_group = self.basic_setting_card.add_group()
        self.basic_setting_card.addWidget(XLabel(tr('Middle-Click Wake-up')), group_index=mouse_group.index, stretch=1)
        self.middle_click_switch = XSwitch(size=XSize.SMALL, text_on='', text_off='')
        self.middle_click_switch.setObjectName('mouse_middle')
        self.basic_setting_card.addWidget(self.middle_click_switch, group_index=mouse_group.index, stretch=0)

        # 快捷键唤醒
        hotkey_group = self.basic_setting_card.add_group()
        self.basic_setting_card.addWidget(XLabel(tr('Hotkey Wake-up (Double-Press)')), group_index=hotkey_group.index,
                                          stretch=1)
        self.hotkey_combo = XComboBox(size=XSize.SMALL)
        self.hotkey_combo.addItems(['ctrl', 'alt', 'shift', 'f11', 'f12'])
        self.hotkey_combo.setMinimumWidth(100)
        self.basic_setting_card.addWidget(self.hotkey_combo, group_index=hotkey_group.index, stretch=0)

        # 主题
        theme_group = self.basic_setting_card.add_group()
        self.basic_setting_card.addWidget(XLabel(tr('Theme Settings')), group_index=theme_group.index, stretch=1)
        self.theme_combo = XComboBox(size=XSize.SMALL)
        self.theme_combo.addItems(['light', 'dark'])
        self.theme_combo.setMinimumWidth(100)
        self.basic_setting_card.addWidget(self.theme_combo, group_index=theme_group.index, stretch=0)

        # 语言
        language_group = self.basic_setting_card.add_group()
        self.basic_setting_card.addWidget(XLabel(tr('Language Settings')), group_index=language_group.index, stretch=1)
        self.language_combo = XComboBox(size=XSize.SMALL)
        self.language_combo.addItems(['Chinese', 'English'])
        self.language_combo.setMinimumWidth(100)
        self.basic_setting_card.addWidget(self.language_combo, group_index=language_group.index, stretch=0)

        # 代理
        proxy_group = self.basic_setting_card.add_group()
        self.basic_setting_card.addWidget(XLabel(tr('Proxy Settings')), group_index=proxy_group.index, stretch=1)
        self.proxy_btn = XPushButton(text=tr('Edit'), size=XSize.SMALL, color=XColor.TERTIARY,
                                     variant=XButtonVariant.FILLED, icon=IconName.EDIT)
        self.basic_setting_card.addWidget(self.proxy_btn, group_index=proxy_group.index, stretch=0)

        # 清理缓存
        cache_group = self.basic_setting_card.add_group()
        self.basic_setting_card.addWidget(XLabel(tr('Cache Management')), group_index=cache_group.index, stretch=1)
        self.clean_cache_btn = XPushButton(text=tr('Clear'), size='small', color='danger',
                                           variant=XButtonVariant.FILLED, icon=IconName.CLEAR)
        self.basic_setting_card.addWidget(self.clean_cache_btn, group_index=cache_group.index, stretch=0)

        # 查看日志
        log_group = self.basic_setting_card.add_group()
        self.basic_setting_card.addWidget(XLabel(tr('Log Management')), group_index=log_group.index, stretch=1)
        self.check_log_btn = XPushButton(text=tr('View'), size='small', color='primary', variant=XButtonVariant.FILLED,
                                         icon=IconName.LOG)
        self.clear_log_btn = XPushButton(text=tr('Clear'), size='small', color='danger', variant=XButtonVariant.FILLED,
                                         icon=IconName.CLEAR)
        self.basic_setting_card.addWidget(self.check_log_btn, group_index=log_group.index, stretch=0)
        self.basic_setting_card.addWidget(self.clear_log_btn, group_index=log_group.index, stretch=0)

        # 数据
        self.group_card = XGroupCard(title=tr('Resource Management'))
        basic_frame_layout.addWidget(self.group_card)
        self.group_card.add_group()
        self.group_card.add_group()
        self.group_card.add_group()

        # 环境目录
        self.group_card.addWidget(XLabel(tr('Environment Variables：')), target=XGroupCard.CardPosition.GROUP,
                                  group_index=0, stretch=1)
        self.venv_lineedit = XLineEdit()
        self.venv_lineedit.setMinimumWidth(320)
        self.venv_lineedit.setReadOnly(True)
        self.venv_lineedit.setText(str(BmTools.get_root_path() / 'BmPackages' / 'bin'))
        self.group_card.addWidget(self.venv_lineedit, target=XGroupCard.CardPosition.GROUP, group_index=0, stretch=0)

        # 脚本目录
        self.group_card.addWidget(XLabel(tr('User Scripts Path：')), target=XGroupCard.CardPosition.GROUP, group_index=1,
                                  stretch=1)
        self.scripts_lineedit = XLineEdit()
        self.scripts_lineedit.setMinimumWidth(320)
        self.scripts_lineedit.setReadOnly(True)
        self.scripts_lineedit.setText(str(BmTools.get_root_path() / 'BmScripts'))
        self.group_card.addWidget(self.scripts_lineedit, target=XGroupCard.CardPosition.GROUP, group_index=1, stretch=0)

        # 全局缓存
        self.group_card.addWidget(XLabel(tr('Global Cache Path：')), target=XGroupCard.CardPosition.GROUP, group_index=2,
                                  stretch=1)
        self.cache_lineedit = XLineEdit()
        self.cache_lineedit.setMinimumWidth(320)
        self.cache_lineedit.setReadOnly(True)
        self.cache_lineedit.setText(str(BmTools.get_root_path() / 'BmPackages'/ 'BmCache'))
        self.group_card.addWidget(self.cache_lineedit, target=XGroupCard.CardPosition.GROUP, group_index=2, stretch=0)

        return setting_area


if __name__ == '__main__':
    app = QApplication(sys.argv)
    window = SettingWidget()
    window.show()
    sys.exit(app.exec_())
