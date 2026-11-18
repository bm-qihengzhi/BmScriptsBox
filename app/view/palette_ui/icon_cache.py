"""
Copyright (c) 2026 綦恒智
Email: bmscriptsbox@163.com
SPDX-License-Identifier: MIT
SPDX-License-Identifier: LicenseRef-Commons-Clause

命令面板图标缓存：UI 只读内存/磁盘，桌面应用图标由后台 worker 提取。
"""
import hashlib
from pathlib import Path
from typing import Dict, List, Optional

from PySide6.QtCore import QObject, QSize, Qt, Signal
from PySide6.QtGui import QGuiApplication, QIcon, QPixmap

from xsideui import XColor, XIcon, IconName, theme_manager

from app.servers.launcher.models import SearchItem
from app.utils import BmTools

from .icon_worker import IconExtractWorker

_IMAGE_SUFFIXES = (".png", ".jpg", ".jpeg", ".bmp", ".gif", ".svg", ".ico")

ICON_SIZE = 24


def _screen_dpr() -> float:
    screen = QGuiApplication.primaryScreen()
    return float(screen.devicePixelRatio()) if screen is not None else 1.0


def _icon_pixmap(path: str, size: int = ICON_SIZE) -> QPixmap:
    """按屏幕 DPR 取图标位图，否则结果列表在高 DPI 下会拉伸发虚。"""
    return QIcon(path).pixmap(QSize(size, size), _screen_dpr())


def _fit_pixmap(pixmap: QPixmap, size: int = ICON_SIZE) -> QPixmap:
    """把磁盘上取回的位图归一到 size 逻辑像素，避免偏大或拉伸。"""
    dpr = _screen_dpr()
    target = max(1, int(round(size * dpr)))
    if pixmap.width() != target or pixmap.height() != target:
        pixmap = pixmap.scaled(target, target, Qt.KeepAspectRatio,
                               Qt.SmoothTransformation)
    pixmap.setDevicePixelRatio(dpr)
    return pixmap


_GENERIC_ICON = {
    "script": IconName.APPLICATION,
    "app": IconName.APPLICATION,
    "uwp": IconName.APPLICATION,
    "setting": IconName.SETTING,
    "tool": IconName.TOOL,
    "file": IconName.FILE,
    "folder": IconName.FOLDER,
    "content": IconName.FILE_TEXT,
}


class IconCache(QObject):
    icon_ready = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._cache: Dict[str, QPixmap] = {}
        self._generic: Dict[str, QPixmap] = {}
        self._queue: List[tuple] = []
        self._queued = set()
        self._failed = set()
        self._worker: Optional[IconExtractWorker] = None
        self._closing = False
        self._icon_dir = (BmTools.get_root_path() / "BmCache" /
                          "launcher" / "icons")
        self._icon_dir.mkdir(parents=True, exist_ok=True)

    def pixmap(self, item: SearchItem) -> QPixmap:
        path = item.icon_path
        if path:
            suffix = Path(path).suffix.lower()
            if suffix in _IMAGE_SUFFIXES:
                key = self._file_key("image", path, suffix)
                cached = self._cache.get(key)
                if cached is not None:
                    return cached
                pixmap = _icon_pixmap(path)
                if not pixmap.isNull():
                    self._cache[key] = pixmap
                    return pixmap
            else:
                key = self._file_key("shell", path, suffix)
                cached = self._cache.get(key)
                if cached is not None:
                    return cached
                disk = self._disk_path(key)
                if disk.exists():
                    pixmap = QPixmap(str(disk))
                    if not pixmap.isNull():
                        pixmap = _fit_pixmap(pixmap)
                        self._cache[key] = pixmap
                        return pixmap
                if key not in self._failed:
                    self._enqueue(path, key)

        if item.icon_name:
            name = str(item.icon_name)
            key = self._theme_key(name)
            cached = self._generic.get(key)
            if cached is None:
                cached = XIcon.get(name, size=24,
                                   color=XColor.SECONDARY).pixmap()
                self._generic[key] = cached
            return cached

        icon_name = _GENERIC_ICON.get(item.kind, IconName.APPLICATION)
        return self._generic_pixmap(icon_name)

    def warm_items(self, items, replace=False):
        if replace:
            self._queue = []
            self._queued.clear()
        for item in items:
            path = item.icon_path
            if not path:
                continue
            suffix = Path(path).suffix.lower()
            if suffix in _IMAGE_SUFFIXES:
                continue
            key = self._file_key("shell", path, suffix)
            if (key in self._cache or key in self._failed
                    or key in self._queued
                    or self._disk_path(key).exists()):
                continue
            self._enqueue(path, key)
        self._start_worker()

    def _generic_pixmap(self, icon_name):
        key = self._theme_key(icon_name)
        pixmap = self._generic.get(key)
        if pixmap is None:
            pixmap = XIcon.get(icon_name, size=24,
                               color=XColor.SECONDARY).pixmap()
            self._generic[key] = pixmap
        return pixmap

    @staticmethod
    def _theme_key(icon_name) -> str:
        return "%s|%s|%s" % (
            theme_manager.theme_name,
            getattr(theme_manager, "theme_revision", ""),
            icon_name,
        )

    @staticmethod
    def _file_key(kind: str, path: str, suffix: str) -> str:
        try:
            mtime = int(Path(path).stat().st_mtime)
        except OSError:
            mtime = 0
        raw = "%s|%s|%s|%s" % (kind, path, suffix, mtime)
        return hashlib.md5(raw.encode("utf-8", "ignore")).hexdigest()

    def _disk_path(self, key: str) -> Path:
        return self._icon_dir / ("%s.png" % key)

    def _enqueue(self, path: str, key: str):
        if key in self._queued or key in self._failed:
            return
        self._queued.add(key)
        self._queue.append((path, key, str(self._disk_path(key))))

    def _start_worker(self):
        if self._closing or self._worker is not None or not self._queue:
            return
        batch = [self._queue.pop(0) for _ in range(min(40, len(self._queue)))]
        worker = IconExtractWorker(batch, self)
        worker.processed.connect(self._on_processed)
        worker.finished.connect(self._on_worker_finished)
        worker.finished.connect(worker.deleteLater)
        self._worker = worker
        worker.start()

    def _on_processed(self, success, failed):
        for key in success:
            self._queued.discard(key)
            self.icon_ready.emit(key)
        for key in failed:
            self._queued.discard(key)
            self._failed.add(key)

    def _on_worker_finished(self):
        self._worker = None
        self._start_worker()

    def shutdown(self):
        self._closing = True
        self._queue = []
        self._queued.clear()
        worker = self._worker
        if worker is not None:
            worker.cancel()
            if not worker.wait(2000):
                worker.terminate()
                worker.wait(1000)
        self._worker = None
