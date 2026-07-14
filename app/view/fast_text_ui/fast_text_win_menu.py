"""
Copyright (c) 2026 綦恒智
Email: bmscriptsbox@163.com
SPDX-License-Identifier: AGPL-3.0
"""
from pynput import mouse
from PySide2.QtCore import Qt
from PySide2.QtGui import QIcon, QCursor
from PySide2.QtWidgets import QWidget, QVBoxLayout, QApplication, QListWidgetItem

from xsideui import XListWidget, XDialog, tr

from app.data import ProjectGlobal, ScriptDatabase
from app.utils import BmNotify, BmTools, ParameterManager
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
        for value in ProjectGlobal.SCRIPTS:
            if not value.quick_copy_active:
                continue
            icon = value.icon
            if not icon:
                icon = BmTools.get_language_icon_path(value.language)
            item = QListWidgetItem(QIcon(icon), value.name)
            item.setData(Qt.UserRole, value.id)
            self.scripts_list.addItem(item)

    def on_script_selected(self, item):
        script_id = item.data(Qt.UserRole)

        if not self._clipboard_text:
            BmNotify().show_error_notify(content=tr('Clipboard content is empty'))
            return

        from app.data import ProjectGlobal
        with ProjectGlobal.RUNNING_SCRIPTS_LOCK:
            if script_id in ProjectGlobal.RUNNING_SCRIPTS:
                script_data = ScriptDatabase().get_script_by_id(script_id)
                name = script_data.name if script_data else script_id
                BmNotify().show_warning_notify(f"脚本「{name}」正在运行中，请等待完成")
                return

        # 从数据库获取脚本的输入定义
        script_data = ScriptDatabase().get_script_by_id(script_id)
        inputs = script_data.inputs_schema
        input_data = inputs[-1] if inputs else {}

        # 用标准 JSON 参数文件传递
        json_path = ParameterManager().construct_parameters(
            script_input_data=input_data,
            data=[self._clipboard_text]
        )


        self.run = ExecuteScriptWork(script_id=script_id, script_args=str(json_path))
        self.run.execute_signal.connect(self._execute_notify)
        self.run.start()
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
        """重写show方法，在鼠标位置下沿显示窗口（支持多显示器）"""
        # 获取当前鼠标位置
        cursor_pos = QCursor.pos()

        # 调整窗口位置到鼠标下沿
        # 获取窗口大小
        self.adjustSize()
        window_width = self.width()
        window_height = self.height()

        # 计算窗口位置（鼠标下沿右侧）
        x = cursor_pos.x() + 10  # 鼠标右侧10像素
        y = cursor_pos.y() + 10  # 鼠标下方10像素

        # 获取鼠标所在的屏幕（支持多显示器）
        mouse_screen = QApplication.screenAt(cursor_pos)
        if mouse_screen:
            screen_geometry = mouse_screen.availableGeometry()
        else:
            # 如果找不到鼠标所在的屏幕，使用主屏幕
            screen_geometry = QApplication.primaryScreen().availableGeometry()

        # 检查右边界
        if x + window_width > screen_geometry.right():
            x = screen_geometry.right() - window_width - 10

        # 检查左边界
        if x < screen_geometry.left():
            x = screen_geometry.left() + 10

        # 检查下边界
        if y + window_height > screen_geometry.bottom():
            y = cursor_pos.y() - window_height - 10  # 如果下方空间不够，显示在鼠标上方

        # 检查上边界
        if y < screen_geometry.top():
            y = screen_geometry.top() + 10

        # 设置窗口位置
        self.move(x, y)

        super().show()
        self.raise_()

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
            self.mouse_signals.click_outside.disconnect()
            self.mouse_signals = None

        self.is_listening = False

    def on_click(self, x, y, button, pressed):
        """鼠标点击回调函数"""
        if pressed and button == mouse.Button.left:
            # 检查点击位置是否在widget外部
            if not self.geometry().contains(x, y):
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

