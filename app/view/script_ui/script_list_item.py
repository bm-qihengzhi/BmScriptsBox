"""
Copyright (c) 2026 綦恒智
Email: bmscriptsbox@163.com
SPDX-License-Identifier: MIT
SPDX-License-Identifier: LicenseRef-Commons-Clause

搜索结果列表的透明行控件。
行本身不绘制背景和选中态，交互与选中背景全部交给 XListWidget。
"""
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QHBoxLayout, QLabel, QSizePolicy, QWidget

from xsideui import XColor, XIcon, XImage, XLabel, IconName, theme_manager

from app.utils import BmTools
from app.utils.badge import badge_label_style, badge_text


class ScriptListItemWidget(QWidget):
    """搜索结果中的一行，透明背景、鼠标事件穿透给列表。"""

    def __init__(self, script_info, parent=None):
        super().__init__(parent)
        self.script_info = script_info
        self._badge_label = None
        self._pin_label = None
        self.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 0, 10, 0)
        layout.setSpacing(8)

        icon = script_info.icon or BmTools.get_language_icon_path(
            script_info.language)
        self.img = XImage(source=icon, fit=XImage.FitMode.COVER,
                          lazy=True, min_size=24)
        self.img.setFixedSize(24, 24)
        self.img.setContextMenuPolicy(Qt.NoContextMenu)
        self.img.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        layout.addWidget(self.img, 0, Qt.AlignVCenter)

        self.title_label = XLabel(script_info.name, elide_mode=True)
        self.title_label.setSizePolicy(QSizePolicy.Ignored,
                                       QSizePolicy.Preferred)
        self.title_label.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        layout.addWidget(self.title_label, 1, Qt.AlignVCenter)

        if script_info.pin:
            pin = QLabel(self)
            pin.setFixedSize(14, 14)
            pin.setAttribute(Qt.WA_TransparentForMouseEvents, True)
            layout.addWidget(pin, 0, Qt.AlignVCenter)
            self._pin_label = pin
            self._refresh_pin()

        if script_info.badge:
            badge = QLabel(badge_text(script_info.badge), self)
            badge.setStyleSheet(badge_label_style(script_info.badge))
            badge.adjustSize()
            badge.setAttribute(Qt.WA_TransparentForMouseEvents, True)
            layout.addWidget(badge, 0, Qt.AlignVCenter)
            self._badge_label = badge

        if self._pin_label is not None or self._badge_label is not None:
            theme_manager.theme_changed.connect(self._refresh_theme)

    def _refresh_theme(self, *args):
        """主题切换后刷新图钉与徽章颜色"""
        self._refresh_pin()
        badge = self._badge_label
        if badge is None:
            return
        badge.setStyleSheet(badge_label_style(self.script_info.badge))
        badge.adjustSize()

    def _refresh_pin(self):
        if self._pin_label is None:
            return
        self._pin_label.setPixmap(
            XIcon.get(name=IconName.PIN_FILL,
                      color=XColor.TERTIARY, size=14).pixmap())
