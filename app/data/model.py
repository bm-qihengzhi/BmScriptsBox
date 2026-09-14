"""
Copyright (c) 2026 綦恒智
Email: bmscriptsbox@163.com
SPDX-License-Identifier: MIT
SPDX-License-Identifier: LicenseRef-Commons-Clause
"""
import atexit
import json
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
db = SqliteDatabase(db_path)

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

    class Meta:
        table_name = "app_config"

class Task(BaseModel):
    """定时任务模型"""
    task_id = AutoField(primary_key=True)  # 任务ID
    task_name = CharField()  # 任务名称
    task_type = CharField()  # 任务类型: fixed_interval, random_interval, countdown, daily, weekly
    script_id = CharField()
    icon = CharField()
    is_active = BooleanField(default=True)  # 是否启用
    task_parameter = TextField(null=True)
    task_parameter_type = CharField(default="")
    task_params = TextField(null=True)  # 任务可配置的 params 覆盖（JSON 字符串）

    # 执行次数上限（固定/随机间隔可用，None=不限次数）
    max_run_count = IntegerField(null=True)  # 执行次数上限
    executed_count = IntegerField(default=0)  # 已执行次数

    # 固定间隔任务参数（列名沿用 *_minutes，值单位已统一为秒）
    interval_minutes = IntegerField(null=True)  # 间隔秒数

    # 随机间隔任务参数
    min_interval_minutes = IntegerField(null=True)  # 最小间隔秒数
    max_interval_minutes = IntegerField(null=True)  # 最大间隔秒数

    # 倒计时任务参数
    delay_minutes = IntegerField(null=True)  # 延迟秒数

    # 每日任务参数
    daily_time = CharField(null=True)  # 每日执行时间（格式: HH:MM）

    # 每周任务参数
    weekly_weekday = CharField(null=True)  # 星期几（中文或英文）
    weekly_time = CharField(null=True)  # 每周执行时间（格式: HH:MM）

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
    # 迁移 v2：间隔/随机间隔/倒计时单位由分钟改为秒（旧值 ×60），user_version 保证只执行一次
    cur = db.execute_sql("PRAGMA user_version").fetchone()
    if not cur or cur[0] < 2:
        db.execute_sql(
            "UPDATE app_tasks SET interval_minutes = interval_minutes * 60 "
            "WHERE interval_minutes IS NOT NULL"
        )
        db.execute_sql(
            "UPDATE app_tasks SET min_interval_minutes = min_interval_minutes * 60, "
            "max_interval_minutes = max_interval_minutes * 60 "
            "WHERE min_interval_minutes IS NOT NULL OR max_interval_minutes IS NOT NULL"
        )
        db.execute_sql(
            "UPDATE app_tasks SET delay_minutes = delay_minutes * 60 "
            "WHERE delay_minutes IS NOT NULL"
        )
        db.execute_sql("PRAGMA user_version = 2")
    if not Config.select().exists():
        Config.create(
            mouse_middle=True,
            shortcut_key_rouse=json.dumps(['ctrl']),
            desktop_inform=True,
            follow_start=False,
            start_to_tray=False
        )
    _tables_initialized = True