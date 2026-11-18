"""
Copyright (c) 2026 綦恒智
Email: bmscriptsbox@163.com
SPDX-License-Identifier: MIT
SPDX-License-Identifier: LicenseRef-Commons-Clause
"""
import webbrowser
import json
from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout
from PySide6.QtCore import Qt, QUrl, QThread, Signal, QTimer
from PySide6.QtGui import QDesktopServices
from xsideui import XImage, XLabel, tr, XPushButton, XButtonVariant, XColor, IconName
from app.utils import BmTools, BM_LOG
from app.data import ProjectGlobal


class AboutWidget(QWidget):
    def __init__(self):
        super(AboutWidget, self).__init__()
        self.version_work = None
        self._init_ui()
        self._init_signal()
        QTimer.singleShot(100, self.get_version)

    def _init_signal(self):
        self.website_btn.clicked.connect(lambda: webbrowser.open(f'{ProjectGlobal.API_GATEWAY}'))
        self.help_btn.clicked.connect(lambda: webbrowser.open(f'{ProjectGlobal.API_GATEWAY}/help'))
        self.github_btn.clicked.connect(lambda: webbrowser.open('https://www.github.com/bm-qihengzhi/bmscriptsbox'))
        self.licenses_btn.clicked.connect(self.open_licenses_file)

    def open_licenses_file(self):
        file_path = BmTools.get_resources_path() / 'THIRD-PARTY LICENSES.txt'
        if file_path.exists():
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(file_path)))

    def get_version(self):
        self.version_work = SoftVersionWork()
        self.version_work.start()
        self.version_work.version_signal.connect(lambda version: self.version_label.setText(version))



    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(11)
        soft_ico = XImage(source=BmTools.get_logo_path(),min_size=72)
        layout.addStretch()
        layout.addWidget(soft_ico, alignment=Qt.AlignVCenter | Qt.AlignHCenter)
        layout.addWidget(XLabel(tr('BmScriptsBox'), XLabel.Style.H1), alignment=Qt.AlignCenter)
        self.version_label = XLabel('0.0.1', XLabel.Style.CAPTION)
        layout.addWidget(self.version_label, alignment=Qt.AlignCenter)

        btn_layout = QHBoxLayout()
        btn_layout.setContentsMargins(0, 20, 0, 0)
        self.website_btn = XPushButton(tr('Website'), variant=XButtonVariant.FILLED,
                                       color=XColor.SECONDARY, icon=IconName.BROWSER)

        self.help_btn = XPushButton(tr('Help'), variant=XButtonVariant.FILLED,  color=XColor.SECONDARY, icon=IconName.HELP)

        self.licenses_btn = XPushButton(tr('Licenses'), variant=XButtonVariant.FILLED, color=XColor.SECONDARY, icon=IconName.ABNORMAL)

        self.github_btn = XPushButton('GitHub', variant=XButtonVariant.FILLED,  color=XColor.SECONDARY,
                                      icon=IconName.GITHUB)

        btn_layout.addStretch()
        btn_layout.addWidget(self.website_btn)
        btn_layout.addWidget(self.help_btn)
        btn_layout.addWidget(self.licenses_btn)
        btn_layout.addWidget(self.github_btn)
        btn_layout.addStretch()

        layout.addLayout(btn_layout)
        layout.addWidget(XLabel(tr('This project is open source - stars and PRs welcome')), alignment=Qt.AlignCenter)
        layout.addWidget(
            XLabel(tr('Released under MIT + Commons Clause | (c) 2026 XiaMang Software Studio')),
            alignment=Qt.AlignCenter)
        layout.addStretch()



class SoftVersionWork(QThread):
    version_signal = Signal(str)
    def __init__(self, parent=None):
        super(SoftVersionWork, self).__init__(parent)

    def run(self):
        version_path = BmTools.get_resources_path() / 'version.json'
        if not version_path.exists():
            BM_LOG.error('version.json does not exist')
            return

        with open(version_path) as f:
            version_data = json.load(f)
            version = version_data.get('version','')
            self.version_signal.emit(version)


