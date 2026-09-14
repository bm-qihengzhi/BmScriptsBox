"""
Copyright (c) 2026 綦恒智
Email: bmscriptsbox@163.com
SPDX-License-Identifier: MIT
SPDX-License-Identifier: LicenseRef-Commons-Clause
"""
import json
import tempfile
import uuid
from pathlib import Path

from typing import Any, List, Optional

from app.utils.log_manager import BM_LOG
from app.utils.tools import BmTools

DEFAULT_API_BASE = "http://127.0.0.1:9527"


def build_launch_env(script_id: str, api_base: str = DEFAULT_API_BASE,
                     script_dir: str = None, invoke_mode: str = "manual") -> dict:
    """
    构造注入脚本 environment 段的盒子上下文（脚本只读，供其作为联动发起方连回盒子）。
    invoke_mode：'manual'（手动触发，默认）/ 'node'（以节点形式被调用，须自动运行并写回信封）。
    不含身份 token，链接门禁收敛在 /api/link 的 is_node 校验。
    """
    return {
        "api_base": api_base,
        "task_id": uuid.uuid4().hex,
        "script_id": script_id,
        "script_dir": script_dir or str(BmTools.get_script_dir_path(script_id)),
        "invoke_mode": invoke_mode,
    }


class ParameterManager:

    def construct_parameters(self,
                             script_input_data: Optional[dict] = None,
                             data: Optional[List[str]] = None,
                             json_name: Optional[str] = None,
                             space: Optional[str] = None,
                             output_json: Optional[str] = None,
                             params_defs: Optional[List[dict]] = None,
                             params_overrides: Optional[dict] = None,
                             env_extra: Optional[dict] = None) -> Optional[Path]:
        """
        统一构建json格式参数文件（三段契约）
          environment — 盒子保留区（invoke_mode/output_json/api_base/task_id/script_id/script_dir等，脚本只读）
          data        — 触发/调用方喂的主数据（单键，键名取 inputs 的 name）
          params      — 脚本运行参数（toml 默认值 + 调用方覆盖）
        """
        try:
            if not isinstance(script_input_data, dict):
                script_input_data = {}
            if not isinstance(data, list):
                data = []
            parameter_name = script_input_data.get('name', 'source_path')

            environment = {
                'workspace': space,
                "output_json": output_json,
                "encoding": "utf-8",
            }
            if isinstance(env_extra, dict):
                environment.update(env_extra)

            parameters = {
                'environment': environment,
                'data': ({parameter_name: data} if data else {}),
                'params': self._merge_params(params_defs, params_overrides),
            }
            if not space:
                space = tempfile.gettempdir()
            if not json_name:
                json_name = f"{uuid.uuid4()}.json"
            json_path = Path(space) / json_name
            with open(json_path, 'w', encoding='utf-8') as f:
                json_str = json.dumps(parameters, ensure_ascii=False, indent=4)
                f.write(json_str)
            return json_path
        except Exception as e:
            BM_LOG.error(f"<参数构造报错>{e}")
            return None

    @staticmethod
    def _coerce(value: Any, ptype: str) -> Any:
        """按声明类型轻量强转；int/float/bool 强转失败则原样保留，list/dict 透传"""
        if value is None:
            return None
        try:
            if ptype == 'str':
                return str(value)
            if ptype == 'int':
                if isinstance(value, bool):
                    return value
                return int(value)
            if ptype == 'float':
                if isinstance(value, bool):
                    return value
                return float(value)
            if ptype == 'bool':
                if isinstance(value, bool):
                    return value
                if isinstance(value, (int, float)):
                    return value != 0
                if isinstance(value, str):
                    low = value.strip().lower()
                    if low in ('1', 'true', 'yes', 'on'):
                        return True
                    if low in ('0', 'false', 'no', 'off'):
                        return False
                return value
            if ptype in ('list', 'dict'):
                return value
        except (TypeError, ValueError):
            return value
        return value

    @staticmethod
    def _merge_params(params_defs: Optional[List[dict]],
                      params_overrides: Optional[dict]) -> dict:
        """params = toml 声明的默认值（按类型强转）被调用方覆盖；只保留已声明的参数名"""
        defs = {pd.get('name'): pd for pd in (params_defs or []) if isinstance(pd, dict) and pd.get('name')}
        merged = {}
        for name, pd in defs.items():
            merged[name] = ParameterManager._coerce(pd.get('default'), pd.get('type', 'str'))
        if isinstance(params_overrides, dict):
            for name, value in params_overrides.items():
                if name in defs:
                    merged[name] = ParameterManager._coerce(value, defs[name].get('type', 'str'))
        return merged



