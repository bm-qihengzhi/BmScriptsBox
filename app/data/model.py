"""
Copyright (c) 2026 綦恒智
Email: bmscriptsbox@163.com
SPDX-License-Identifier: MIT
SPDX-License-Identifier: LicenseRef-Commons-Clause
"""
import atexit
import json
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

from peewee import *

if getattr(sys, 'frozen', False):
    _root = Path(sys.executable).parent
else:
    _root = Path(__file__).parents[2]
db_path = _root / 'BmData' / 'app_scripts.db'
db_path.parent.mkdir(exist_ok=True)
db = SqliteDatabase(
    db_path,
    pragmas={
        'journal_mode': 'wal',      # 读写并发友好，降低 "database is locked"
        'busy_timeout': 5000,       # 锁等待 5s
        'synchronous': 'NORMAL',
    },
)

atexit.register(db.close)
class BaseModel(Model):
    class Meta:
        database = db


class Script(BaseModel):
    # --- 1. Info (脚本基本信息) ---
    id = CharField(primary_key=True)         # 脚本 ID (UUID)
    name = CharField()                       # 名称
    icon = CharField()                       # 图标
    version = CharField()                    # 版本
    desc = TextField(null=True)              # 描述
    badge = CharField(null=True)             # 标签
    pin = BooleanField(default=False)        # 置顶

    # --- 2. Runtime (运行环境) ---
    language = CharField()                       # 语言 (powershell/python...)
    language_version = CharField()           # 语言版本 ('>=3.8')
    entry = CharField()                      # 入口文件
    terminal = CharField(default="never")    # 终端策略
    binaries = TextField(null=True)          # 依赖的二进制 (存储为 JSON 字符串)
    dependencies = TextField(null=True)      # 依赖库

    # --- 3. IO Contract (核心契约 - 工作流关键) ---
    # 存储为 JSON 字符串，包含 name, type, exts 等
    inputs_schema = TextField(null=True)
    outputs_schema = TextField(null=True)
    params_schema = TextField(null=True)  # 脚本运行参数 ([[bmscriptsbox.params]])
    workflow_enabled = BooleanField(default=True)
    is_node = BooleanField(default=False)  # 可作为节点被联动调用 ([bmscriptsbox.node])
    schedule_enabled = BooleanField(default=False)  # 声明可被定时任务调度 ([bmscriptsbox.schedule])
    params_form_enabled = BooleanField(default=False)  # 声明：交互式运行时盒子生成参数表单 ([bmscriptsbox.params_form])
    models_schema = TextField(null=True)  # 模型声明 ([bmscriptsbox.models])，存储为 JSON 字符串

    # --- 4. Triggers (触发器配置) ---
    triggers_schema = TextField(default="{}")
    hotkey = CharField(null=True, unique=True) # 组合键
    hotkey_active = BooleanField(default=False)
    quick_copy_active = BooleanField(default=False)


    # --- 5. Audit (审计) ---
    created_at = DateTimeField(default=datetime.now)
    updated_at = DateTimeField(default=datetime.now)
    run_count = IntegerField(default=0) # 允许次数
    last_run_at = DateTimeField(null=True) # 最后运行时间

    class Meta:
        table_name = "app_scripts"


class Config(BaseModel):
    mouse_middle = BooleanField(default=True)  # 是否启用鼠标中键
    shortcut_key_rouse = TextField(default=json.dumps([]))  # 改为列表存储  # 快捷键列表
    desktop_inform = BooleanField(default=True)  # 是否启用桌面通知
    follow_start = BooleanField(default=False)  # 是否跟随启动
    start_to_tray = BooleanField(default=False)  # 启动时隐藏到托盘
    wechat_push_to = CharField(default='')  # 只读镜像：当前绑定收件人ID，真实来源是 weixin_state.json 的 recipient

    class Meta:
        table_name = "app_config"

class Task(BaseModel):
    """定时任务模型"""
    task_id = AutoField(primary_key=True)  # 任务ID
    task_name = CharField()  # 任务名称
    task_type = CharField()  # 任务类型: fixed_interval, countdown, daily, weekly, monthly（random_interval 已废弃）
    script_id = CharField()
    icon = CharField()
    is_active = BooleanField(default=True)  # 是否启用
    task_parameter = TextField(null=True)
    task_parameter_type = CharField(default="")
    task_params = TextField(null=True)  # 任务可配置的 params 覆盖（JSON 字符串）

    # 执行次数上限（固定/随机间隔可用，None=不限次数）
    max_run_count = IntegerField(null=True)  # 执行次数上限
    executed_count = IntegerField(default=0)  # 已执行次数

    wechat_push = BooleanField(default=False)  # 执行结果是否推送到微信（按任务决定，收件人全局唯一）

    # 固定间隔任务参数（单位：秒；列名已由 *_minutes 统一改名为 *_seconds）
    interval_seconds = IntegerField(null=True)  # 间隔秒数
    jitter_seconds = IntegerField(null=True)  # ±秒扰动，实际间隔∈[base-jitter, base+jitter]；0=纯固定

    # 随机间隔任务参数（已废弃：策略被“固定间隔+扰动”取代；列保留以兼容旧任务显示/回填）
    min_interval_seconds = IntegerField(null=True)  # 最小间隔秒数
    max_interval_seconds = IntegerField(null=True)  # 最大间隔秒数

    # 倒计时任务参数
    delay_seconds = IntegerField(null=True)  # 延迟秒数

    # 每日任务参数
    daily_time = CharField(null=True)  # 每日执行时间（格式: HH:MM）

    # 每周任务参数
    weekly_weekday = CharField(null=True)  # 星期几（中文或英文）
    weekly_time = CharField(null=True)  # 每周执行时间（格式: HH:MM）

    # 每月任务参数
    monthly_day = IntegerField(null=True)  # 每月执行日（1-31；29-31 短月回退到当月最后一天）
    monthly_time = CharField(null=True)  # 每月执行时间（格式: HH:MM）

    created_time = DateTimeField(default=datetime.now)  # 创建时间
    updated_time = DateTimeField(default=datetime.now)  # 更新时间

    class Meta:
        table_name = "app_tasks"


class TaskRun(BaseModel):
    """定时任务历史执行记录（只记 code+msg，业务键不落库）"""
    id = AutoField(primary_key=True)
    task_id = IntegerField(index=True)   # 关联 app_tasks.task_id
    script_id = CharField(null=True)     # 执行的脚本 ID
    status = CharField(default='completed')  # success | failed | completed
    code = IntegerField(null=True)       # 脚本回传信封的 code；脚本未写则 null
    msg = TextField(null=True)           # 信封 msg（人话描述）
    run_at = DateTimeField(default=datetime.now)  # 执行时间
    duration_ms = IntegerField(null=True)         # 耗时（毫秒）

    class Meta:
        table_name = "app_task_runs"


class ScriptParamMemory(BaseModel):
    """脚本参数表单记忆：记住每次确认运行的 params 覆盖值，下次回填"""
    script_id = CharField(primary_key=True)
    params = TextField(default='{}')  # 上次确认的 params（JSON）
    updated_at = DateTimeField(default=datetime.now)

    class Meta:
        table_name = "app_script_param_memory"


_tables_initialized = False

def ensure_tables():
    global _tables_initialized
    if _tables_initialized:
        return
    db.create_tables([Script, Config, Task, TaskRun, ScriptParamMemory], safe=True)
    # 迁移：新增列（兼容已有数据库）
    try:
        db.execute_sql("ALTER TABLE app_config ADD COLUMN start_to_tray INTEGER NOT NULL DEFAULT 0")
    except Exception:
        pass  # 列已存在
    try:
        db.execute_sql("ALTER TABLE app_scripts ADD COLUMN params_schema TEXT")
    except Exception:
        pass  # 列已存在
    try:
        db.execute_sql("ALTER TABLE app_scripts ADD COLUMN is_node INTEGER NOT NULL DEFAULT 0")
    except Exception:
        pass  # 列已存在
    try:
        db.execute_sql("ALTER TABLE app_scripts ADD COLUMN schedule_enabled INTEGER NOT NULL DEFAULT 0")
    except Exception:
        pass  # 列已存在
    try:
        db.execute_sql("ALTER TABLE app_scripts ADD COLUMN params_form_enabled INTEGER NOT NULL DEFAULT 0")
    except Exception:
        pass  # 列已存在
    try:
        db.execute_sql("ALTER TABLE app_scripts ADD COLUMN models_schema TEXT")
    except Exception:
        pass  # 列已存在
    try:
        db.execute_sql("ALTER TABLE app_tasks ADD COLUMN task_params TEXT")
    except Exception:
        pass  # 列已存在
    try:
        db.execute_sql("ALTER TABLE app_tasks ADD COLUMN max_run_count INTEGER")
    except Exception:
        pass  # 列已存在
    try:
        db.execute_sql("ALTER TABLE app_tasks ADD COLUMN executed_count INTEGER NOT NULL DEFAULT 0")
    except Exception:
        pass  # 列已存在
    try:
        db.execute_sql("ALTER TABLE app_tasks ADD COLUMN monthly_day INTEGER")
    except Exception:
        pass  # 列已存在
    try:
        db.execute_sql("ALTER TABLE app_tasks ADD COLUMN monthly_time TEXT")
    except Exception:
        pass  # 列已存在
    # 迁移 v3：app_tasks 间隔/倒计时字段列名 *_minutes → *_seconds（值单位仍为秒），
    # 并兼容历史 v2（早期分钟单位 ×60 转秒）。以 PRAGMA table_info 判断列是否存在，
    # 保证新库/旧库都能安全、且只执行一次。
    cur = db.execute_sql("PRAGMA user_version").fetchone()
    ver = cur[0] if cur else 0
    cols = {r[1] for r in db.execute_sql("PRAGMA table_info(app_tasks)").fetchall()}
    legacy = [c for c in ('interval_minutes', 'min_interval_minutes',
                          'max_interval_minutes', 'delay_minutes') if c in cols]
    if legacy:
        # v2：早期以“分钟”存储的旧库，先换算为秒（仅在 user_version<2 时做一次）
        if ver < 2:
            db.execute_sql("UPDATE app_tasks SET interval_minutes = interval_minutes * 60 "
                           "WHERE interval_minutes IS NOT NULL")
            db.execute_sql("UPDATE app_tasks SET min_interval_minutes = min_interval_minutes * 60, "
                           "max_interval_minutes = max_interval_minutes * 60 "
                           "WHERE min_interval_minutes IS NOT NULL OR max_interval_minutes IS NOT NULL")
            db.execute_sql("UPDATE app_tasks SET delay_minutes = delay_minutes * 60 "
                           "WHERE delay_minutes IS NOT NULL")
        # v3：列名改名（SQLite >= 3.25 原生 RENAME COLUMN，否则回退“建新表搬数据”）
        rename_map = {
            'interval_minutes': 'interval_seconds',
            'min_interval_minutes': 'min_interval_seconds',
            'max_interval_minutes': 'max_interval_seconds',
            'delay_minutes': 'delay_seconds',
        }
        if tuple(int(x) for x in sqlite3.sqlite_version.split('.')) >= (3, 25, 0):
            for old, new in rename_map.items():
                if old in cols and new not in cols:
                    db.execute_sql(f"ALTER TABLE app_tasks RENAME COLUMN {old} TO {new}")
        else:
            # 兜底（SQLite < 3.25 无 RENAME COLUMN）：新增 *_seconds 列并拷贝值，
            # 遗留 *_minutes 列不再被 peewee 映射，保留无害。
            for old, new in rename_map.items():
                if old in cols and new not in cols:
                    db.execute_sql(f"ALTER TABLE app_tasks ADD COLUMN {new} INTEGER")
                    db.execute_sql(f"UPDATE app_tasks SET {new} = {old}")
    if ver < 3:
        db.execute_sql("PRAGMA user_version = 3")
    # 迁移 v5：新增 jitter_seconds（幂等），并把已废弃的“随机间隔”任务停用
    # （策略被“固定间隔+扰动”取代；列 min/max_interval_seconds 保留以兼容旧行显示/回填）。
    try:
        db.execute_sql("ALTER TABLE app_tasks ADD COLUMN jitter_seconds INTEGER DEFAULT 0")
    except Exception:
        pass  # 列已存在
    if ver < 5:
        db.execute_sql("UPDATE app_tasks SET is_active = 0 WHERE task_type = 'random_interval'")
        db.execute_sql("PRAGMA user_version = 5")
    # 迁移 v6：app_config 新增 wechat_push_to（绑定收件人 ID 的只读镜像，幂等，旧行取 SQL 默认 ''）
    # 注：曾经的全局推送开关 wechat_push_enabled 已废弃，改由 app_tasks.wechat_push 按任务决定；
    # 旧库残留的那一列不再被模型映射，无害。
    try:
        db.execute_sql("ALTER TABLE app_config ADD COLUMN wechat_push_to TEXT DEFAULT ''")
    except Exception:
        pass  # 列已存在
    if ver < 6:
        db.execute_sql("PRAGMA user_version = 6")
    # 按任务粒度的微信推送开关（纯加列，幂等，不需要 user_version 参与）
    try:
        db.execute_sql("ALTER TABLE app_tasks ADD COLUMN wechat_push INTEGER NOT NULL DEFAULT 0")
    except Exception:
        pass  # 列已存在
    if not Config.select().exists():
        Config.create(
            mouse_middle=True,
            shortcut_key_rouse=json.dumps(['ctrl']),
            desktop_inform=True,
            follow_start=False,
            start_to_tray=False
        )
    _tables_initialized = True