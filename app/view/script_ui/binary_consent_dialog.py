"""
Copyright (c) 2026 綦恒智
Email: bmscriptsbox@163.com
SPDX-License-Identifier: MIT
SPDX-License-Identifier: LicenseRef-Commons-Clause

外部二进制下载确认对话框：脚本声明作者直连（GitHub）二进制时，
安装前展示来源、标签与指纹信息，由用户决定是否允许下载/部署。
- 拒绝 → 安装失败并回滚；
- 允许 → 本次放行；
- 允许并记住 → 写入信任表，同脚本同来源后续不再询问。
"""
from urllib.parse import urlparse

from PySide2.QtCore import Qt
from PySide2.QtWidgets import QVBoxLayout, QHBoxLayout, QWidget

from xsideui import (XPushButton, XButtonVariant, XColor, tr, XDialog, XLabel)


class BinaryConsentDialog(XDialog):
    """外部二进制下载确认弹窗"""

    def __init__(self, payload: dict, parent=None):
        super().__init__(parent)
        self._payload = payload or {}
        self._allow = False
        self._remember = False
        self._setup_ui()

    def _setup_ui(self):
        p = self._payload
        name = p.get('name', '')
        url = p.get('url', '')
        tag = p.get('tag', '') or 'latest'
        sha = p.get('sha256', '') or ''
        is_installer = bool(p.get('is_installer'))

        self.set_title(tr('External Binary Download'))
        self.setMinimumWidth(480)

        body = QWidget()
        self.addWidget(body)
        lay = QVBoxLayout(body)
        lay.setContentsMargins(20, 20, 20, 12)
        lay.setSpacing(10)

        lay.addWidget(XLabel(tr('The script requests to download and deploy an external executable.')).set_font_size(13))
        lay.addWidget(XLabel(tr('Please confirm the source is trustworthy before allowing.')).set_font_size(12).set_color(XColor.TERTIARY))

        host = ''
        try:
            host = urlparse(url).netloc
        except Exception:
            host = ''

        info = (
            f"{tr('Name')}: {name}\n"
            f"{tr('Source')}: {host or url}\n"
            f"{tr('Tag')}: {tag}\n"
            f"{tr('SHA256')}: {sha or tr('(record on first download)')}"
        )
        if is_installer:
            info += "\n" + tr('Warning: it will run a silent installer (per-user, no auto-elevation).')
        lay.addWidget(XLabel(info).set_font_size(12))
        lay.addWidget(XLabel(url,word_wrap=True).set_font_size(12).set_color(XColor.TERTIARY))

        btn_row = QHBoxLayout()
        btn_row.addStretch()
        reject_btn = XPushButton(text=tr('Reject'), variant=XButtonVariant.OUTLINED, color=XColor.DANGER)
        reject_btn.clicked.connect(self._on_reject)
        btn_row.addWidget(reject_btn)

        once_btn = XPushButton(text=tr('Allow Once'), variant=XButtonVariant.OUTLINED, color=XColor.SECONDARY)
        once_btn.clicked.connect(self._on_allow_once)
        btn_row.addWidget(once_btn)

        remember_btn = XPushButton(text=tr('Allow and Remember'))
        remember_btn.clicked.connect(self._on_allow_remember)
        btn_row.addWidget(remember_btn)

        lay.addLayout(btn_row)

        self.setWindowFlag(Qt.WindowStaysOnTopHint, True)
        self.raise_()

    def _on_reject(self):
        self._allow = False
        self._remember = False
        self.reject()

    def _on_allow_once(self):
        self._allow = True
        self._remember = False
        self.accept()

    def _on_allow_remember(self):
        self._allow = True
        self._remember = True
        self.accept()

    def get_result(self):
        """返回 (allow, remember)"""
        return self._allow, self._remember
