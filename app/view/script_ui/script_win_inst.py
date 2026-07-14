"""
Copyright (c) 2026 綦恒智
Email: bmscriptsbox@163.com
SPDX-License-Identifier: AGPL-3.0
"""
from pathlib import Path

from xsideui import XPushButton, XLineEdit, XTextEdit, IconName, XButtonVariant, XColor, XDialog, \
    tr, XCard, XLabel, XTabWidget
from PySide2.QtCore import Qt, Signal, QTimer
from PySide2.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QFileDialog, QApplication, QFormLayout, QGridLayout

from app.utils import BmTools
from app.works.script_work import InstallLocalScriptWork, InstallCloudScriptWork


class InstallScriptWindow(XDialog):
    """
    安装脚本窗口
    """
    success_signal = Signal(dict)

    # 定义不同类型的日志颜色
    LOG_COLORS = {
        "STAGE": "#BB86FC",  # 紫色：核心阶段
        "SUCCESS": "#62BB46",  # 绿色：成功完成
        "ERROR": "#F44336",  # 红色：错误
        "DOWNLOADING": "#00A3E0",  # 蓝色：下载进度
        "INFO": "#d4d4d4"  # 浅灰：普通信息
    }

    def __init__(self, show_local: bool = False, parent=None):
        super().__init__(parent)
        self.git_install_work = None
        self.could_install_work = None
        self.install_work = None
        self.loading = None
        self.install_git = None
        self.btn_local = None
        self.show_local = show_local
        self._setup_ui()
        self.setModal(True)

    def _setup_ui(self):
        self.setMinimumWidth(360)
        self.set_title(tr('Install Script Log'))
        self.set_logo(BmTools.get_logo_path())
        self.hide_maximize_button()

        content_layout = QVBoxLayout()
        content_layout.setContentsMargins(11, 11, 11, 11)
        content_layout.setSpacing(11)

        # 本地安装模块
        if self.show_local:
            content_layout.addWidget(self._create_local_pane())

        # 终端/进度区
        self.terminal = XTextEdit(read_only=True, parent=self)
        self.terminal.setAcceptRichText(True)
        self.terminal.setUndoRedoEnabled(False)
        self.terminal.setPlaceholderText(tr('Waiting for task to start...'))
        self.terminal.setStyleSheet("background-color: #1e1e1e; color: #d4d4d4;")
        self.terminal.setMinimumHeight(260)

        content_layout.addWidget(XLabel(tr('Install Log'), parent=self))
        content_layout.addWidget(self.terminal, 1)

        self.addLayout(content_layout)

    def _create_local_pane(self):
        """本地安装面板"""

        self.tab = XTabWidget()

        # 本地安装
        self.local_pane = QWidget()
        lay = QGridLayout(self.local_pane)
        lay.setContentsMargins(0, 11, 0, 11)
        lay.setSpacing(11)

        self.script_path_input = XLineEdit(placeholder=tr("Quick install via .zip file"))
        self.btn_browse = XPushButton(icon=IconName.FOLDER, variant=XButtonVariant.FILLED, color=XColor.TERTIARY)
        self.btn_local = XPushButton(tr('Install'), variant=XButtonVariant.FILLED)
        self.btn_browse.clicked.connect(self._browse_file)
        self.btn_local.clicked.connect(self.install_local_script)
        lay.addWidget(self.script_path_input,0,0)
        lay.addWidget(self.btn_browse,0,1)
        lay.addWidget(self.btn_local,1,0,1,2)


        # 仓库安装
        self.git_pane = QWidget()
        lay_git = QGridLayout(self.git_pane)
        lay_git.setContentsMargins(0, 11, 0, 11)
        lay_git.setSpacing(11)
        lay_git.addWidget(XLabel(tr('Repo url:：'), parent=self), 0,0)
        self.git_input = XLineEdit(placeholder=tr("GitHub repo URL only (HTTPS)"))
        lay_git.addWidget(self.git_input, 0 , 1, 1, 2)
        lay_git.addWidget(XLabel(tr('Repo branch:'), parent=self), 1, 0)
        self.branch_input = XLineEdit(placeholder=tr("default to main"))
        lay_git.addWidget(self.branch_input, 1, 1)
        self.install_git = XPushButton(tr('Install'), variant=XButtonVariant.FILLED)
        self.install_git.clicked.connect(self.install_git_script)
        lay_git.addWidget(self.install_git, 1, 2)

        self.tab.addTab(self.local_pane, '从本地安装')
        self.tab.addTab(self.git_pane, '从仓库安装')
        return self.tab

    def _browse_file(self):
        """浏览选择脚本文件"""
        dialog = QFileDialog(self)
        dialog.setFileMode(QFileDialog.ExistingFile)
        dialog.setNameFilter("Python Files (*.zip)")
        dialog.setWindowModality(Qt.WindowModal)

        if dialog.exec_():
            self.script_path_input.setText(dialog.selectedFiles()[0])

    def install_git_script(self):
        """从仓库安装脚本"""
        from app.works.script_work import InstallGitScriptWork
        git_url = self.git_input.text().strip()
        branch = self.branch_input.text().strip() or "main"
        if not git_url:
            self.terminal.append('错误：未填写仓库地址')
            return
        if not git_url.startswith("https"):
            self.terminal.append('错误：只支持https开头的仓库地址')
            return
        if not 'github.com' in git_url:
            self.terminal.append('错误：只支持GitHub仓库')
            return

        self.install_git.set_loading(True)
        self.terminal.clear()
        self.append_styled_log("准备从仓库安装脚本...", "STAGE")
        self.git_install_work = InstallGitScriptWork(git_url=git_url,branch=branch)
        self.git_install_work.finished_signal.connect(self._install_complete)
        self.git_install_work.progress_signal.connect(self._install_progress)
        self.git_install_work.start()

        self.terminal.append("正在安装脚本...")
        self.terminal.append("请勿关闭此窗口...")

    def install_cloud_script(self, script_id: str, script_git_url: str, branch: str = 'main'):
        """安装云端脚本"""
        self.terminal.clear()
        self.append_styled_log("准备从脚本库安装脚本...", "STAGE")
        self.could_install_work = InstallCloudScriptWork(script_id=script_id, script_git_url=script_git_url,
                                                         branch=branch)
        self.could_install_work.finished_signal.connect(self._install_complete)
        self.could_install_work.progress_signal.connect(self._install_progress)
        self.could_install_work.start()

        self.terminal.append("正在安装脚本...")
        self.terminal.append("请勿关闭此窗口...")

    def install_local_script(self):
        """安装本地脚本"""
        script_path = self.script_path_input.text().strip()
        if not script_path:
            self.terminal.append('错误：请选择本地脚本文件路径')
            return

        if not Path(script_path).exists():
            self.terminal.append('错误：脚本文件不存在')
            return

        if not script_path.endswith(".zip"):
            self.terminal.append('错误：只支持zip压缩包')
            return
        self.btn_local.set_loading(True)
        self.terminal.clear()
        self.append_styled_log("准备安装本地脚本...", "STAGE")

        self.install_work = InstallLocalScriptWork(script_path)
        self.install_work.progress_signal.connect(self._install_progress)
        self.install_work.finished_signal.connect(self._install_complete)
        self.install_work.start()

        self.terminal.append("正在安装脚本...")
        self.terminal.append("请勿关闭此窗口...")

    def _install_progress(self, progress: dict):
        """
        安装进度回调
        期待格式: {'status': True, 'msg': '...', 'level': 'STAGE'}
        """
        msg = progress.get('msg', '')

        # 智能判定 Level (如果你在 Work 类里没传 level)
        level = "INFO"
        if "完成" in msg or "成功" in msg or "Downloaded" in msg:
            level = "SUCCESS"
        elif "开始" in msg or "正在" in msg:
            level = "STAGE"
        elif "进度:" in msg or "Downloading" in msg or "Progress" in msg:
            level = "DOWNLOADING"
        elif "失败" in msg:
            level = "ERROR"

        self.append_styled_log(msg, level)

    def _install_complete(self, callback_data: dict):
        """安装完成回调"""
        if self.install_git:
            self.install_git.set_loading(False)
        if self.btn_local:
            self.btn_local.set_loading(False)
        if callback_data["status"]:
            msg = callback_data.get("msg", tr("Installation Successful"))
            self.append_styled_log(msg, "SUCCESS")
            self.append_styled_log(tr("安装窗口将于三秒后自动关闭..."), "INFO")

            self.success_signal.emit({"state": True, "message": "OK"})
            QTimer.singleShot(3000, self.close)
        else:
            error_msg = callback_data.get("msg", tr("Unknown Error"))
            self.append_styled_log(f"{tr('Installation Failed')}: {error_msg}", "ERROR")
            self.success_signal.emit({"state": False, "message": "Failed"})

    def append_styled_log(self, text: str, color_key: str = "INFO"):
        """带 HTML 样式的日志追加（支持同行刷新）"""
        color = self.LOG_COLORS.get(color_key, "#d4d4d4")

        # 根据内容判定图标
        icon = ""
        if color_key == "STAGE":
            icon = "🚀 "
        elif color_key == "SUCCESS":
            icon = "✅ "
        elif color_key == "ERROR":
            icon = "❌ "
        elif color_key == "DOWNLOADING":
            icon = "📥 "

        html = f'<div style="color: {color}; margin-bottom: 2px;">{icon}{text}</div>'

        # 获取当前光标
        cursor = self.terminal.textCursor()

        # 检查是否是下载进度
        if "进度:" in text:
            # 移到文档末尾
            cursor.movePosition(cursor.End)
            cursor.movePosition(cursor.StartOfBlock)
            cursor.movePosition(cursor.EndOfBlock, cursor.KeepAnchor)

            # 检查最后一行是否包含“进度:”
            if "进度:" in cursor.selectedText():
                cursor.insertHtml(html)
            else:
                self.terminal.append(html)
        else:
            self.terminal.append(html)

        self.terminal.moveCursor(self.terminal.textCursor().End)
