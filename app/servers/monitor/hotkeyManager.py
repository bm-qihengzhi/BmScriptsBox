"""
Copyright (c) 2026 綦恒智
Email: bmscriptsbox@163.com
SPDX-License-Identifier: MIT
SPDX-License-Identifier: LicenseRef-Commons-Clause
"""

import threading

from app.data import ScriptDatabase
from PySide2.QtCore import QObject, Signal, Slot

from app.utils import BM_LOG


class HotkeyManager(QObject):
    hotkey_triggered = Signal(object)
    _instance = None

    def __new__(cls, *args, **kwargs):
        if not cls._instance:
            cls._instance = super(HotkeyManager, cls).__new__(cls)
        return cls._instance

    def __init__(self, parent=None):
        if not hasattr(self, '_initialized'):
            super().__init__(parent)
            self._initialized = True
            self.db = ScriptDatabase()
            self.scripts = []
            self._hotkey_hooks = []
            self._kb = None  # 记录已注册的快捷键
            self._lock = threading.RLock()  # reload/stop 跨线程互斥

    def start(self):
        """显式启动快捷键监听"""
        BM_LOG.info("HotkeyManager 启动中...")
        self.reload_hotkeys()

    @Slot()
    def reload_hotkeys(self):
        """当用户在脚本盒子修改了配置，调用此方法同步（逐脚本容错，单条失败不影响其余）"""
        import keyboard as kb
        with self._lock:
            self._kb = kb
            # 1. 精准清除旧的热键，而不是全部清除
            for hook in self._hotkey_hooks:
                try:
                    kb.remove_hotkey(hook)
                except Exception:
                    pass
            self._hotkey_hooks.clear()

            # 2. 从数据库同步最新配置
            self.scripts = self.db.get_all_scripts()

            # 3. 重新迭代注册：逐脚本容错，坏键只告警不中断
            ok = failed = 0
            for script in self.scripts:
                if script.hotkey and script.hotkey_active:
                    try:
                        hook = kb.add_hotkey(
                            script.hotkey,
                            self._on_triggered,
                            args=(script,)
                        )
                        self._hotkey_hooks.append(hook)  # 保存引用
                        ok += 1
                    except Exception as e:
                        failed += 1
                        BM_LOG.warning(
                            f"热键注册失败 {script.id}/{script.hotkey}: {e}")
            BM_LOG.info(f"快捷键同步完成：成功 {ok} 个，失败 {failed} 个")


    def _on_triggered(self, script_info):
        """
        回调函数。注意：此函数在 keyboard 的独立线程中运行。
        通过 emit 发出信号，Qt 会安全地将其转交给主线程 UI 或执行线程。
        """
        self.hotkey_triggered.emit(script_info)

    def stop(self):
        with self._lock:
            if not self._kb:
                import keyboard as kb
                self._kb = kb
            for hook in self._hotkey_hooks:
                try:
                    self._kb.remove_hotkey(hook)
                except Exception:
                    pass
            self._hotkey_hooks.clear()


_hotkey_manager_instance = None
def get_hotkey_manager():
    global _hotkey_manager_instance
    if _hotkey_manager_instance is None:
        _hotkey_manager_instance = HotkeyManager()
    return _hotkey_manager_instance
if __name__ == '__main__':
    # 在GUI主窗口中
    hotkey_manager = HotkeyManager()
    hotkey_manager.hotkey_triggered.connect(lambda hotkey_info: print(hotkey_info))
    hotkey_manager.start()
