"""
Copyright (c) 2026 綦恒智
Email: bmscriptsbox@163.com
SPDX-License-Identifier: MIT
SPDX-License-Identifier: LicenseRef-Commons-Clause
"""
from pynput import mouse
from PySide2.QtCore import Qt
from PySide2.QtGui import QIcon, QCursor
from PySide2.QtWidgets import QWidget, QVBoxLayout, QApplication, QListWidgetItem

from xsideui import XListWidget, XDialog, tr

from app.data import ProjectGlobal
from app.utils import BmNotify, BmTools
from app.works import ExecuteScriptWork
from .fast_text_signal import MouseSignals


class FastTextMenu(XDialog):
    """超级复制快捷键菜单"""

    def __init__(self, parent=None):
        super(FastTextMenu, self).__init__(parent)
        # 初始化变量
        self.mouse_signals = None
        self.mouse_listener = None
        self.is_listening = False
        self._clipboard_text = ""
        self.setWindowFlag(Qt.WindowStaysOnTopHint, True)  # 设置窗口永远在最上层
        self.setAttribute(Qt.WA_ShowWithoutActivating)
        self._setup_ui()

    def _setup_ui(self):
        self.set_title('超级复制菜单')
        self.set_logo(BmTools.get_logo_path())
        self.hide_title_bar()
        self.setMaximumWidth(160)
        self.setMinimumHeight(300)

        menu_widget = QWidget()
        layout = QVBoxLayout(menu_widget)

        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        self.scripts_list = XListWidget(show_border=False)
        self.scripts_list.itemClicked.connect(self.on_script_selected)
        layout.addWidget(self.scripts_list)
        self.addWidget(menu_widget)

    def setup_list_items(self):
        # 清空列表
        self.scripts_list.clear()
        for value in (ProjectGlobal.safe_get('SCRIPTS') or []):
            if not value.quick_copy_active:
                continue
            icon = value.icon
            if not icon:
                icon = BmTools.get_language_icon_path(value.language)
            item = QListWidgetItem(QIcon(icon), value.name)
            item.setData(Qt.UserRole, value.id)
            self.scripts_list.addItem(item)

    def on_script_selected(self, item):
        from app.servers.scripts import (
            ScriptLaunchService, ScriptBusyError, ScriptNotFoundError)
        script_id = item.data(Qt.UserRole)

        if not self._clipboard_text:
            BmNotify().show_error_notify(content=tr('Clipboard content is empty'))
            return

        # 先原子占用 + 构造参数（含可选参数表单），失败/取消一律已自动清理
        try:
            ctx = ScriptLaunchService.prepare(
                script_id, data=[self._clipboard_text],
                invoke_mode='manual', allow_params_form=True,
                reserve_first=True, parent=self, source='quick_copy')
        except ScriptBusyError:
            BmNotify().show_warning_notify(tr('脚本正在运行中，请等待完成'))
            return
        except ScriptNotFoundError:
            BmNotify().show_error_notify(content=tr('脚本不存在或已被卸载'))
            self.hide_window()
            return

        if ctx is None:  # 参数表单取消
            self.hide_window()
            return

        try:
            self.run = ExecuteScriptWork(ctx)
            self.run.execute_signal.connect(self._execute_notify)
            self.run.start()
        except Exception:
            ScriptLaunchService.cleanup(ctx)
            raise
        self.hide_window()

    def _execute_notify(self, state):
        if state:
            BmNotify().show_info_notify(content=tr('Executing Script'))
        else:
            BmNotify().show_error_notify(content=tr('Executing Failed'))

    def set_clipboard_text(self, text):
        self._clipboard_text = text

    def show_window(self):
        """显示窗口"""
        self.show()

    def show(self):
        """重写show方法：先让基类显示（XDialog 会居中），再纠正到鼠标位置"""
        self.adjustSize()
        super().show()                 # 触发 XDialog.showEvent 的居中逻辑
        self._position_near_cursor()   # 基类居中之后覆盖为鼠标位置
        self.raise_()

    def _position_near_cursor(self):
        """把窗口定位到鼠标右下沿（支持多显示器、越界回退）"""
        cursor_pos = QCursor.pos()
        window_width = self.width()
        window_height = self.height()

        # 鼠标所在的屏幕（支持多显示器）
        mouse_screen = QApplication.screenAt(cursor_pos) or QApplication.primaryScreen()
        screen_geometry = mouse_screen.availableGeometry()

        # 鼠标下沿右侧
        x = cursor_pos.x() + 10
        y = cursor_pos.y() + 10

        # 右边界
        if x + window_width > screen_geometry.right():
            x = screen_geometry.right() - window_width - 10
        # 左边界
        if x < screen_geometry.left():
            x = screen_geometry.left() + 10
        # 下边界：下方空间不够则显示在鼠标上方
        if y + window_height > screen_geometry.bottom():
            y = cursor_pos.y() - window_height - 10
        # 上边界
        if y < screen_geometry.top():
            y = screen_geometry.top() + 10

        self.move(x, y)

    def showEvent(self, event):
        """窗口显示时启动鼠标监听"""
        super().showEvent(event)
        self.start_mouse_listener()

    def hideEvent(self, event):
        """窗口隐藏时停止鼠标监听"""
        super().hideEvent(event)
        self.stop_mouse_listener()

    def start_mouse_listener(self):
        """启动鼠标监听"""
        if self.is_listening:
            return

        # 创建信号对象
        self.mouse_signals = MouseSignals()
        self.mouse_signals.click_outside.connect(self.hide)

        # 启动鼠标监听
        self.mouse_listener = mouse.Listener(on_click=self.on_click)
        self.mouse_listener.start()
        self.is_listening = True

    def stop_mouse_listener(self):
        """停止鼠标监听"""
        if not self.is_listening:
            return

        if self.mouse_listener:
            self.mouse_listener.stop()
            self.mouse_listener = None

        if self.mouse_signals:
            try:
                self.mouse_signals.click_outside.disconnect()
            except Exception:
                pass
            self.mouse_signals = None

        self.is_listening = False

    def on_click(self, x, y, button, pressed):
        """鼠标点击回调函数"""
        if pressed and button == mouse.Button.left:
            # 检查点击位置是否在widget外部（含窗口边框，避免坐标错位）
            if not self.frameGeometry().contains(x, y):
                # 通过信号触发隐藏，确保在UI线程中执行
                if self.mouse_signals:
                    self.mouse_signals.click_outside.emit()

    def closeEvent(self, event):
        """窗口关闭时停止监听"""
        self.stop_mouse_listener()
        super().closeEvent(event)

    def hide_window(self):
        """隐藏窗口并移除事件过滤器"""
        QApplication.instance().removeEventFilter(self)
        self.hide()

