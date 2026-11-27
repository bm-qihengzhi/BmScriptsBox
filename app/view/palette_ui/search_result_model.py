"""
Copyright (c) 2026 綦恒智
Email: bmscriptsbox@163.com
SPDX-License-Identifier: MIT
SPDX-License-Identifier: LicenseRef-Commons-Clause

启动器结果列表的 Model/View 数据模型。
"""
from dataclasses import dataclass
from typing import Optional

from PySide6.QtCore import QAbstractListModel, QModelIndex, QSize, Qt

from xsideui import IconName, XListBadge, XListItemRole, theme_manager, XI18N

from app.servers.launcher.models import SearchItem
from app.utils.badge import badge_color, badge_text

RESULT_HEIGHT = 48
TWO_LINE_RESULT_HEIGHT = 64

# 英文 source，展示时查表；不要在模块级调用 x_tr（UI 模块导入早于语言包加载）
_KIND_LABEL = {
    "script": ("Script", "primary"),
    "app": ("App", "success"),
    "uwp": ("App", "success"),
    "setting": ("Setting", "warning"),
    "tool": ("Tool", "neutral"),
    "command": ("Command", "neutral"),
    "calculator": ("Calculator", "error"),
    # 带参匹配本质仍是"某个脚本 + 带入了查询内容"，副标题已写明是哪种输入，
    # 类型徽章继续用「脚本」，避免同一脚本按名字/按参数搜到时时徽章不一致
    "script_input": ("Script", "primary"),
    "market_script": ("Market", "primary"),
}
_DEFAULT_KIND_COLOR = "neutral"


def _kind_color(family: str) -> str:
    fallback = theme_manager.semantic_color(
        "text.tertiary", "#909399") or "#909399"
    return theme_manager.palette_color(family, 6, fallback) or fallback


@dataclass
class SearchRow:
    item: Optional[SearchItem] = None
    text: str = ""
    selectable: bool = True


def row_height_for(item: SearchItem) -> int:
    if item.kind == "market_script":
        return TWO_LINE_RESULT_HEIGHT
    return RESULT_HEIGHT


def _subtitle_for(item: SearchItem):
    if item.kind == "market_script":
        return item.status or item.subtitle
    return ""


def _badges_for(item: SearchItem):
    badges = []
    label, family = _KIND_LABEL.get(item.kind, ("", _DEFAULT_KIND_COLOR))
    if label:
        badges.append(XListBadge(XI18N.x_tr(label), _kind_color(family)))
    if item.kind in ("script", "script_input", "market_script") and item.badge:
        badges.append(XListBadge(badge_text(item.badge), badge_color(item.badge)))
    return badges


class SearchResultModel(QAbstractListModel):
    def __init__(self, icon_cache, parent=None):
        super().__init__(parent)
        self._icon_cache = icon_cache
        self._rows = []
        theme_manager.theme_changed.connect(self._on_theme_changed)

    def _on_theme_changed(self, *args):
        if not self._rows:
            return
        top = self.index(0, 0)
        bottom = self.index(len(self._rows) - 1, 0)
        self.dataChanged.emit(top, bottom,
                              [XListItemRole.BADGES, Qt.DecorationRole])

    def rowCount(self, parent=QModelIndex()):
        if parent.isValid():
            return 0
        return len(self._rows)

    def data(self, index, role=Qt.DisplayRole):
        if not index.isValid() or not (0 <= index.row() < len(self._rows)):
            return None
        row = self._rows[index.row()]
        if row.item is None:
            if role == Qt.DisplayRole:
                return row.text
            if role == Qt.SizeHintRole:
                return QSize(0, RESULT_HEIGHT)
            return None

        item = row.item
        if role == Qt.DisplayRole:
            return item.display_title or item.title
        if role == Qt.DecorationRole:
            if self._icon_cache is None:
                return None
            return self._icon_cache.pixmap(item)
        if role == Qt.UserRole:
            return item
        if role == XListItemRole.SUBTITLE:
            return _subtitle_for(item)
        if role == XListItemRole.BADGES:
            return _badges_for(item)
        if role == XListItemRole.TRAILING_ICON:
            return IconName.PIN_FILL if item.pin else None
        if role == Qt.SizeHintRole:
            return QSize(0, row_height_for(item))
        return None

    def flags(self, index):
        if not index.isValid() or not (0 <= index.row() < len(self._rows)):
            return Qt.NoItemFlags
        flags = Qt.ItemIsEnabled
        if self._rows[index.row()].selectable:
            flags |= Qt.ItemIsSelectable
        return flags

    def append_item(self, item):
        return self.append_items([item])[0]

    def append_items(self, items):
        items = list(items or [])
        if not items:
            return []
        start = len(self._rows)
        self.beginInsertRows(QModelIndex(), start, start + len(items) - 1)
        try:
            for item in items:
                self._rows.append(SearchRow(item=item))
        finally:
            self.endInsertRows()
        return list(range(start, start + len(items)))

    def append_placeholder(self, text):
        # placeholder 是 model 里的纯文本行，delegate 直接绘制，同样需要查表
        start = len(self._rows)
        self.beginInsertRows(QModelIndex(), start, start)
        try:
            self._rows.append(SearchRow(text=str(XI18N.x_tr(text)), selectable=False))
        finally:
            self.endInsertRows()
        return start

    def clear(self):
        if not self._rows:
            return
        self.beginResetModel()
        try:
            self._rows.clear()
        finally:
            self.endResetModel()

    def row_count(self):
        return len(self._rows)

    def index_for_row(self, row):
        if row is None or row < 0 or row >= len(self._rows):
            return QModelIndex()
        return self.index(row, 0)

    def row_for_id(self, item_id):
        if not item_id:
            return None
        for row, entry in enumerate(self._rows):
            if entry.item is not None and entry.item.id == item_id:
                return row
        return None

    def set_item_status(self, item_id: str, status: str):
        row = self.row_for_id(item_id)
        if row is None:
            return
        item = self.item_at(row)
        if item is None:
            return
        item.status = status
        index = self.index(row, 0)
        self.dataChanged.emit(
            index, index,
            [XListItemRole.SUBTITLE, XListItemRole.BADGES, Qt.DisplayRole])

    def item_at(self, row):
        if not (0 <= row < len(self._rows)):
            return None
        return self._rows[row].item

    def is_selectable(self, row):
        if not (0 <= row < len(self._rows)):
            return False
        return self._rows[row].selectable
