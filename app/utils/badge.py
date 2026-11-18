"""
Copyright (c) 2026 綦恒智
Email: bmscriptsbox@163.com
SPDX-License-Identifier: MIT
SPDX-License-Identifier: LicenseRef-Commons-Clause

脚本徽章常量与统一样式。
"""
from PySide6.QtGui import QColor

from xsideui import theme_manager, XI18N

LOCAL_BADGE = "本地"
DEFAULT_BADGE_COLOR = "#909399"
BADGE_COLORS = {}


def _neutral_badge_color() -> str:
    return (theme_manager.semantic_color("text.tertiary", DEFAULT_BADGE_COLOR)
            or DEFAULT_BADGE_COLOR)


def badge_color(text):
    if text == LOCAL_BADGE:
        return _neutral_badge_color()
    return BADGE_COLORS.get(text, _neutral_badge_color())


def tinted_badge_colors(base_hex: str, fg_light: str = None,
                        fg_dark: str = None):
    """按当前主题生成浅色底 + 同色系文字（返回 QColor）。"""
    base = QColor(base_hex)
    if not base.isValid():
        base = QColor(_neutral_badge_color())
    background = QColor(base)
    background.setAlphaF(0.20 if theme_manager.is_dark else 0.12)
    if theme_manager.is_dark:
        foreground = QColor(fg_dark or base.lighter(135).name())
    else:
        foreground = QColor(fg_light or base.darker(125).name())
    return background, foreground


def badge_colors(text: str):
    """中性脚本徽章：浅色底 + 主题文字色。"""
    background, _ = tinted_badge_colors(badge_color(text))
    foreground = theme_manager.semantic_color(
        "text.primary", DEFAULT_BADGE_COLOR)
    return background, QColor(foreground or DEFAULT_BADGE_COLOR)


def _rgba(color: QColor) -> str:
    return (f"rgba({color.red()}, {color.green()}, {color.blue()}, "
            f"{color.alphaF():.3f})")


def badge_label_style(text: str) -> str:
    background, foreground = badge_colors(text)
    return (
        f"QLabel {{"
        f"  background-color: {_rgba(background)};"
        f"  color: {foreground.name()};"
        f"  padding: 1px 6px;"
        f"  border-radius: 4px;"
        f"  font-size: 11px;"
        f"}}"
    )


def is_local_badge(text):
    return text == LOCAL_BADGE


def badge_text(text: str) -> str:
    """徽章展示文案。

    LOCAL_BADGE 在库里是中文常量（参与判断与取色），展示时映射到英文 source 再查表；
    其余徽章（Installable / Installed 等）本身就是英文 source。
    徽章最终由原生 QLabel / XListView 绘制，不会自动查表，必须走这里。
    """
    if not text:
        return ""
    if is_local_badge(text):
        return XI18N.x_tr("Local")
    return XI18N.x_tr(text)
