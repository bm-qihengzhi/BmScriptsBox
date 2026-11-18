"""
Copyright (c) 2026 綦恒智
Email: bmscriptsbox@163.com
SPDX-License-Identifier: MIT
SPDX-License-Identifier: LicenseRef-Commons-Clause
"""


import webbrowser

from PySide6.QtCore import QTimer, Signal, QPoint, QRect, Qt
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QApplication,
                               QStackedWidget, QFrame)
from app.utils import BmTools
from xsideui import (XLabel, XPushButton, XProgressBar, XButtonVariant, XSize,
                     tr, XDialog, XColor, XScrollArea)

try:
    from app.cloud.works import UpdateDownLoadTask
except ImportError:
    UpdateDownLoadTask = None



class UpdateWidget(XDialog):
    """软件更新小部件"""
    completed_single = Signal(str)

    def __init__(self, version: str, diff: list, remote_details: dict = None,
                 changelog=None, local_version: str = None, removed: list = None,
                 parent=None):
        super().__init__(parent=parent)
        self.version = version
        self.diff = diff
        self.remote_details = remote_details
        self._local_version = local_version
        self._removed = list(removed or [])
        self._summary, self._groups = self._normalize_changelog(changelog)
        self._notes_url = ""
        if isinstance(changelog, dict):
            url = changelog.get("url")
            if isinstance(url, str) and url.strip():
                self._notes_url = url.strip()
        self._setup_ui()
        self._preload_widgets()

    @staticmethod
    def _normalize_changelog(changelog):
        """把云端 changelog 归一成 (summary, [(title, [items])])。

        支持对象（summary + groups）与纯字符串（按行拆分）两种写法；
        任何脏数据都降级为空，保证弹窗不会因为字段异常打不开。
        """
        if not changelog:
            return None, []

        if isinstance(changelog, str):
            items = [line.strip() for line in changelog.splitlines() if line.strip()]
            return None, [(None, items)] if items else []

        if not isinstance(changelog, dict):
            return None, []

        summary = changelog.get("summary")
        if not isinstance(summary, str) or not summary.strip():
            summary = None

        groups = []
        raw_groups = changelog.get("groups")
        if isinstance(raw_groups, list):
            for group in raw_groups:
                if not isinstance(group, dict):
                    continue
                items = [str(item).strip() for item in (group.get("items") or [])
                         if str(item).strip()]
                if not items:
                    continue
                title = group.get("title")
                title = title.strip() if isinstance(title, str) and title.strip() else None
                groups.append((title, items))

        return summary, groups

    @property
    def _has_notes(self) -> bool:
        return bool(self._groups or self._summary)

    def _setup_ui(self):
        # 有更新内容时放宽窗口；无内容保持原来的紧凑形态
        self.setMinimumWidth(380 if self._has_notes else 260)
        if self._has_notes:
            self.setMaximumWidth(520)
        self.hide_title_bar()
        self.hide_maximize_button()
        self.hide_minimize_button()
        self.hide_theme_button()
        self.set_logo(str(BmTools.get_resources_path() /'imgs'/ 'update.svg'))
        self.set_title(tr('New Version Available'))

        self.stack = QStackedWidget()
        self.addWidget(self.stack)
        self.update_prompt()
        self.update_tails()
        self.stack.setCurrentIndex(0)
        self._single()

        self.setModal(False)
        self.setWindowModality(Qt.NonModal)

    def showEvent(self, event):
        """窗口显示事件"""
        super().showEvent(event)
        if self.parent() and not hasattr(self, '_positioned'):
            self._position_at_parent_bottom_right()

    def _position_at_parent_bottom_right(self):
        """将可见内容区定位到父窗口右下角"""
        parent = self.parent()
        if not parent:
            return
        parent_rect = QRect(parent.mapToGlobal(QPoint(0, 0)), parent.size())
        visible = self.content_global_rect()
        target_x = parent_rect.right() - visible.width() - 10
        target_y = parent_rect.bottom() - visible.height() - 10

        # 窗口加宽后父窗口贴屏幕边缘时可能出屏，钳制到可用区域内
        screen = self.screen() or QApplication.primaryScreen()
        if screen is not None:
            avail = screen.availableGeometry()
            target_x = max(avail.left(), min(target_x, avail.right() - visible.width() + 1))
            target_y = max(avail.top(), min(target_y, avail.bottom() - visible.height() + 1))

        self.move(self.x() + target_x - visible.left(),
                  self.y() + target_y - visible.top())

    def _preload_widgets(self):
        """预加载所有页面以确保流畅切换"""
        for i in range(self.stack.count()):
            widget = self.stack.widget(i)
            widget.adjustSize()
            widget.update()

    def update_prompt(self):
        content_widget = QWidget()
        layout = QVBoxLayout(content_widget)
        layout.setSpacing(11)
        layout.setContentsMargins(11, 20, 11, 11)

        if self._has_notes:
            self._build_notes_section(layout)
        else:
            layout.addWidget(XLabel(tr('Update available. Please install the latest version')))

        btn_layout = QHBoxLayout()
        self.btn_ignore = XPushButton(
            text=tr('Later'),
            variant=XButtonVariant.OUTLINED,
            size=XSize.SMALL,
            color=XColor.TERTIARY,
        )
        self.btn_update = XPushButton(
            variant=XButtonVariant.FILLED,
            text=tr('Update Now'),
            size=XSize.SMALL,
        )
        btn_layout.addStretch()
        btn_layout.addWidget(self.btn_ignore)
        btn_layout.addWidget(self.btn_update)

        layout.addLayout(btn_layout)
        self.stack.addWidget(content_widget)

    def _build_notes_section(self, layout: QVBoxLayout):
        """版本行 + 概述 + 分组条目（可滚动） + 完整说明链接"""
        version_text = (f"{self._local_version} → {self.version}"
                        if self._local_version and self.version
                        else str(self.version or ""))
        if version_text:
            layout.addWidget(XLabel(version_text, style=XLabel.Style.SECONDARY))

        if self._summary:
            layout.addWidget(XLabel(self._summary, word_wrap=True))

        if self._groups:
            layout.addWidget(self._build_groups_area())

        if self._notes_url:
            link = XPushButton(
                text=tr('View full release notes'),
                variant=XButtonVariant.TEXT,
                size=XSize.SMALL,
                color=XColor.PRIMARY,
            )
            link.clicked.connect(lambda: webbrowser.open_new_tab(self._notes_url))
            layout.addWidget(link)

    def _build_groups_area(self) -> QWidget:
        """把分组条目塞进固定最大高度的滚动区，内容再多也不撑破窗口"""
        inner = QWidget()
        inner_layout = QVBoxLayout(inner)
        inner_layout.setContentsMargins(0, 0, 0, 0)
        inner_layout.setSpacing(6)

        for title, items in self._groups:
            if title:
                inner_layout.addWidget(XLabel(title, style=XLabel.Style.H4))
            for item in items:
                inner_layout.addWidget(XLabel("· " + item, word_wrap=True))
        inner_layout.addStretch()

        scroll = XScrollArea()
        scroll.setWidgetResizable(True)
        scroll.set_scrollbar_visible(True, False)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setWidget(inner)
        scroll.setMaximumHeight(240)
        return scroll

    def update_tails(self):
        tails_widget = QWidget()
        tails_layout = QVBoxLayout(tails_widget)
        tails_layout.setSpacing(11)
        tails_layout.setContentsMargins(11, 11, 11, 11)

        # 进度条从0开始
        self.progress_bar = XProgressBar(height=16, value=0)
        self.progress_label = XLabel(tr('Restart after download'))
        tails_layout.addWidget(self.progress_label)
        tails_layout.addWidget(self.progress_bar)
        tails_layout.addStretch()
        self.stack.addWidget(tails_widget)

    def _single(self):
        self.btn_update.clicked.connect(self.execute_update)
        self.btn_ignore.clicked.connect(self.close)

    def execute_update(self):
        """执行更新"""
        # 先重置进度条
        self.progress_bar.setValue(0)
        # 延迟切换确保UI响应
        QTimer.singleShot(10, self._switch_to_update_view)

    def _switch_to_update_view(self):
        """切换到更新视图"""
        self.stack.setCurrentIndex(1)
        # 立即开始更新进度
        self._start_download()

    def _start_download(self):
        """执行下载"""
        self.update_task = UpdateDownLoadTask(
            self.diff, self.remote_details, self._removed)
        self.update_task.progressed.connect(self.update_details)
        self.update_task.completed.connect(self.download_complete)
        self.update_task.start()

    def update_details(self, value):
        """更新下载进度"""
        self.progress_bar.setValue(value)

    def download_complete(self, paras: dict):
        """下载完成"""
        success = paras.get('success', False)
        save_dir = paras.get('save_dir', '')
        if success:
            self.completed_single.emit(save_dir)
            QTimer.singleShot(100, self.close)
        else:
            self.progress_label.setText(tr('Update failed'))

    def closeEvent(self, event):
        """确保窗口关闭时停止下载任务"""
        task = getattr(self, 'update_task', None)
        if task is not None and task.isRunning():
            task.terminate()
            task.wait(1000)
        super().closeEvent(event)


if __name__ == '__main__':
    app = QApplication([])
    win = UpdateWidget('1.1', [])
    win.show()
    app.exec()
