"""
Copyright (c) 2026 綦恒智
Email: bmscriptsbox@163.com
SPDX-License-Identifier: MIT
SPDX-License-Identifier: LicenseRef-Commons-Clause

基础设置页：启动、唤醒、主题、语言、代理、日志与资源清理。
"""
from functools import partial

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QFrame, QVBoxLayout, QWidget
from click import style

from xsideui import (IconName, XButtonVariant, XColor, XComboBox, XGroupCard,
                     XLabel, XLineEdit, XLoadingMask, XMessageBox, XPushButton,
                     XScrollArea, XSize, XSwitch, tr, XI18N, theme_manager)

from app.data import ProjectGlobal
from app.utils import BM_LOG, BmNotify, BmTools

from .setting_pr import CleanResourceThread, ScanResourceThread


class BasicSettingsPage(QWidget):
    language_changed = Signal()

    def __init__(self, presenter, parent=None):
        super().__init__(parent)
        self.presenter = presenter
        self._loading = None
        self._scan_thread = None
        self._clean_thread = None
        self._setup_ui()
        self._connect_signals()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(11, 11, 11, 11)
        layout.setSpacing(20)

        setting_area = XScrollArea()
        setting_area.setWidgetResizable(True)
        setting_area.set_scrollbar_visible(False, False)
        frame = QFrame()
        setting_area.setWidget(frame)
        frame_layout = QVBoxLayout(frame)
        frame_layout.setContentsMargins(0, 0, 0, 0)
        frame_layout.setSpacing(10)


        frame_layout.addWidget(XLabel(tr("Basic Config"), style=XLabel.Style.H3))
        self.basic_setting_card = XGroupCard(title=tr('Launch on Startup'))
        frame_layout.addWidget(self.basic_setting_card)
        self.auto_start_switch = XSwitch(size=XSize.SMALL, text_on='',
                                         text_off='')
        self.auto_start_switch.setObjectName('follow_start')
        self.basic_setting_card.addWidget(
            self.auto_start_switch, target=XGroupCard.CardPosition.HEADER, stretch=0)

        mouse_group = self.basic_setting_card.add_group()
        self.basic_setting_card.addWidget(
            XLabel(tr('Middle-Click Wake-up')), group_index=mouse_group.index,
            stretch=1)
        self.middle_click_switch = XSwitch(size=XSize.SMALL, text_on='',
                                           text_off='')
        self.middle_click_switch.setObjectName('mouse_middle')
        self.basic_setting_card.addWidget(
            self.middle_click_switch, group_index=mouse_group.index, stretch=0)

        start_tray_group = self.basic_setting_card.add_group()
        self.basic_setting_card.addWidget(
            XLabel(tr('Start Minimized to Tray')), group_index=start_tray_group.index,
            stretch=1)
        self.start_tray_switch = XSwitch(size=XSize.SMALL, text_on='',
                                         text_off='')
        self.start_tray_switch.setObjectName('start_to_tray')
        self.basic_setting_card.addWidget(
            self.start_tray_switch, group_index=start_tray_group.index,
            stretch=0)

        hotkey_group = self.basic_setting_card.add_group()
        self.basic_setting_card.addWidget(
            XLabel(tr('Hotkey Wake-up (Double-Press)')),
            group_index=hotkey_group.index, stretch=1)
        self.hotkey_combo = XComboBox(size=XSize.SMALL)
        self.hotkey_combo.addItems(['ctrl', 'alt', 'shift', 'f11', 'f12'])
        self.hotkey_combo.setMinimumWidth(100)
        self.basic_setting_card.addWidget(
            self.hotkey_combo, group_index=hotkey_group.index, stretch=0)

        theme_group = self.basic_setting_card.add_group()
        self.basic_setting_card.addWidget(
            XLabel(tr('Theme Settings')), group_index=theme_group.index,
            stretch=1)
        self.theme_combo = XComboBox(size=XSize.SMALL)
        self.theme_combo.addItems(['light', 'dark'])
        self.theme_combo.setMinimumWidth(100)
        self.basic_setting_card.addWidget(
            self.theme_combo, group_index=theme_group.index, stretch=0)

        language_group = self.basic_setting_card.add_group()
        self.basic_setting_card.addWidget(
            XLabel(tr('Language Settings')), group_index=language_group.index,
            stretch=1)
        self.language_combo = XComboBox(size=XSize.SMALL)
        self.language_combo.addItems(['Chinese', 'English'])
        self.language_combo.setMinimumWidth(100)
        self.basic_setting_card.addWidget(
            self.language_combo, group_index=language_group.index, stretch=0)

        proxy_group = self.basic_setting_card.add_group()
        self.basic_setting_card.addWidget(
            XLabel(tr('Proxy Settings')), group_index=proxy_group.index,
            stretch=1)
        self.proxy_btn = XPushButton(
            text=tr('Edit'), size=XSize.SMALL, color=XColor.TERTIARY,
            variant=XButtonVariant.FILLED, icon=IconName.EDIT)
        self.basic_setting_card.addWidget(
            self.proxy_btn, group_index=proxy_group.index, stretch=0)

        cache_group = self.basic_setting_card.add_group()
        self.basic_setting_card.addWidget(
            XLabel(tr('Resource Cleanup')), group_index=cache_group.index,
            stretch=1)
        self.clean_cache_btn = XPushButton(
            text=tr('Clear'), size='small', color='danger',
            variant=XButtonVariant.FILLED, icon=IconName.CLEAR)
        self.basic_setting_card.addWidget(
            self.clean_cache_btn, group_index=cache_group.index, stretch=0)

        log_group = self.basic_setting_card.add_group()
        self.basic_setting_card.addWidget(
            XLabel(tr('Log Management')), group_index=log_group.index,
            stretch=1)
        self.check_log_btn = XPushButton(
            text=tr('View'), size='small', color='primary',
            variant=XButtonVariant.FILLED, icon=IconName.LOG)
        self.clear_log_btn = XPushButton(
            text=tr('Clear'), size='small', color='danger',
            variant=XButtonVariant.FILLED, icon=IconName.CLEAR)
        self.basic_setting_card.addWidget(
            self.check_log_btn, group_index=log_group.index, stretch=0)
        self.basic_setting_card.addWidget(
            self.clear_log_btn, group_index=log_group.index, stretch=0)


        frame_layout.addWidget(XLabel(tr("Resource Management"), style=XLabel.Style.H3) )
        self.group_card = XGroupCard(title=tr('Environment Variables:'))
        frame_layout.addWidget(self.group_card)
        self.group_card.add_group()
        self.group_card.add_group()

        self.venv_lineedit = XLineEdit()
        self.venv_lineedit.setMinimumWidth(420)
        self.venv_lineedit.setReadOnly(True)
        self.venv_lineedit.setText(
            str(BmTools.get_root_path() / 'BmPackages' / 'bin'))
        self.group_card.addWidget(
            self.venv_lineedit, target=XGroupCard.CardPosition.HEADER, stretch=0)

        self.group_card.addWidget(
            XLabel(tr('User Scripts Path:')),
            target=XGroupCard.CardPosition.GROUP, group_index=0, stretch=1)
        self.scripts_lineedit = XLineEdit()
        self.scripts_lineedit.setMinimumWidth(420)
        self.scripts_lineedit.setReadOnly(True)
        self.scripts_lineedit.setText(
            str(BmTools.get_root_path() / 'BmScripts'))
        self.group_card.addWidget(
            self.scripts_lineedit, target=XGroupCard.CardPosition.GROUP,
            group_index=0, stretch=0)

        self.group_card.addWidget(
            XLabel(tr('Global Cache Path:')),
            target=XGroupCard.CardPosition.GROUP, group_index=1, stretch=1)
        self.cache_lineedit = XLineEdit()
        self.cache_lineedit.setMinimumWidth(420)
        self.cache_lineedit.setReadOnly(True)
        self.cache_lineedit.setText(
            str(BmTools.get_root_path() / 'BmPackages' / 'BmCache'))
        self.group_card.addWidget(
            self.cache_lineedit, target=XGroupCard.CardPosition.GROUP,
            group_index=1, stretch=0)

        layout.addWidget(setting_area, 1)

    def _connect_signals(self):
        presenter = self.presenter
        self.middle_click_switch.clicked.connect(
            partial(presenter.update_setting, name='mouse_middle'))
        self.start_tray_switch.clicked.connect(
            partial(presenter.update_setting, name='start_to_tray'))
        self.auto_start_switch.clicked.connect(presenter.add_to_startup)
        self.hotkey_combo.currentIndexChanged.connect(presenter.update_hotkey)
        self.check_log_btn.clicked.connect(presenter.check_log)
        self.clear_log_btn.clicked.connect(presenter.clear_log)
        self.clean_cache_btn.clicked.connect(self._start_clean_resources)
        self.proxy_btn.clicked.connect(self._open_proxy_win)
        self.language_combo.currentIndexChanged.connect(
            presenter.update_language)
        self.language_combo.currentIndexChanged.connect(
            lambda _: self.language_changed.emit())
        self.theme_combo.currentIndexChanged.connect(presenter.update_theme)

    def update_setting(self, config):
        config = config or {}
        self.middle_click_switch.setChecked(bool(config.get('mouse_middle')))
        self.start_tray_switch.setChecked(bool(config.get('start_to_tray')))
        self.auto_start_switch.setChecked(bool(config.get('follow_start')))

        self.hotkey_combo.blockSignals(True)
        hotkey = config.get('shortcut_key_rouse') or ['ctrl']
        self.hotkey_combo.setCurrentText(hotkey[0])
        self.hotkey_combo.blockSignals(False)

        self.language_combo.blockSignals(True)
        self.language_combo.setCurrentIndex(
            0 if ProjectGlobal.LANGUAGE == 'zh_CN' else 1)
        self.language_combo.blockSignals(False)

        self.theme_combo.blockSignals(True)
        self.theme_combo.setCurrentIndex(
            0 if theme_manager.theme_name == 'light' else 1)
        self.theme_combo.blockSignals(False)

    def _open_proxy_win(self):
        from .proxy_win_set import ProxyWidget
        ProxyWidget(parent=self).exec()

    @staticmethod
    def _format_size(value) -> str:
        try:
            value = float(value)
        except (TypeError, ValueError):
            return "0 B"
        for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
            if value < 1024 or unit == 'TB':
                return (f"{value:.0f} B" if unit == 'B'
                        else f"{value:.1f} {unit}")
            value /= 1024
        return f"{value:.1f} TB"

    def _start_clean_resources(self):
        self._loading = XLoadingMask.show_loading(self, tr('Scanning...'))
        self._scan_thread = ScanResourceThread()
        self._scan_thread.scanned.connect(self._on_resources_scanned)
        self._scan_thread.start()

    def _on_resources_scanned(self, report: dict):
        if self._loading is not None:
            self._loading.hide()
        if not report:
            BmNotify().show_error_notify(tr('Scan failed'), in_window=True)
            return
        binaries = report.get('binaries', {})
        models = report.get('models', {})
        caches = report.get('caches', {})
        b_count = len(binaries.get('names', []))
        b_bytes = binaries.get('bytes', 0)
        m_count = len(models.get('repo_ids', []))
        m_bytes = models.get('bytes', 0)
        cache_names = [name for name, ok in
                       (('uv', caches.get('uv')), ('pnpm', caches.get('pnpm')))
                       if ok]
        if b_count == 0 and m_count == 0 and not cache_names:
            XMessageBox.information(self, tr('Resource Cleanup'),
                                    tr('No unused resources to clean'))
            return
        lines = [
            XI18N.x_tr("Binaries: %1 (%2)").replace("%1", str(b_count))
                .replace("%2", self._format_size(b_bytes)),
            XI18N.x_tr("Models: %1 (%2)").replace("%1", str(m_count))
                .replace("%2", self._format_size(m_bytes)),
        ]
        if cache_names:
            lines.append(XI18N.x_tr("Cache: trim Python / Node package caches"))
        lines.append(
            XI18N.x_tr("Estimated free space: %1").replace(
                "%1", self._format_size(report.get("total_bytes", 0))))
        message = "\n".join(lines) + "\n\n" + XI18N.x_tr("Only unused package caches, binaries and models are cleaned")
        if not XMessageBox.ask(self, tr('Resource Cleanup'), message):
            return
        self._loading = XLoadingMask.show_loading(self, tr('Cleaning...'))
        self._clean_thread = CleanResourceThread()
        self._clean_thread.cleaned.connect(self._on_resources_cleaned)
        self._clean_thread.start()

    def _on_resources_cleaned(self, result: dict):
        if self._loading is not None:
            self._loading.hide()
        if result.get('error'):
            BmNotify().show_error_notify(
                tr("Cleanup failed: %1").replace("%1", str(result['error'])),
                in_window=True)
            return
        freed = result.get('freed_bytes', 0)
        failures = result.get('failures', [])
        if failures:
            BmNotify().show_warning_notify(
                (tr("Cleanup partially failed (%1 items), freed %2")
                 .replace("%1", str(len(failures)))
                 .replace("%2", self._format_size(freed))),
                in_window=True)
        else:
            BmNotify().show_success_notify(
                tr("Cleanup finished, freed %1").replace("%1", self._format_size(freed)),
                in_window=True)
