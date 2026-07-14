"""
Copyright (c) 2026 綦恒智
Email: bmscriptsbox@163.com
SPDX-License-Identifier: AGPL-3.0
"""
from PySide2.QtCore import QObject, Signal, QElapsedTimer, Slot
from app.utils import BM_LOG

class RouseMonitor(QObject):
    """
    专门负责双击特定按键（如 F12）唤醒主程序的监听器
    """
    double_key_triggered = Signal()
    _instance = None

    def __new__(cls, *args, **kwargs):
        if not cls._instance:
            cls._instance = super(RouseMonitor, cls).__new__(cls)
        return cls._instance

    def __init__(self, threshold=300):
        if not hasattr(self, '_initialized'):
            super().__init__()
            self._initialized = True

            self.threshold = threshold  # 双击判定阈值（毫秒）
            self.target_keys = ['f12']  # 默认值

            # 使用 QElapsedTimer 记录时间差，无需事件循环
            self.timer = QElapsedTimer()
            self.press_count = 0
            self._kb = None

    def start(self):
        """启动监听"""
        import keyboard as kb
        self._kb = kb
        try:
            from app.data import ConfigDatabase
            config = ConfigDatabase().get_all()
            self.target_keys = [k.lower() for k in config.get('shortcut_key_rouse', ['f12'])]
        except (AttributeError, Exception) as e:
            BM_LOG.warning(f"读取双击唤醒配置失败，使用默认值: {e}")
        self._kb.hook(self._on_key_event)

    def _on_key_event(self, event):
        """底层按键回调"""
        if event.name.lower() in self.target_keys:
            if event.event_type == self._kb.KEY_UP:
                self._process_click()

    def update_configs(self, new_keys=None, new_threshold=None):
        """
        动态更新配置：
        :param new_keys: 列表类型，如 ['f12'] 或 ['ctrl']
        :param new_threshold: 整数类型，单位毫秒
        """
        if new_keys is not None:
            # 统一转小写，防止匹配失败
            self.target_keys = [str(k).lower() for k in new_keys]

        if new_threshold is not None:
            self.threshold = new_threshold

        # 状态重置，防止修改过程中产生误触发
        self.press_count = 0
        self.timer.invalidate()

    def _process_click(self):
        """核心双击判定逻辑"""
        # 如果是第一次按，或者距离上次按键超过了阈值，重置计数
        if not self.timer.isValid() or self.timer.elapsed() > self.threshold:
            self.press_count = 1
            self.timer.start()
        else:
            # 在阈值时间内再次按下
            self.press_count += 1

        if self.press_count >= 2:
            self.double_key_triggered.emit()
            self.press_count = 0  # 触发后重置
            self.timer.invalidate()  # 使计时器失效

    def stop(self):
        if self._kb:
            self._kb.unhook(self._on_key_event)

    def update_keys(self, new_keys):
        self.target_keys = [k.lower() for k in new_keys]
        self.press_count = 0

_double_monitor_instance = None
def get_double_monitor():
    global _double_monitor_instance
    if _double_monitor_instance is None:
        _double_monitor_instance = RouseMonitor()
    return _double_monitor_instance