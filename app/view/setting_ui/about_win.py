"""
Copyright (c) 2026 綦恒智
Email: bmscriptsbox@163.com
SPDX-License-Identifier: MIT
SPDX-License-Identifier: LicenseRef-Commons-Clause
"""
import webbrowser
import json
from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout
from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QDesktopServices
from xsideui import XImage, XLabel, tr, XPushButton, XButtonVariant, XColor, IconName
from app.utils import BmTools, BM_LOG
from app.data import ProjectGlobal


class AboutWidget(QWidget):
    def __init__(self):
        super(AboutWidget, self).__init__()
        self._init_ui()
        self._init_signal()
        self.get_version()

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
        """直接读本地发布清单的版本号。

        本地小文件，同步读取即可；之前放 QThread 里 start() 后才 connect，
        文件读得快时信号先发出、连接还没建立，标签就停在占位的 0.0.1 上。
        """
        try:
            with open(BmTools.get_resources_path() / 'version.json', encoding='utf-8') as f:
                version = json.load(f).get('version') or ''
        except (OSError, ValueError) as exc:
            BM_LOG.error(f"读取本地版本号失败: {exc}")
            version = ''
        self.version_label.setText(version or '—')



    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(11)
        soft_ico = XImage(source=BmTools.get_logo_path(),min_size=72)
        layout.addStretch()
        layout.addWidget(soft_ico, alignment=Qt.AlignVCenter | Qt.AlignHCenter)
        layout.addWidget(XLabel(tr('BmScriptsBox'), XLabel.Style.H1), alignment=Qt.AlignCenter)
        self.version_label = XLabel('—', XLabel.Style.CAPTION)
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



