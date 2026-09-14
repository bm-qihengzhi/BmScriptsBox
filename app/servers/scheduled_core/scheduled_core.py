"""
Copyright (c) 2026 綦恒智
Email: bmscriptsbox@163.com
SPDX-License-Identifier: MIT
SPDX-License-Identifier: LicenseRef-Commons-Clause
"""
import json
import random
import tempfile
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import schedule

from app.data.database import TaskDatabase, ScriptDatabase
from app.utils import BM_LOG, ParameterManager
from app.servers.scripts import ScriptRunner
from app.utils.parameter_generate import build_launch_env


# 兼容早期版本误存的中文 task_type，统一为英文码
_TASK_TYPE_CODE = {
    '固定间隔执行': 'fixed_interval', '随机间隔执行': 'random_interval',
    '倒计时执行': 'countdown', '每天执行': 'daily', '每周执行': 'weekly',
}


class DatabaseTaskScheduler:
    def __init__(self):
        self.scheduled_jobs = {}
        self.active_timers = {}
        self.running_tasks = {}
        self.thread_pool = ThreadPoolExecutor(max_workers=10)
        self._stop_event = threading.Event()
        self.executed_counts = {}   # task_id -> 已执行次数（内存缓存）
        self.max_run_counts = {}    # task_id -> 执行次数上限，None=不限

    def execute_script(self, script_id, parameters: list, params_overrides: dict = None, task_id: int = None):
        """执行外部脚本；注入 output_json 供脚本回传结果，跑完记录执行历史"""
        from app.data import ProjectGlobal
        with ProjectGlobal.RUNNING_SCRIPTS_LOCK:
            ProjectGlobal.RUNNING_SCRIPTS.add(script_id)
        output_json = None
        status, code, msg = 'completed', None, None
        start = time.perf_counter()
        try:
            if not isinstance(parameters, list):
                parameters = [parameters] if parameters else []
            script_data = ScriptDatabase().get_script_by_id(script_id)
            inputs_schema = script_data.inputs_schema if script_data else []
            input_data = inputs_schema[0] if inputs_schema else {}
            params_defs = script_data.params_schema if script_data else []
            output_json = str(Path(tempfile.gettempdir()) / f"bms_{uuid.uuid4().hex}.out.json")
            env_extra = build_launch_env(script_id, invoke_mode="scheduled")

            json_path = ParameterManager().construct_parameters(
                input_data, parameters,
                output_json=output_json,
                params_defs=params_defs,
                params_overrides=params_overrides,
                env_extra=env_extra,
            )
            param_str = str(json_path)
            ScriptRunner().run_script(script_id=script_id, param=param_str)
            return True

        except Exception as e:
            BM_LOG.error(f"执行脚本异常 {script_id}: {e}")
            status, code, msg = 'failed', None, str(e)
            return False
        finally:
            with ProjectGlobal.RUNNING_SCRIPTS_LOCK:
                ProjectGlobal.RUNNING_SCRIPTS.discard(script_id)
            if task_id is not None:
                self._record_task_run(task_id, script_id, output_json, status, code, msg, start)

    def _record_task_run(self, task_id, script_id, output_json, status, code, msg, start):
        """读脚本回传的信封（只取 code/msg）落一条执行历史；随后清理结果文件"""
        duration_ms = int((time.perf_counter() - start) * 1000)
        if output_json and Path(output_json).exists():
            try:
                raw = json.loads(Path(output_json).read_text(encoding='utf-8'))
                if isinstance(raw, dict):
                    code = raw.get('code')
                    msg = raw.get('msg')
                    status = 'success' if code == 0 else 'failed'
            except Exception as e:
                BM_LOG.error(f"[定时任务] 解析结果失败 task={task_id}: {e}")
        try:
            TaskDatabase.record_task_run(task_id, script_id, status, code, msg, duration_ms)
        except Exception as e:
            BM_LOG.error(f"[定时任务] 记录失败 task={task_id}: {e}")
        if output_json and Path(output_json).exists():
            try:
                Path(output_json).unlink()
            except Exception:
                pass
                ProjectGlobal.RUNNING_SCRIPTS.discard(script_id)

    def _bump_executed_count(self, task_id) -> bool:
        """间隔类任务触发计数；跑满 max_run 次的最后一次仍执行，同时自动停用"""
        count = self.executed_counts.get(task_id)
        if count is None:
            task = TaskDatabase.get_task(task_id)
            if task:
                self.executed_counts[task_id] = task.get('executed_count', 0)
                self.max_run_counts[task_id] = task.get('max_run_count')
            count = self.executed_counts.get(task_id, 0)
        count += 1
        self.executed_counts[task_id] = count
        try:
            TaskDatabase.increment_executed_count(task_id)
        except Exception as e:
            BM_LOG.error(f"[定时任务] 计数失败 task={task_id}: {e}")

        max_run = self.max_run_counts.get(task_id)
        if max_run is not None and count >= max_run:
            self.stop_task(task_id)
            try:
                TaskDatabase.update_task(task_id, {"is_active": False})
            except Exception as e:
                BM_LOG.error(f"[定时任务] 停用失败 task={task_id}: {e}")
            BM_LOG.info(f"任务 {task_id} 已执行满 {max_run} 次，自动停用")
            # 跑满的那次仍执行；仅当异常超限（count > max_run）时不再执行
            return count <= max_run
        return True

    def schedule_fixed_interval_task(self, task_id, script_id, interval_seconds, parameters:list,
                                     params_overrides: dict = None):
        """1. 固定间隔时间运行（秒）"""
        def fixed_interval_wrapper():
            if not self._bump_executed_count(task_id):
                return
            try:
                self.thread_pool.submit(self.execute_script, script_id, parameters, params_overrides, task_id)
            except Exception as e:
                BM_LOG.error(f"[定时任务] wrapper 异常: {e}")

        if interval_seconds <= 0:
            interval_seconds = 5
        job = schedule.every(interval_seconds).seconds.do(fixed_interval_wrapper)
        self.scheduled_jobs[task_id] = job
        BM_LOG.info(f"已安排固定间隔任务 {task_id}: 每{interval_seconds}秒执行一次, job={job}")

    def schedule_random_interval_task(self, task_id, script_id, min_interval_seconds,
                                      max_interval_seconds, parameters:list, params_overrides: dict = None):
        """2. 随机间隔时间运行（最小间隔、最大间隔、秒）"""

        if min_interval_seconds <= 0:
            min_interval_seconds = 1
        if max_interval_seconds <= 0:
            max_interval_seconds = 1
        if min_interval_seconds > max_interval_seconds:
            min_interval_seconds, max_interval_seconds = max_interval_seconds, min_interval_seconds

        def random_interval_wrapper():
            if not self._bump_executed_count(task_id):
                return
            self.thread_pool.submit(self.execute_script, script_id, parameters, params_overrides, task_id)

            # 已达上限时 _bump 已移除 job，此时不再重排下一轮
            job = self.scheduled_jobs.get(task_id)
            if not job:
                return
            next_interval_seconds = random.randint(min_interval_seconds, max_interval_seconds)
            schedule.cancel_job(job)
            job = schedule.every(next_interval_seconds).seconds.do(random_interval_wrapper)
            self.scheduled_jobs[task_id] = job

        initial_interval_seconds = random.randint(min_interval_seconds, max_interval_seconds)
        job = schedule.every(initial_interval_seconds).seconds.do(random_interval_wrapper)
        self.scheduled_jobs[task_id] = job

    def schedule_countdown_task(self, task_id, script_id, delay_seconds, parameters:list,
                                params_overrides: dict = None):
        """3. 倒计时运行（秒）"""

        def countdown_wrapper():
            self.thread_pool.submit(self.execute_script, script_id, parameters, params_overrides, task_id)
            if task_id in self.active_timers:
                del self.active_timers[task_id]

        if delay_seconds <= 0:
            delay_seconds = 5
        timer = threading.Timer(delay_seconds, countdown_wrapper)
        timer.daemon = True
        timer.start()
        self.active_timers[task_id] = timer

    def schedule_daily_task(self, task_id, script_id, scheduled_time, parameters:list,
                            params_overrides: dict = None):
        """4. 每天固定时间运行（每天15:30）"""

        def daily_wrapper():
            self.thread_pool.submit(self.execute_script, script_id, parameters, params_overrides, task_id)

        job = schedule.every().day.at(scheduled_time).do(daily_wrapper)
        self.scheduled_jobs[task_id] = job
        BM_LOG.info(f"已安排每日任务 {task_id}: 每天{scheduled_time}执行")

    def schedule_weekly_task(self, task_id, script_id, weekday, scheduled_time, parameters:list,
                             params_overrides: dict = None):
        """5. 每周固定时间运行（例周三16:40分运行）"""

        def weekly_wrapper():
            self.thread_pool.submit(self.execute_script, script_id, parameters, params_overrides, task_id)

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
                    params_overrides = task.get("task_params") or {}
                    self.executed_counts[task_id] = task.get('executed_count', 0)
                    self.max_run_counts[task_id] = task.get('max_run_count')
                    task_type = _TASK_TYPE_CODE.get(task.get("task_type"), task.get("task_type"))

                    if task_type == "fixed_interval":
                        self.schedule_fixed_interval_task(
                            task_id, script_id, task["interval_minutes"],
                            parameters, params_overrides)

                    elif task_type == "random_interval":
                        self.schedule_random_interval_task(
                            task_id, script_id,
                            task["min_interval_minutes"], task["max_interval_minutes"],
                            parameters, params_overrides)

                    elif task_type == "countdown":
                        self.schedule_countdown_task(
                            task_id, script_id, task["delay_minutes"],
                            parameters, params_overrides)

                    elif task_type == "daily":
                        self.schedule_daily_task(
                            task_id, script_id, task["daily_time"],
                            parameters, params_overrides)

                    elif task_type == "weekly":
                        self.schedule_weekly_task(
                            task_id, script_id, task["weekly_weekday"], task["weekly_time"],
                            parameters, params_overrides)

                except Exception as e:
                    BM_LOG.error(f"加载任务 {task.get('task_id', 'unknown')} 失败: {e}")

        except Exception as e:
            BM_LOG.error(f"从数据库加载任务时出错: {e}")

    def _schedule_single_task(self, task_data):
        """安排单个任务"""
        task_id = task_data["task_id"]
        script_id = task_data["script_id"]
        self.executed_counts[task_id] = task_data.get('executed_count', 0)
        self.max_run_counts[task_id] = task_data.get('max_run_count')
        task_type = _TASK_TYPE_CODE.get(task_data["task_type"], task_data["task_type"])

        raw = task_data.get("task_parameter", [])
        parameters = raw if isinstance(raw, list) else [raw] if raw else []
        params_overrides = task_data.get("task_params") or {}
        if not task_data.get('is_active'):
            return

        if task_type == "fixed_interval":
            self.schedule_fixed_interval_task(
                task_id, script_id, task_data["interval_minutes"],
                parameters, params_overrides)

        elif task_type == "random_interval":
            self.schedule_random_interval_task(
                task_id, script_id,
                task_data["min_interval_minutes"], task_data["max_interval_minutes"],
                parameters, params_overrides)

        elif task_type == "countdown":
            self.schedule_countdown_task(
                task_id, script_id, task_data["delay_minutes"],
                parameters, params_overrides)

        elif task_type == "daily":
            self.schedule_daily_task(
                task_id, script_id, task_data["daily_time"],
                parameters, params_overrides)

        elif task_type == "weekly":
            self.schedule_weekly_task(
                task_id, script_id, task_data["weekly_weekday"], task_data["weekly_time"],
                parameters, params_overrides)

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

        self.executed_counts.pop(task_id, None)
        self.max_run_counts.pop(task_id, None)

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
