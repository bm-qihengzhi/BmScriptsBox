"""
Copyright (c) 2026 綦恒智
Email: bmscriptsbox@163.com
SPDX-License-Identifier: AGPL-3.0
"""

import json
from datetime import datetime
from typing import  Any, List, Optional

from app.data.toml_schemas import ScriptTomlConfig, TriggersConfig
from playhouse.shortcuts import model_to_dict
from .model import db, Script, Config, Task, ensure_tables
from .schemas import ScriptEntity


class ScriptDatabase:
    """脚本库管理逻辑"""

    # 定义需要自动处理 JSON 的字段
    JSON_FIELDS = [
        'binaries', 'dependencies', 'inputs_schema', 'outputs_schema',
        'triggers_schema'
    ]

    @staticmethod
    def _parse_dict(data: dict) -> dict:
        """解析数据库返回的 dict，处理 JSON 和时间格式"""
        for field in ScriptDatabase.JSON_FIELDS:
            value = data.get(field)

            # 修复报错 2 & 3: 如果是字符串则解析，如果是 None 则赋空容器
            if isinstance(value, str) and value.strip():
                try:
                    data[field] = json.loads(value)
                except json.JSONDecodeError:
                    data[field] = [] if field != 'triggers_schema' else {}
            elif value is None:
                data[field] = [] if field != 'triggers_schema' else {}

        # 补丁：处理 badge 等可能为 None 的字符串字段
        if data.get('badge') is None: data['badge'] = ""
        if data.get('desc') is None: data['desc'] = ""

        return data

    @staticmethod
    def insert_or_update(script_info: dict):
        """插入或更新脚本 (适配最新字段名)"""
        ensure_tables()
        triggers = script_info.get('triggers', {})

        insert_data = {
            'id': script_info['id'],
            'name': script_info['name'],
            'icon': script_info.get('icon', ''),
            'version': script_info.get('version', '0.1.0'),
            'desc': script_info.get('desc', ''),
            'language': script_info['language'],
            'language_version': script_info.get('language_version', '0.0.0'),
            'entry': script_info['entry'],
            'terminal': script_info.get('terminal', 'never'),
            'binaries': json.dumps(script_info.get('binaries', [])),
            'dependencies': json.dumps(script_info.get('dependencies', [])),
            'inputs_schema': json.dumps(script_info.get('inputs', [])),
            'outputs_schema': json.dumps(script_info.get('outputs', [])),
            'workflow_enabled': script_info.get('workflow_enabled', True),
            'triggers_schema': json.dumps(triggers),
            'hotkey': script_info.get('hotkey'),
            'hotkey_active': script_info.get('hotkey_active', False),
            'quick_copy_active': script_info.get('quick_copy_active', False),
            'updated_at': datetime.now()
        }

        Script.insert(insert_data).on_conflict(
            conflict_target=[Script.id],
            update=insert_data
        ).execute()


    @staticmethod
    def get_all_scripts() -> List[ScriptEntity]:
        ensure_tables()
        scripts = Script.select().order_by(Script.pin.desc(), Script.created_at.desc())
        result = []
        for s in scripts:
            # 1. 转为 dict
            data = model_to_dict(s)
            # 2. 处理 JSON 字符串转 dict (已经在 _parse_dict 处理过)
            parsed_data = ScriptDatabase._parse_dict(data)
            # 3. 压入 Pydantic 模型进行校验和清洗
            result.append(ScriptEntity.model_validate(parsed_data))
        return result

    @staticmethod
    def get_script_by_id(script_id: str) -> Optional[ScriptEntity]:
        """根据脚本 ID 获取单个脚本详情"""
        ensure_tables()
        try:
            # 1. 从数据库查询
            script = Script.get_or_none(Script.id == script_id)
            if not script:
                return None

            # 2. 转换为字典并处理 JSON 字段
            data = model_to_dict(script)
            parsed_data = ScriptDatabase._parse_dict(data)

            # 3. 校验并转换为 Pydantic 模型
            return ScriptEntity.model_validate(parsed_data)
        except Exception as e:
            return None


    @staticmethod
    def update_status(script_id: str, field: str, value: Any):
        """通用的状态修改方法 (修改 pin, hotkey_active 等)"""
        ensure_tables()
        # 1. 执行原始更新
        field_obj = getattr(Script, field)
        query = Script.update({field_obj: value}).where(Script.id == script_id)
        query.execute()

        # 2. 增加联动清理逻辑
        if field == "hotkey" and value is None:
            Script.update(hotkey_active=False).where(Script.id == script_id).execute()

    @staticmethod
    def update_run_stats(script_id: str):
        """更新运行次数和最后运行时间"""
        ensure_tables()
        Script.update(
            run_count=Script.run_count + 1,
            last_run_at=datetime.now()
        ).where(Script.id == script_id).execute()

    @staticmethod
    def delete_script(script_id: str):
        """根据 ID 删除脚本"""
        ensure_tables()
        if Script.delete().where(Script.id == script_id).execute():
            return True
        else:
            return False

    @staticmethod
    def from_config_model(config: ScriptTomlConfig, badge:str=''):
        """
        直接从校验成功的 Pydantic 模型对象构造数据库 Script 模型
        """
        ensure_tables()
        info = config.info
        runtime = config.runtime
        triggers = config.triggers or TriggersConfig()

        # 2. 构造入库字典
        data = {
            'id': str(info.id),  # UUID 转字符串存入数据库
            'name': info.name,
            'icon': info.icon,
            'version': info.version,
            'desc': info.desc,
            'badge': badge,

            'language': runtime.language,
            'language_version': runtime.language_version,  # 别忘了新加的字段
            'entry': runtime.entry,
            'terminal': runtime.terminal,
            # Pydantic 对象转 JSON 字符串
            'binaries': json.dumps(runtime.binaries),

            'inputs_schema': json.dumps([i.model_dump() for i in config.inputs]),
            'outputs_schema': json.dumps([o.model_dump() for o in config.outputs]),
            'workflow_enabled': config.workflow.get("workflow_enabled", True),

            # 触发器配置直接 model_dump 序列化
            'triggers_schema': json.dumps(triggers.model_dump()),

            # 冗余字段用于快速查询
            'hotkey': triggers.shortcut.hotkey if hasattr(triggers.shortcut, 'hotkey') else None,
            'hotkey_active': triggers.shortcut.enabled,
            'quick_copy_active': triggers.quick_copy.enabled,

            'updated_at': datetime.now()
        }

        # 3. 执行插入/更新
        return Script.insert(data).on_conflict_replace().execute()


class ConfigDatabase:
    """全局配置管理逻辑"""

    @staticmethod
    def get_all() -> dict:
        """获取全部配置"""
        ensure_tables()
        config, _ = Config.get_or_create(id=1)
        data = model_to_dict(config)
        # 解析快捷键列表
        if data.get('shortcut_key_rouse'):
            data['shortcut_key_rouse'] = json.loads(data['shortcut_key_rouse'])
        return data

    @staticmethod
    def update_item(key: str, value: Any):
        """更新单个配置项"""
        ensure_tables()
        config = Config.get_or_create(id=1)[0]
        if key == "shortcut_key_rouse" and isinstance(value, list):
            value = json.dumps(value)
        setattr(config, key, value)
        config.save()



class TaskDatabase:
    """定时任务数据库操作类"""

    @staticmethod
    def create_task(task_data: dict) -> dict:
        """创建定时任务"""
        ensure_tables()
        try:
            task = Task.create(
                task_name=task_data['task_name'],
                task_type=task_data['task_type'],
                script_id=task_data['script_id'],
                icon = task_data['icon'],
                is_active=task_data.get('is_active', True),
                task_parameter=json.dumps(task_data.get("task_parameter", [])),
                task_parameter_type=task_data.get('task_parameter_type'),
                interval_minutes=task_data.get('interval_minutes'),
                min_interval_minutes=task_data.get('min_interval_minutes'),
                max_interval_minutes=task_data.get('max_interval_minutes'),
                delay_minutes=task_data.get('delay_minutes'),
                daily_time=task_data.get('daily_time'),
                weekly_weekday=task_data.get('weekly_weekday'),
                weekly_time=task_data.get('weekly_time'),
                updated_time=datetime.now()
            )

            return TaskDatabase._task_to_dict(task)

        except Exception as e:
            raise ValueError(f"创建定时任务失败: {str(e)}")

    @staticmethod
    def update_task(task_id: int, task_data: dict) -> dict:
        """更新定时任务"""
        ensure_tables()
        try:
            task = Task.get_or_none(Task.task_id == task_id)
            if not task:
                raise ValueError(f"任务 {task_id} 不存在")

            # 更新字段
            update_fields = {
                'task_name': task_data.get('task_name', task.task_name),
                'task_type': task_data.get('task_type', task.task_type),
                'script_id': task_data.get('script_id', task.script_id),
                'icon': task_data.get('icon', task.icon),
                'is_active': task_data.get('is_active', task.is_active),
                "task_parameter": json.dumps(task_data.get("task_parameter")) if task_data.get(
                    "task_parameter") else task.task_parameter,
                'task_parameter_type': task_data.get('task_parameter_type', task.task_parameter_type),
                'interval_minutes': task_data.get('interval_minutes', task.interval_minutes),
                'min_interval_minutes': task_data.get('min_interval_minutes', task.min_interval_minutes),
                'max_interval_minutes': task_data.get('max_interval_minutes', task.max_interval_minutes),
                'delay_minutes': task_data.get('delay_minutes', task.delay_minutes),
                'daily_time': task_data.get('daily_time', task.daily_time),
                'weekly_weekday': task_data.get('weekly_weekday', task.weekly_weekday),
                'weekly_time': task_data.get('weekly_time', task.weekly_time),
                'updated_time': datetime.now()
            }

            # 执行更新
            Task.update(**update_fields).where(Task.task_id == task_id).execute()

            # 返回更新后的任务
            updated_task = Task.get(Task.task_id == task_id)
            return TaskDatabase._task_to_dict(updated_task)

        except Exception as e:
            raise ValueError(f"更新定时任务失败: {str(e)}")

    @staticmethod
    def get_task(task_id: int) -> Optional[dict]:
        """根据ID获取定时任务"""
        ensure_tables()
        task = Task.get_or_none(Task.task_id == task_id)
        if task:
            data = model_to_dict(task, backrefs=False)
            data['task_parameter'] = json.loads(data['task_parameter'])
            return data
        return None

    def get_task_by_name(self, task_name: str) -> Optional[dict]:
        """根据任务名称获取定时任务"""
        ensure_tables()
        task = Task.get_or_none(Task.task_name == task_name)
        if task:
            data = model_to_dict(task, backrefs=False)
            data['task_parameter'] = json.loads(data['task_parameter'])
            return data
        return None

    @staticmethod
    def get_all_tasks() -> list:
        """获取所有定时任务"""
        ensure_tables()
        tasks = Task.select().order_by(Task.created_time.desc())
        tasks_data = []
        for task in tasks:
            data = model_to_dict(task, backrefs=False)
            data['task_parameter'] = json.loads(data['task_parameter'])
            tasks_data.append(data)

        return tasks_data

    @staticmethod
    def get_active_tasks() -> list:
        """获取所有启用的定时任务"""
        ensure_tables()
        tasks = Task.select().where(Task.is_active == True).order_by(Task.created_time.desc())
        tasks_data = []
        for task in tasks:
            data = model_to_dict(task, backrefs=False)
            data['task_parameter'] = json.loads(data['task_parameter'])
            tasks_data.append(data)

        return tasks_data

    @staticmethod
    def delete_task(task_id: int) -> bool:
        """删除定时任务"""
        ensure_tables()
        task = Task.get_or_none(Task.task_id == task_id)
        if task:
            task.delete_instance()
            return True
        return False

    @staticmethod
    def delete_task_by_script_id(script_id: str) -> bool:
        ensure_tables()
        # 删除所有匹配的记录
        deleted_count = Task.delete().where(Task.script_id == script_id).execute()
        return deleted_count > 0

    @staticmethod
    def toggle_task_status(task_id: int) -> dict:
        """切换任务启用状态"""
        ensure_tables()
        task = Task.get_or_none(Task.task_id == task_id)
        if not task:
            raise ValueError(f"任务 {task_id} 不存在")

        task.is_active = not task.is_active
        task.updated_time = datetime.now()
        task.save()

        return TaskDatabase._task_to_dict(task)

    @staticmethod
    def _task_to_dict(task: Task) -> dict:
        """将Task对象转换为字典"""
        data = model_to_dict(task, backrefs=False)
        data['task_parameter'] = json.loads(data['task_parameter'])

        # 格式化时间字段
        if 'created_time' in data:
            data['created_time'] = data['created_time'].isoformat()
        if 'updated_time' in data:
            data['updated_time'] = data['updated_time'].isoformat()

        return data


