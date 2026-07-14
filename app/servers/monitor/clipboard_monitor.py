"""
Copyright (c) 2026 綦恒智
Email: bmscriptsbox@163.com
SPDX-License-Identifier: AGPL-3.0
"""
import time
from threading import Lock
from PySide2.QtCore import QObject, Signal
from app.utils import BM_LOG
class ShortcutState:
    IDLE = 0
    CTRL_PRESSED = 1
    FIRST_C_PRESSED = 2
    WAITING_SECOND_C = 3


class ClipboardMonitor(QObject):
    """
    双击 Ctrl+C 检测器：用于提取剪切板文本
    单例模式，基于 keyboard 钩子实现，无需手动开启 QThread
    """
    # 信号：成功提取文本时发射 (文本内容, 错误信息)
    triggered = Signal(str, str)

    _instance = None

    def __new__(cls, *args, **kwargs):
        if not cls._instance:
            cls._instance = super(ClipboardMonitor, cls).__new__(cls)
        return cls._instance

    def __init__(self, max_interval=0.5, parent=None):
        if not hasattr(self, '_initialized'):
            super().__init__(parent)
            self._initialized = True

            # 配置参数
            self.max_interval = max_interval  # 两次 C 按下的最大间隔
            self.cleanup_interval = 10.0  # 状态自动重置时间

            # 内部状态
            self.state = ShortcutState.IDLE
            self.last_event_time = 0
            self.last_cleanup_time = time.time()
            self.lock = Lock()
            self.hook_id = None

            # 键名定义（适配不同操作系统的 keyboard 键名）
            self.ctrl_keys = {'ctrl', 'ctrl left', 'ctrl right', 'ctrl_l', 'ctrl_r'}
            self.c_keys = {'c', 'C'}

    def start(self):
        """启动全局钩子监听"""
        import keyboard
        self._kb = keyboard
        self.hook_id = self._kb.hook(self.handle_key_event)
        if self.hook_id is None:
            try:
                self.hook_id = self._kb.hook(self.handle_key_event)
            except Exception as e:
                BM_LOG.error(f"启动剪切板监测失败: {e}")


    def stop(self):
        """停止监听并重置状态"""
        if self.hook_id is not None and self._kb:
            self._kb.unhook(self.hook_id)
            self.hook_id = None
            self.state = ShortcutState.IDLE
            print("剪切板双击检测服务已停止")

    def handle_key_event(self, event):
        """键盘事件回调（状态机核心逻辑）"""
        try:
            self._cleanup_old_state()

            current_time = time.time()
            key_name = event.name.lower() if event.name else ""
            event_type = event.event_type  # 'down' 或 'up'

            with self.lock:
                # --- 状态机切换逻辑 ---
                if self.state == ShortcutState.IDLE:
                    if key_name in self.ctrl_keys and event_type == 'down':
                        self.state = ShortcutState.CTRL_PRESSED
                        self.last_event_time = current_time

                elif self.state == ShortcutState.CTRL_PRESSED:
                    if key_name in self.c_keys and event_type == 'down':
                        self.state = ShortcutState.FIRST_C_PRESSED
                        self.last_event_time = current_time
                    elif key_name in self.ctrl_keys and event_type == 'up':
                        self.state = ShortcutState.IDLE

                elif self.state == ShortcutState.FIRST_C_PRESSED:
                    # 如果按下第二个 C
                    if key_name in self.c_keys and event_type == 'down':
                        if current_time - self.last_event_time <= self.max_interval:
                            self.state = ShortcutState.WAITING_SECOND_C
                            self.last_event_time = current_time
                        else:
                            # 间隔太长，重新计时
                            self.state = ShortcutState.CTRL_PRESSED
                            self.last_event_time = current_time
                    elif current_time - self.last_event_time > self.max_interval:
                        self.state = ShortcutState.IDLE

                elif self.state == ShortcutState.WAITING_SECOND_C:
                    # 第二个 C 弹起，且此时 Ctrl 依然处于按下状态
                    if key_name in self.c_keys and event_type == 'up':
                        if self._kb and self._kb.is_pressed('ctrl'):
                            self._on_shortcut_triggered()
                        self.state = ShortcutState.IDLE
                    elif current_time - self.last_event_time > self.max_interval:
                        self.state = ShortcutState.IDLE

        except Exception as e:
            # 遇到异常强制重置，防止键盘死锁
            self.state = ShortcutState.IDLE

    def _on_shortcut_triggered(self):
        """触发后的业务处理"""
        import pyperclip
        time.sleep(0.15)

        try:
            text = pyperclip.paste()
            if text and text.strip():
                self.triggered.emit(text.strip(), "")
            else:
                self.triggered.emit("", "剪切板内容为空")
        except Exception as e:
            self.triggered.emit("", f"读取剪切板出错: {str(e)}")

    def _cleanup_old_state(self):
        """定期检查并清理卡住的状态"""
        current_time = time.time()
        if current_time - self.last_cleanup_time > self.cleanup_interval:
            with self.lock:
                if self.state != ShortcutState.IDLE:
                    # 如果状态停留在某个环节超过 3 倍阈值时间，强制重置
                    if current_time - self.last_event_time > self.max_interval * 3:
                        self.state = ShortcutState.IDLE
            self.last_cleanup_time = current_time

    def __del__(self):
        self.stop()

_clipboard_monitor_instance = None
def get_clipboard_monitor():
    global _clipboard_monitor_instance
    if _clipboard_monitor_instance is None:
        _clipboard_monitor_instance = ClipboardMonitor()
    return _clipboard_monitor_instance