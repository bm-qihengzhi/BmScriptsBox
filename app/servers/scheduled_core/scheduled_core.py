"""
Copyright (c) 2026 綦恒智
Email: bmscriptsbox@163.com
SPDX-License-Identifier: AGPL-3.0
"""
import random
import threading
from concurrent.futures import ThreadPoolExecutor
import schedule

from app.data.database import TaskDatabase, ScriptDatabase
from app.utils import BM_LOG, ParameterManager
from app.servers.scripts import ScriptRunner


class DatabaseTaskScheduler:
    def __init__(self):
        self.scheduled_jobs = {}
        self.active_timers = {}
        self.running_tasks = {}
        self.thread_pool = ThreadPoolExecutor(max_workers=10)
        self._stop_event = threading.Event()

    def execute_script(self, script_id,  parameters:list):
        """执行外部脚本，路径参数使用 ParameterManager 构建 JSON"""
        from app.data import ProjectGlobal
        with ProjectGlobal.RUNNING_SCRIPTS_LOCK:
            ProjectGlobal.RUNNING_SCRIPTS.add(script_id)
        try:
            if not isinstance(parameters, list):
                parameters = [parameters] if parameters else []
            inputs_schema = ScriptDatabase().get_script_by_id(script_id).inputs_schema
            input_data = inputs_schema[-1] if inputs_schema else {}

            json_path = ParameterManager().construct_parameters(input_data, parameters)
            param_str = str(json_path)
            return ScriptRunner().run_script(script_id=script_id, param=param_str)

        except Exception as e:
            BM_LOG.error(f"执行脚本异常 {script_id}: {e}")
            return False
        finally:
            with ProjectGlobal.RUNNING_SCRIPTS_LOCK:
                ProjectGlobal.RUNNING_SCRIPTS.discard(script_id)

    def schedule_fixed_interval_task(self, task_id, script_id, interval_minutes, parameters:list):
        """1. 固定间隔时间运行（分钟）"""

        print(parameters)
        def fixed_interval_wrapper():
            try:
                self.thread_pool.submit(self.execute_script, script_id, parameters)
            except Exception as e:
                BM_LOG.error(f"[定时任务] wrapper 异常: {e}")

        interval_seconds = interval_minutes * 60
        if interval_seconds <= 0:
            interval_seconds = 5
        job = schedule.every(interval_seconds).seconds.do(fixed_interval_wrapper)
        self.scheduled_jobs[task_id] = job
        BM_LOG.info(f"已安排固定间隔任务 {task_id}: 每{interval_minutes}分钟执行一次, job={job}")

    def schedule_random_interval_task(self, task_id, script_id, min_interval_minutes,
                                      max_interval_minutes, parameters:list):
        """2. 随机间隔时间运行（最小间隔、最大间隔、分钟）"""

        if min_interval_minutes <= 0:
            min_interval_minutes = 1
        if max_interval_minutes <= 0:
            max_interval_minutes = 1
        if min_interval_minutes > max_interval_minutes:
            min_interval_minutes, max_interval_minutes = max_interval_minutes, min_interval_minutes

        def random_interval_wrapper():
            self.thread_pool.submit(self.execute_script, script_id, parameters)

            next_interval_minutes = random.randint(min_interval_minutes, max_interval_minutes)
            next_interval_seconds = next_interval_minutes * 60
            schedule.cancel_job(self.scheduled_jobs[task_id])
            job = schedule.every(next_interval_seconds).seconds.do(random_interval_wrapper)
            self.scheduled_jobs[task_id] = job

        initial_interval_minutes = random.randint(min_interval_minutes, max_interval_minutes)
        initial_interval_seconds = initial_interval_minutes * 60
        job = schedule.every(initial_interval_seconds).seconds.do(random_interval_wrapper)
        self.scheduled_jobs[task_id] = job

    def schedule_countdown_task(self, task_id, script_id, delay_minutes, parameters:list):
        """3. 倒计时运行（分钟）"""

        def countdown_wrapper():
            self.thread_pool.submit(self.execute_script, script_id, parameters)
            if task_id in self.active_timers:
                del self.active_timers[task_id]

        delay_seconds = delay_minutes * 60
        timer = threading.Timer(delay_seconds, countdown_wrapper)
        timer.daemon = True
        timer.start()
        self.active_timers[task_id] = timer

    def schedule_daily_task(self, task_id, script_id, scheduled_time, parameters:list):
        """4. 每天固定时间运行（每天15:30）"""

        def daily_wrapper():
            self.thread_pool.submit(self.execute_script, script_id, parameters)

        job = schedule.every().day.at(scheduled_time).do(daily_wrapper)
        self.scheduled_jobs[task_id] = job
        BM_LOG.info(f"已安排每日任务 {task_id}: 每天{scheduled_time}执行")

    def schedule_weekly_task(self, task_id, script_id, weekday, scheduled_time, parameters:list):
        """5. 每周固定时间运行（例周三16:40分运行）"""

        def weekly_wrapper():
            self.thread_pool.submit(self.execute_script, script_id, parameters)

        weekday_map = {
            "monday": "monday", "tuesday": "tuesday", "wednesday": "wednesday",
            "thursday": "thursday", "friday": "friday", "saturday": "saturday", "sunday": "sunday",
            "周一": "monday", "周二": "tuesday", "周三": "wednesday", "周四": "thursday",
            "周五": "friday", "周六": "saturday", "周日": "sunday"
        }

        weekday_en = weekday_map.get(weekday.lower(), weekday)
        job = getattr(schedule.every(), weekday_en).at(scheduled_time).do(weekly_wrapper)
        self.scheduled_jobs[task_id] = job
        BM_LOG.info(f"已安排每周任务 {task_id}: 每周{weekday} {scheduled_time}执行")

    def load_tasks_from_database(self):
        """从数据库加载任务"""
        try:
            tasks = TaskDatabase().get_active_tasks()
            BM_LOG.debug(f"[定时任务] 从数据库加载到 {len(tasks)} 个活跃任务")

            for task in tasks:
                try:
                    task_id = task["task_id"]
                    script_id = task["script_id"]
                    raw = task.get("task_parameter", [])
                    parameters = raw if isinstance(raw, list) else [raw] if raw else []

                    if task["task_type"] == "fixed_interval":
                        self.schedule_fixed_interval_task(
                            task_id, script_id, task["interval_minutes"],
                            parameters)

                    elif task["task_type"] == "random_interval":
                        self.schedule_random_interval_task(
                            task_id, script_id,
                            task["min_interval_minutes"], task["max_interval_minutes"],
                            parameters)

                    elif task["task_type"] == "countdown":
                        self.schedule_countdown_task(
                            task_id, script_id, task["delay_minutes"],
                            parameters)

                    elif task["task_type"] == "daily":
                        self.schedule_daily_task(
                            task_id, script_id, task["daily_time"],
                            parameters)

                    elif task["task_type"] == "weekly":
                        self.schedule_weekly_task(
                            task_id, script_id, task["weekly_weekday"], task["weekly_time"],
                            parameters)

                except Exception as e:
                    BM_LOG.error(f"加载任务 {task.get('task_id', 'unknown')} 失败: {e}")

        except Exception as e:
            BM_LOG.error(f"从数据库加载任务时出错: {e}")

    def _schedule_single_task(self, task_data):
        """安排单个任务"""
        task_id = task_data["task_id"]
        script_id = task_data["script_id"]
        task_type = task_data["task_type"]

        raw = task_data.get("task_parameter", [])
        parameters = raw if isinstance(raw, list) else [raw] if raw else []
        if not task_data.get('is_active'):
            return

        if task_type == "fixed_interval":
            self.schedule_fixed_interval_task(
                task_id, script_id, task_data["interval_minutes"],
                parameters)

        elif task_type == "random_interval":
            self.schedule_random_interval_task(
                task_id, script_id,
                task_data["min_interval_minutes"], task_data["max_interval_minutes"],
                parameters)

        elif task_type == "countdown":
            self.schedule_countdown_task(
                task_id, script_id, task_data["delay_minutes"],
                parameters)

        elif task_type == "daily":
            self.schedule_daily_task(
                task_id, script_id, task_data["daily_time"],
                parameters)

        elif task_type == "weekly":
            self.schedule_weekly_task(
                task_id, script_id, task_data["weekly_weekday"], task_data["weekly_time"],
                parameters)

        else:
            raise ValueError(f"不支持的任务类型: {task_type}")

    def add_dynamic_task(self, task_data):
        """动态添加新任务"""
        try:
            self._schedule_single_task(task_data)
            BM_LOG.info(f"已动态添加任务: {task_data.get('task_name', '未知任务')}")
            return True

        except Exception as e:
            BM_LOG.error(f"动态添加任务失败: {e}")
            raise RuntimeError('动态添加任务失败')

    def remove_task(self, task_id):
        """删除指定任务"""
        try:
            self.stop_task(task_id)
            TaskDatabase.delete_task(task_id)
            BM_LOG.info(f"已从数据库删除任务 {task_id}")
            return True

        except Exception as e:
            BM_LOG.error(f"删除任务 {task_id} 失败: {e}")
            return False

    def stop_task(self, task_id):
        if task_id in self.scheduled_jobs:
            job = self.scheduled_jobs[task_id]
            schedule.cancel_job(job)
            del self.scheduled_jobs[task_id]
            BM_LOG.info(f"已停止任务 {task_id} 的定时任务")

        if task_id in self.active_timers:
            timer = self.active_timers[task_id]
            timer.cancel()
            del self.active_timers[task_id]
            BM_LOG.info(f"已停止任务 {task_id} 的倒计时定时器")

    def clear_all_tasks(self):
        """清除所有已安排的任务和倒计时"""
        schedule.clear()
        self.scheduled_jobs.clear()
        for timer in self.active_timers.values():
            timer.cancel()
        self.active_timers.clear()

    def run(self):
        """运行调度器"""
        self.load_tasks_from_database()
        while not self._stop_event.is_set():
            schedule.run_pending()
            self._stop_event.wait(timeout=1)

        self.shutdown()

    def stop(self):
        """通知调度器退出"""
        self._stop_event.set()

    def get_scheduled_tasks(self):
        return list(self.scheduled_jobs.keys())

    def shutdown(self):
        """优雅关闭调度器，清理资源"""
        self.clear_all_tasks()
        self.thread_pool.shutdown(wait=True)

    def reload_tasks(self):
        """重新加载所有任务"""
        self.clear_all_tasks()
        self.load_tasks_from_database()


if __name__ == '__main__':
    scheduler = DatabaseTaskScheduler()
    scheduler.run()
