"""
Copyright (c) 2026 綦恒智
Email: bmscriptsbox@163.com
SPDX-License-Identifier: AGPL-3.0
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
    workflow_enabled = BooleanField(default=True)

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

    # 固定间隔任务参数
    interval_minutes = IntegerField(null=True)  # 间隔分钟数

    # 随机间隔任务参数
    min_interval_minutes = IntegerField(null=True)  # 最小间隔分钟数
    max_interval_minutes = IntegerField(null=True)  # 最大间隔分钟数

    # 倒计时任务参数
    delay_minutes = IntegerField(null=True)  # 延迟分钟数

    # 每日任务参数
    daily_time = CharField(null=True)  # 每日执行时间（格式: HH:MM）

    # 每周任务参数
    weekly_weekday = CharField(null=True)  # 星期几（中文或英文）
    weekly_time = CharField(null=True)  # 每周执行时间（格式: HH:MM）

    created_time = DateTimeField(default=datetime.now)  # 创建时间
    updated_time = DateTimeField(default=datetime.now)  # 更新时间

    class Meta:
        table_name = "app_tasks"


_tables_initialized = False

def ensure_tables():
    global _tables_initialized
    if _tables_initialized:
        return
    db.create_tables([Script, Config, Task], safe=True)
    if not Config.select().exists():
        Config.create(
            mouse_middle=True,
            shortcut_key_rouse=json.dumps(['f12']),
            desktop_inform=True,
            follow_start=False
        )
    _tables_initialized = True