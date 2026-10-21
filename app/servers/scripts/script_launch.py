"""
Copyright (c) 2026 綦恒智
Email: bmscriptsbox@163.com
SPDX-License-Identifier: MIT
SPDX-License-Identifier: LicenseRef-Commons-Clause

统一脚本启动服务：收敛各触发入口（卡片/热键/超复/HTTP/定时）重复的
「原子查重 → 装载脚本 → 参数表单 → 构造 JSON → 运行 → 清理」逻辑，
消除跨线程竞态与临时文件泄漏。
"""
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

from app.data import ProjectGlobal, ScriptDatabase
from app.servers.scripts.script_run import ScriptRunner, ScriptNotFoundError
from app.utils import BM_LOG, ParameterManager
from app.utils.parameter_generate import build_launch_env


# 允许清理的临时参数文件名（本盒生成的 UUID.json / bms_*.json）
_SAFE_TEMP_NAME = re.compile(r'^(bms_)?[0-9a-fA-F-]{8,}\.json$')


class ScriptBusyError(Exception):
    """脚本已在运行中（原子占用失败）"""

    def __init__(self, script_id: str):
        super().__init__(f"脚本正在运行中: {script_id}")
        self.script_id = script_id


@dataclass
class LaunchContext:
    """一次已就绪的脚本启动：脚本信息 + 参数 JSON 路径 + 占用状态。"""

    script_id: str
    script_data: Any
    json_path: str
    invoke_mode: str = 'manual'
    owned_run_key: bool = False


class ScriptLaunchService:
    """各触发入口唯一的启动门面。"""

    # ------------------------------------------------------------ 原子占用
    @staticmethod
    def reserve(script_id: str) -> bool:
        """同锁"检查+占位"，成功返回 True（消除检查-注册竞态）"""
        with ProjectGlobal.RUNNING_SCRIPTS_LOCK:
            if script_id in ProjectGlobal.RUNNING_SCRIPTS:
                BM_LOG.warning(f"脚本已在运行中，拒绝重复启动: {script_id}")
                return False
            ProjectGlobal.RUNNING_SCRIPTS.add(script_id)
            return True

    @staticmethod
    def release(script_id: str) -> None:
        with ProjectGlobal.RUNNING_SCRIPTS_LOCK:
            ProjectGlobal.RUNNING_SCRIPTS.discard(script_id)

    # ------------------------------------------------------------ 装载与构造
    @staticmethod
    def _load(script_id: str):
        data = ScriptDatabase().get_script_by_id(script_id)
        if data is None:
            raise ScriptNotFoundError(f"脚本不存在或已被卸载: {script_id}")
        return data

    @classmethod
    def prepare(cls, script_id: str, *, data=None, params_overrides=None,
                params_defs=None, invoke_mode: str = 'manual',
                allow_params_form: bool = True, reserve_first: bool = True,
                holds_reservation: bool = False,
                parent=None, output_json: str = None, env_extra: dict = None,
                source: str = 'manual') -> Optional[LaunchContext]:
        """
        构造一次可运行的 LaunchContext。
        reserve_first=True 时先原子占用；用户取消 / 异常 → 自动释放占用并删除 JSON，
        返回 None 表示用户取消。

        holds_reservation: reserve_first=False 且调用方已自行 reserve() 时置 True，
        把占用所有权转交给本 ctx，由 cleanup() 统一释放（避免各入口重复实现释放逻辑）。
        """
        owned = False
        if reserve_first:
            if not cls.reserve(script_id):
                raise ScriptBusyError(script_id)
            owned = True
        elif holds_reservation:
            owned = True

        json_path = None
        try:
            script_data = cls._load(script_id)
            if isinstance(data, (list, tuple)):
                data_list = list(data)
            elif data is None:
                data_list = []
            else:
                data_list = [data]
            overrides = dict(params_overrides) if params_overrides else {}
            p_defs = params_defs if params_defs is not None else (script_data.params_schema or [])

            if allow_params_form and getattr(script_data, 'params_form_enabled', False):
                from app.view.script_ui.params_prompt import show_params_prompt
                res = show_params_prompt(script_data, data_list, parent=parent)
                if res is None:  # 用户取消 → 不启动
                    if owned:
                        cls.release(script_id)
                    return None
                data_list, overrides = res

            input_data = script_data.inputs_schema[0] if script_data.inputs_schema else {'name': 'source_path'}
            if env_extra is None:
                env_extra = build_launch_env(script_id, invoke_mode=invoke_mode)
            json_path = ParameterManager().construct_parameters(
                input_data, data_list,
                output_json=output_json,
                params_defs=p_defs,
                params_overrides=overrides,
                env_extra=env_extra,
            )
            if not json_path:
                raise RuntimeError('参数文件构造失败')

            return LaunchContext(
                script_id=script_id,
                script_data=script_data,
                json_path=str(json_path),
                invoke_mode=invoke_mode,
                owned_run_key=owned,
            )
        except Exception:
            if json_path:
                cls._safe_delete(str(json_path))
            if owned:
                cls.release(script_id)
            raise

    # ------------------------------------------------------------ 执行与收尾
    @staticmethod
    def run(ctx: LaunchContext, *, capture: bool = False, force_no_window: bool = False,
            timeout: float = None, sync: bool = False):
        if ctx is None:
            return None
        if sync:
            return ScriptRunner().run_script_sync(ctx.script_id, ctx.json_path, timeout=timeout)
        return ScriptRunner().run_script(
            ctx.script_id, ctx.json_path,
            capture=capture, force_no_window=force_no_window)

    @staticmethod
    def cleanup(ctx: Optional[LaunchContext]):
        """删除参数 JSON + 释放占用（幂等，务必在 finally 调用一次）"""
        if ctx is None:
            return
        try:
            ScriptLaunchService._safe_delete(ctx.json_path)
        finally:
            if getattr(ctx, 'owned_run_key', False):
                ScriptLaunchService.release(ctx.script_id)

    @staticmethod
    def _safe_delete(path: str):
        try:
            p = Path(path)
            if not p.is_file() or not _SAFE_TEMP_NAME.match(p.name):
                return
            p.unlink()
        except Exception:
            pass
