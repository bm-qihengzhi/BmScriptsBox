"""
Copyright (c) 2026 綦恒智
Email: bmscriptsbox@163.com
SPDX-License-Identifier: MIT
SPDX-License-Identifier: LicenseRef-Commons-Clause
"""
import time

from PySide6.QtCore import QObject, Signal
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

            self.press_count = 0
            self._last_press = 0.0
            self._hook_id = None
            self._kb = None

    KEY_ALIASES = {
        'left ctrl': 'ctrl', 'right ctrl': 'ctrl',
        'ctrl left': 'ctrl', 'ctrl right': 'ctrl',
        'ctrl_l': 'ctrl', 'ctrl_r': 'ctrl',
        'left shift': 'shift', 'right shift': 'shift',
        'shift_l': 'shift', 'shift_r': 'shift',
        'left alt': 'alt', 'right alt': 'alt',
        'alt_l': 'alt', 'alt_r': 'alt',
    }

    def start(self):
        """启动监听（幂等）"""
        if self._hook_id is not None:
            return
        import keyboard as kb
        self._kb = kb
        try:
            from app.data import ConfigDatabase
            config = ConfigDatabase().get_all()
            self.target_keys = [str(k).lower() for k in config.get('shortcut_key_rouse', ['f12'])]
        except (AttributeError, Exception) as e:
            BM_LOG.warning(f"读取双击唤醒配置失败，使用默认值: {e}")
        self._hook_id = self._kb.hook(self._on_key_event)
        BM_LOG.error(f"[双击唤醒] 监听已启动, targets={self.target_keys}")

    def _on_key_event(self, event):
        """底层按键回调"""
        if not event.name or event.event_type != self._kb.KEY_UP:
            return
        name = event.name.lower()
        name = self.KEY_ALIASES.get(name, name)
        if name in self.target_keys:
            self._process_click(name)

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
        self._last_press = 0.0

    def _process_click(self, name=""):
        """核心双击判定逻辑"""
        now = time.monotonic()
        last = self._last_press
        interval = (now - last) * 1000.0 if last else None
        if interval is not None and interval < 40:
            return  # 同一物理按键的重复上报，忽略
        if interval is None or interval > self.threshold:
            self.press_count = 1
        else:
            self.press_count += 1
        self._last_press = now

        if self.press_count >= 2:
            self.double_key_triggered.emit()
            BM_LOG.error(f"[双击唤醒] 触发 key={name}")
            self.press_count = 0
            self._last_press = 0.0

    def stop(self):
        if self._kb and self._hook_id is not None:
            self._kb.unhook(self._hook_id)
            self._hook_id = None

    def update_keys(self, new_keys):
        self.target_keys = [str(k).lower() for k in new_keys]
        self.press_count = 0
        self._last_press = 0.0

_double_monitor_instance = None
def get_double_monitor():
    global _double_monitor_instance
    if _double_monitor_instance is None:
        _double_monitor_instance = RouseMonitor()
    return _double_monitor_instance