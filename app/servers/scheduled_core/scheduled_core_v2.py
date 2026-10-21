"""
Copyright (c) 2026 綦恒智
Email: bmscriptsbox@163.com
SPDX-License-Identifier: MIT
SPDX-License-Identifier: LicenseRef-Commons-Clause

基于 APScheduler 3.x 的定时任务调度核心（V2）。
用 BackgroundScheduler 替换手写 schedule 轮询循环：调度状态由 APScheduler 内部管理，
UI 线程调用其线程安全 API（add_job/remove_job），从根本上消除跨线程访问全局 schedule 的竞争。

时区：不显式指定，APScheduler 自动跟随操作系统本地时区（tzlocal.get_localzone()）。
对外方法签名与旧 DatabaseTaskScheduler 保持一致，ScheduledWork / Presenter / UI 无需改动。
"""
import calendar
import json
import random
import tempfile
import threading
import time
import uuid
from datetime import datetime, timedelta
from pathlib import Path

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.date import DateTrigger
from apscheduler.events import EVENT_JOB_MISSED

from app.data.database import TaskDatabase
from app.utils import BM_LOG
from app.utils.parameter_generate import build_launch_env


# 兼容早期版本误存的中文 task_type，统一为英文码
_TASK_TYPE_CODE = {
    '固定间隔执行': 'fixed_interval', '随机间隔执行': 'random_interval',
    '倒计时执行': 'countdown', '每天执行': 'daily', '每周执行': 'weekly',
    '每月执行': 'monthly',
}

# 中文/英文星期 → APScheduler CronTrigger day_of_week 名称
_WEEKDAY_MAP = {
    "monday": "mon", "tuesday": "tue", "wednesday": "wed", "thursday": "thu",
    "friday": "fri", "saturday": "sat", "sunday": "sun",
    "周一": "mon", "周二": "tue", "周三": "wed", "周四": "thu",
    "周五": "fri", "周六": "sat", "周日": "sun",
}

# 错过触发时的补跑窗口（秒）：interval/countdown 较短，daily/weekly 给一小时
_MISFIRE_GRACE = {
    'fixed_interval': 60, 'random_interval': 60, 'countdown': 300,
    'daily': 3600, 'weekly': 3600, 'monthly': 3600,
}


def _to_parameters(raw):
    """task_parameter 兼容 list / 标量 / 空"""
    if isinstance(raw, list):
        return raw
    return [raw] if raw else []


def _parse_hhmm(value):
    """'HH:MM' → (hour, minute)；解析失败返回 None"""
    if not value:
        return None
    try:
        hh, mm = str(value).strip().split(':')[:2]
        return int(hh), int(mm)
    except Exception:
        return None


def _next_monthly_run_date(tz, day, hour, minute):
    """下一次“每月 day 号 hour:minute”的 tz-aware 时间。
    day 超出当月天数时回退到该月最后一天（如选 31，2 月则在 28/29 号执行）。"""
    now = datetime.now(tz)
    try:
        day = max(1, min(int(day), 31))
    except (TypeError, ValueError):
        day = 1
    y, m = now.year, now.month
    for _ in range(25):  # 最多向后找 24 个月，防御死循环
        last_day = calendar.monthrange(y, m)[1]
        candidate = datetime(y, m, min(day, last_day), hour, minute, tzinfo=tz)
        if candidate > now:
            return candidate
        m += 1
        if m > 12:
            m, y = 1, y + 1
    return now + timedelta(days=1)


class DatabaseTaskScheduler:
    """APScheduler 版调度核心，对外接口与旧实现一致"""

    def __init__(self):
        # 不传 timezone：BackgroundScheduler 默认取操作系统本地时区
        self._scheduler = BackgroundScheduler(
            job_defaults={
                'max_instances': 1,   # 上一轮未跑完则跳过本轮，杜绝堆积
                'coalesce': True,     # 多次错过合并为一次
            },
        )
        self._stop_event = threading.Event()
        self._started = False
        self._meta_lock = threading.Lock()
        self._task_meta = {}          # task_id -> {'task_type','script_id'}（仅供 MISSED 记录用）

        # 仅监听 MISSED（重叠被跳过时补一条 skipped 历史）；
        # 计数 / max 停用 / 随机重排改到 job 函数（执行器线程）里做，见 _run_and_manage
        self._scheduler.add_listener(self._on_job_missed, EVENT_JOB_MISSED)

    # ------------------------------------------------------------------ 执行

    def execute_script(self, script_id, parameters: list, params_overrides: dict = None, task_id: int = None):
        """执行外部脚本；注入 output_json 供脚本回传结果，跑完记录执行历史。
        返回 {ok, status, code, msg, duration_ms}（未记录历史时 status/duration 可能为默认）。"""
        from app.servers.scripts import ScriptLaunchService, ScriptBusyError
        result = {'ok': False, 'status': 'failed', 'code': None, 'msg': None, 'duration_ms': None}
        output_json = None
        status = 'failed'
        start = time.perf_counter()
        ctx = None
        try:
            if not isinstance(parameters, list):
                parameters = [parameters] if parameters else []
            output_json = str(Path(tempfile.gettempdir()) / f"bms_{uuid.uuid4().hex}.out.json")
            env_extra = build_launch_env(script_id, invoke_mode="scheduled")

            # 原子占用：与手动触发/其它任务共用单例约束；所有权随 ctx 转移，由 cleanup 释放
            ctx = ScriptLaunchService.prepare(
                script_id, data=parameters, params_overrides=params_overrides,
                invoke_mode='scheduled', allow_params_form=False, reserve_first=True,
                output_json=output_json, env_extra=env_extra,
            )
            ScriptLaunchService.run(ctx)
            status = 'success'
            result['ok'] = True

        except ScriptBusyError:
            # 跳过记录由 _run_and_manage 负责，这里不写执行历史
            result['status'] = 'skipped'
            result['msg'] = '脚本正在运行中，跳过本次定时执行'
        except Exception as e:
            BM_LOG.error(f"执行脚本异常 {script_id}: {e}")
            status = 'failed'
            result['msg'] = str(e)
        finally:
            if ctx is not None:
                ScriptLaunchService.cleanup(ctx)
            if task_id is not None and result.get('status') != 'skipped':
                outcome = self._record_task_run(task_id, script_id, output_json, status, result.get('code'), result.get('msg'), start)
                result.update(outcome)
        return result

    def _record_task_run(self, task_id, script_id, output_json, status, code, msg, start):
        """读脚本回传的信封（只取 code/msg）落一条执行历史；随后清理结果文件。
        返回最终判定的 {status, code, msg, duration_ms}，供上层推送复用。"""
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
        if output_json:
            try:
                Path(output_json).unlink(missing_ok=True)
            except Exception:
                pass
        return {'status': status, 'code': code, 'msg': msg, 'duration_ms': duration_ms}

    # ----------------------------------------------------- job 包装（执行器线程）

    def _run_and_manage(self, script_id, parameters, params_overrides, task_id, reschedule):
        """job 实际回调：跑脚本 → 计数 → max 停用 / 自重排 → 推送（全部在 executor 工作线程执行）
        reschedule=True 表示该 job 用一次性 DateTrigger 排程，跑完需重排下一轮
        （固定间隔带扰动、每月；jitter=0 的固定间隔与 daily/weekly 由重复 trigger 续，为 False）。"""
        result = self.execute_script(script_id, parameters, params_overrides, task_id)

        # 脚本正被其它入口占用而跳过：记一条 skipped，不计入执行次数、不重排
        if result.get('status') == 'skipped':
            try:
                TaskDatabase.record_task_run(task_id, script_id, 'skipped')
            except Exception as e:
                BM_LOG.error(f"[定时任务] 记录跳过失败 task={task_id}: {e}")
            return

        try:
            TaskDatabase.increment_executed_count(task_id)
            task = TaskDatabase.get_task(task_id)
        except Exception as e:
            BM_LOG.error(f"[定时任务] 计数失败 task={task_id}: {e}")
            return
        if not task:
            # 任务已被删除，兜底移除可能残留的 job
            self._remove_job(task_id)
            return

        executed = task.get('executed_count', 0)
        max_run = task.get('max_run_count')
        if max_run is not None and executed >= max_run:
            self._remove_job(task_id)
            try:
                TaskDatabase.update_task(task_id, {"is_active": False})
            except Exception as e:
                BM_LOG.error(f"[定时任务] 停用失败 task={task_id}: {e}")
            BM_LOG.info(f"任务 {task_id} 已执行满 {max_run} 次，自动停用")
        elif reschedule and task.get('is_active'):
            # 一次性触发 + 自重排任务（固定带扰动、每月）跑完后排下一轮
            self._apply_task(task)

        # 推送放在排程/停用都落定之后：sendmessage 是同步等待，不能让微信侧拖后下一轮触发时间
        self._maybe_push(task, result)

    def _maybe_push(self, task, result):
        """按任务勾选把本次执行结果推送到微信；best-effort，异常绝不影响调度。"""
        if not task.get('wechat_push'):
            return
        try:
            from app.servers.wechat_push import WechatPushService
            service = WechatPushService.instance()
            if not service.push_task_result(
                    task, result.get('status'), result.get('code'),
                    result.get('msg'), result.get('duration_ms')):
                # 勾了却没收到时，原因只在这一行日志里可查
                BM_LOG.warning(f"[定时任务] 微信推送未发出 task={task.get('task_id')}: "
                               f"{service.last_skip_reason()}")
        except Exception as e:
            BM_LOG.error(f"[定时任务] 微信推送失败 task={task.get('task_id')}: {e}")

    # --------------------------------------------------------------- MISSED 事件

    def _on_job_missed(self, event):
        """重叠被跳过：补一条 skipped 历史（不计入执行次数）"""
        try:
            task_id = int(event.job_id)
        except (TypeError, ValueError):
            return
        with self._meta_lock:
            meta = self._task_meta.get(task_id, {})
        try:
            TaskDatabase.record_task_run(task_id, meta.get('script_id'), 'skipped')
        except Exception as e:
            BM_LOG.error(f"[定时任务] 记录跳过失败 task={task_id}: {e}")

    # ------------------------------------------------------------ 排程逻辑

    def _remove_job(self, task_id):
        jid = str(task_id)
        if self._scheduler.get_job(jid):
            self._scheduler.remove_job(jid)

    def _apply_task(self, task):
        """按任务字典安排 job；不存在/未启用则仅移除旧 job"""
        task_id = task["task_id"]
        task_type = _TASK_TYPE_CODE.get(task.get("task_type"), task.get("task_type"))
        # 已废弃的"随机间隔"透明转为固定+扰动近似值（base=区间均值、jitter=半幅）
        if task_type == 'random_interval':
            task = dict(task)
            lo = task.get("min_interval_seconds") or 1
            hi = task.get("max_interval_seconds") or 1
            lo = lo if lo > 0 else 1
            hi = hi if hi > 0 else 1
            if lo > hi:
                lo, hi = hi, lo
            task['interval_seconds'] = (lo + hi) // 2
            task['jitter_seconds'] = (hi - lo) // 2
            task_type = 'fixed_interval'
        with self._meta_lock:
            self._task_meta[task_id] = {'task_type': task_type, 'script_id': task.get('script_id')}

        # 先移除同名旧 job，避免重复排程（编辑覆盖场景）
        self._remove_job(task_id)
        if not task.get('is_active'):
            return

        script_id = task["script_id"]
        parameters = _to_parameters(task.get("task_parameter", []))
        params_overrides = task.get("task_params") or {}
        tz = self._scheduler.timezone
        jid = str(task_id)
        grace = _MISFIRE_GRACE.get(task_type, 60)
        reschedule = False

        if task_type == 'fixed_interval':
            base = task.get("interval_seconds") or 5
            if base <= 0:
                base = 5
            jitter = task.get("jitter_seconds") or 0
            if jitter < 0:
                jitter = 0
            if jitter == 0:
                trigger = IntervalTrigger(seconds=base)
            else:
                nxt = max(1, base + random.uniform(-jitter, jitter))
                trigger = DateTrigger(run_date=datetime.now(tz) + timedelta(seconds=nxt), timezone=tz)
                reschedule = True
        elif task_type == 'countdown':
            delay = task.get("delay_seconds") or 5
            if delay <= 0:
                delay = 5
            run_date = datetime.now(tz) + timedelta(seconds=delay)
            trigger = DateTrigger(run_date=run_date, timezone=tz)
        elif task_type == 'daily':
            hm = _parse_hhmm(task.get("daily_time"))
            if not hm:
                BM_LOG.error(f"[定时任务] 每日任务 {task_id} 时间格式非法: {task.get('daily_time')}")
                return
            trigger = CronTrigger(hour=hm[0], minute=hm[1])
        elif task_type == 'weekly':
            hm = _parse_hhmm(task.get("weekly_time"))
            dow = _WEEKDAY_MAP.get(str(task.get("weekly_weekday", "")).lower(),
                                  _WEEKDAY_MAP.get(task.get("weekly_weekday", ""), None))
            if not hm or not dow:
                BM_LOG.error(f"[定时任务] 每周任务 {task_id} 参数非法: {task.get('weekly_weekday')} {task.get('weekly_time')}")
                return
            trigger = CronTrigger(day_of_week=dow, hour=hm[0], minute=hm[1])
        elif task_type == 'monthly':
            hm = _parse_hhmm(task.get("monthly_time"))
            if not hm:
                BM_LOG.error(f"[定时任务] 每月任务 {task_id} 时间格式非法: {task.get('monthly_time')}")
                return
            run_date = _next_monthly_run_date(tz, task.get("monthly_day", 1), hm[0], hm[1])
            trigger = DateTrigger(run_date=run_date, timezone=tz)
            reschedule = True
        else:
            raise ValueError(f"不支持的任务类型: {task_type}")

        args = (script_id, parameters, params_overrides, task_id, reschedule)
        self._scheduler.add_job(
            self._run_and_manage, trigger=trigger, args=args, id=jid,
            name=task.get('task_name', jid), misfire_grace_time=grace,
            replace_existing=True,
        )
        BM_LOG.info(f"已安排任务 {task_id}({task_type}) job={jid}")

    def load_tasks_from_database(self):
        """从数据库加载所有活跃任务"""
        try:
            tasks = TaskDatabase.get_active_tasks()
            BM_LOG.debug(f"[定时任务] 从数据库加载到 {len(tasks)} 个活跃任务")
            for task in tasks:
                try:
                    self._apply_task(task)
                except Exception as e:
                    BM_LOG.error(f"加载任务 {task.get('task_id', 'unknown')} 失败: {e}")
        except Exception as e:
            BM_LOG.error(f"从数据库加载任务时出错: {e}")

    def add_dynamic_task(self, task_data):
        """动态添加/更新单个任务"""
        try:
            self._apply_task(task_data)
            BM_LOG.info(f"已动态添加任务: {task_data.get('task_name', '未知任务')}")
            return True
        except Exception as e:
            BM_LOG.error(f"动态添加任务失败: {e}")
            raise RuntimeError('动态添加任务失败')

    def remove_task(self, task_id):
        """删除指定任务（连同 job 与 DB 记录）"""
        try:
            self.stop_task(task_id)
            TaskDatabase.delete_task(task_id)
            BM_LOG.info(f"已从数据库删除任务 {task_id}")
            return True
        except Exception as e:
            BM_LOG.error(f"删除任务 {task_id} 失败: {e}")
            return False

    def stop_task(self, task_id):
        """停止某任务的调度并清理元数据"""
        self._remove_job(task_id)
        with self._meta_lock:
            self._task_meta.pop(task_id, None)

    def clear_all_tasks(self):
        try:
            self._scheduler.remove_all_jobs()
        except Exception as e:
            BM_LOG.error(f"[定时任务] 清空任务失败: {e}")
        with self._meta_lock:
            self._task_meta.clear()

    def get_scheduled_tasks(self):
        try:
            return [int(j.id) for j in self._scheduler.get_jobs()]
        except Exception:
            return []

    def reload_tasks(self):
        self.clear_all_tasks()
        self.load_tasks_from_database()

    # ------------------------------------------------------------- 生命周期

    def run(self):
        """启动调度器并阻塞，直到收到停止信号"""
        self.load_tasks_from_database()
        if not self._started:
            self._scheduler.start()
            self._started = True
        self._stop_event.wait()
        self.shutdown()

    def stop(self):
        """通知调度线程退出"""
        self._stop_event.set()

    def shutdown(self):
        """优雅关闭"""
        if self._started:
            try:
                self._scheduler.shutdown(wait=True)
            except Exception:
                pass
            self._started = False


if __name__ == '__main__':
    scheduler = DatabaseTaskScheduler()
    scheduler.run()
