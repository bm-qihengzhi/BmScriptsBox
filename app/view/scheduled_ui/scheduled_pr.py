"""
Copyright (c) 2026 綦恒智
Email: bmscriptsbox@163.com
SPDX-License-Identifier: AGPL-3.0
"""
from PySide2.QtCore import QTimer

from app.data import ProjectGlobal
from app.data.database import TaskDatabase
from app.works.work_scheduled import ScheduledWork
from app.utils import BM_LOG


class ScheduledPresenter:
    """定时任务逻辑处理"""

    def __init__(self, view):
        self.scheduled_work = None
        self.view = view
        self.tasks_data = []
        QTimer.singleShot(100, self._init_scheduled_work)

    def _init_scheduled_work(self):
        if not self.scheduled_work:
            self.scheduled_work = ScheduledWork()
        self.scheduled_work.start()

    def add_new_timing_work(self, task_data):
        """在调配线程中增加新的任务"""
        if not self.scheduled_work:
            return
        self.scheduled_work.add_task(task_data)

    def get_tasks(self):
        """获取所有任务、并展示在列表中"""
        tasks = TaskDatabase.get_all_tasks()
        ProjectGlobal.Task = tasks
        self.view.update_tasks(tasks)

    def on_switch_clicked(self, task_id, state):
        """修改任务状态"""
        if task_id:
            TaskDatabase.update_task(task_id, {"is_active": state})
            if state:
                self.scheduled_work.add_task(self.get_task(task_id))
            else:
                self.scheduled_work.stop_task(task_id)
        self.get_tasks()

    def edit_task(self, task_data):
        """编辑任务"""
        self.scheduled_work.stop_task(task_data.get('task_id'))
        self.scheduled_work.add_task(task_data)
        self.get_tasks()

    def get_task(self, db_id: int):
        """根据任务名称获取任务信息"""
        return TaskDatabase().get_task(db_id)

    def delete_task(self, db_id: int):
        """删除定时任务"""
        try:
            if not self.scheduled_work:
                return
            self.scheduled_work.remove_task(db_id)
            self.get_tasks()
        except Exception as e:
            BM_LOG.error(f"删除定时任务失败：{e}")
