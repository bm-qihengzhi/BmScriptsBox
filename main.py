"""
Copyright (c) 2026 綦恒智
Email: bmscriptsbox@163.com
SPDX-License-Identifier: AGPL-3.0
"""
import sys
from pathlib import Path

if not getattr(sys, 'frozen', False):
    sys.path.insert(0, str(Path(__file__).parent.absolute()))

# 加载纯 Python 包 zip（减少 Defender 扫描文件数）
_pure_zip = Path(__file__).parent / 'runtime' / 'Lib' / 'site-packages' / '_pure_packages.zip'
if _pure_zip.exists():
    sys.path.insert(0, str(_pure_zip))

from PySide2.QtCore import Qt
from PySide2.QtWidgets import QApplication
from PySide2.QtNetwork import QLocalServer
from app.view.index_ui.index_win_disp import MainView
from app.utils.tools import BmTools


main_window = None

def handle_new_connection(server):
    """当第二个实例尝试启动时触发"""
    socket = server.nextPendingConnection()
    if socket:
        socket.close()
    global main_window
    if main_window:
        if main_window.isMinimized():
            main_window.showNormal()
        main_window.show()
        main_window.raise_()
        main_window.activateWindow()


def main():
    app_id = "BmScriptsBox_Unique_ID"

    # 1. 预检查
    if BmTools.is_already_running(app_id):
        sys.exit(0)

    # 2. 创建应用实例
    QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)
    QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, True)
    app = QApplication(sys.argv)

    # 3.  单例守护
    server = QLocalServer(app)  # 绑定到 app 自动销毁
    if not server.listen(app_id):
        QLocalServer.removeServer(app_id)
        server.listen(app_id)
    server.newConnection.connect(lambda: handle_new_connection(server))

    # 4. 语言/图标设置
    BmTools.set_win32_logo()
    BmTools.set_language()
    app.setQuitOnLastWindowClosed(False)

    # 5. 启动窗口
    global main_window
    main_window = MainView()
    main_window.show()
    sys.exit(app.exec_())





if __name__ == '__main__':
    main()

