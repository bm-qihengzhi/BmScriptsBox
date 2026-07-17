"""
Copyright (c) 2026 綦恒智
Email: bmscriptsbox@163.com
SPDX-License-Identifier: AGPL-3.0
"""


from PySide2.QtCore import QTimer, Signal
from PySide2.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QApplication, QStackedWidget
from app.utils import BmTools
from xsideui import  XLabel, XPushButton, XProgressBar, XButtonVariant, XSize, tr, XDialog

try:
    from app.cloud.works import UpdateDownLoadTask
except ImportError:
    UpdateDownLoadTask = None



class UpdateWidget(XDialog):
    """软件更新小部件"""
    completed_single = Signal(str)

    def __init__(self, version: str, diff: list, remote_details: dict = None, parent=None):
        super().__init__(parent=parent)
        self.version = version
        self.diff = diff
        self.remote_details = remote_details
        self._setup_ui()
        self._preload_widgets()

    def _setup_ui(self):
        self.setMinimumWidth(260)
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

        if self.parent():
            # 设置模态显示
            self.setModal(True)

    def showEvent(self, event):
        """窗口显示事件"""
        super().showEvent(event)
        if self.parent() and not hasattr(self, '_positioned'):
            self._position_at_parent_bottom_right()

    def _position_at_parent_bottom_right(self):
        """将窗口定位到父窗口右下角"""
        if self.parent():
            parent_geometry = self.parent().geometry()
            self.move(
                parent_geometry.right() - self.width() - 10,
                parent_geometry.bottom() - self.height() - 10
            )

    def _preload_widgets(self):
        """预加载所有页面以确保流畅切换"""
        for i in range(self.stack.count()):
            widget = self.stack.widget(i)
            widget.adjustSize()
            widget.update()

        # 处理一次待处理的事件
        QApplication.processEvents()

    def update_prompt(self):
        content_widget = QWidget()
        layout = QVBoxLayout(content_widget)
        layout.setSpacing(11)
        layout.setContentsMargins(11, 11, 11, 11)
        layout.addWidget(XLabel(tr('Update available. Please install the latest version')))

        btn_layout = QHBoxLayout()
        self.btn_ignore = XPushButton(
            text=tr('Later'),
            variant=XButtonVariant.OUTLINED,
            size=XSize.SMALL,
        )
        self.btn_update = XPushButton(
            text=tr('Update Now'),
            size=XSize.SMALL,
        )
        btn_layout.addStretch()
        btn_layout.addWidget(self.btn_ignore)
        btn_layout.addWidget(self.btn_update)

        layout.addLayout(btn_layout)
        self.stack.addWidget(content_widget)

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
        self.update_task = UpdateDownLoadTask(self.diff, self.remote_details)
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
        if hasattr(self, 'update_task') and self.update_task.isRunning():
            self.update_task.terminate()  # 或者更优雅的 stop 逻辑
            self.update_task.wait()
        super().closeEvent(event)


if __name__ == '__main__':
    app = QApplication([])
    win = UpdateWidget('1.1', [])
    win.show()
    app.exec_()
