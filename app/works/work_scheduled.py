"""
Copyright (c) 2026 綦恒智
Email: bmscriptsbox@163.com
SPDX-License-Identifier: AGPL-3.0
"""
from PySide2.QtCore import QThread

from app.utils import BM_LOG
from app.servers.scheduled_core import DatabaseTaskScheduler


class ScheduledWork(QThread):
    """
    定时工作线程
    """

    def __init__(self):
        super().__init__()
        self.schedule = None
        self._is_running = True

    def run(self):
        try:
            self.schedule = DatabaseTaskScheduler()
            self.schedule.run()
        except Exception as e:
            BM_LOG.error(f"定时任务执行异常: {e}")

    def add_task(self,task_data):
        """更新任务"""
        self.schedule.add_dynamic_task(task_data)

    def remove_task(self, task_id):
        """删除任务"""
        self.schedule.remove_task(task_id)

    def stop_task(self,task_id):
        """停止任务"""
        self.schedule.stop_task(task_id)
    def stop(self):
        """优雅停止调度器"""
        self._is_running = False
        if self.schedule:
            self.schedule.stop()
        self.quit()
        if not self.wait(3000):  # 等待调度器自行退出
            self.terminate()
            self.wait()
        BM_LOG.info("定时任务已停止")