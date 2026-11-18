"""
Copyright (c) 2026 綦恒智
Email: bmscriptsbox@163.com
SPDX-License-Identifier: MIT
SPDX-License-Identifier: LicenseRef-Commons-Clause

params 取值校验：必填非空 + str 取值命中 choices。
交互弹窗、定时任务、HTTP 接口三条入口共用同一口径。

另含 secret 字段处理：secret 只用于回显遮蔽，不落参数记忆（明文存储风险）。
"""
from typing import Any, Dict, List, Optional, Set


def is_blank(value: Any) -> bool:
    """空值判定：None / 纯空白字符串 / 空容器（False、0 视为有值）"""
    if value is None:
        return True
    if isinstance(value, str):
        return not value.strip()
    if isinstance(value, (list, tuple, dict, set)):
        return len(value) == 0
    return False


def secret_names(params_defs: Optional[List[Dict]]) -> Set[str]:
    """声明了 secret = true 的参数名集合"""
    return {pd['name'] for pd in (params_defs or [])
            if isinstance(pd, dict) and pd.get('name') and pd.get('secret')}


def strip_secret(values: Optional[Dict[str, Any]],
                 params_defs: Optional[List[Dict]]) -> Dict[str, Any]:
    """剔除 secret 字段：这类值不写参数记忆，避免 token / 密码明文落库"""
    if not isinstance(values, dict):
        return {}
    secrets = secret_names(params_defs)
    if not secrets:
        return dict(values)
    return {k: v for k, v in values.items() if k not in secrets}


def validate_params(params_defs: Optional[List[Dict]],
                    values: Optional[Dict[str, Any]]) -> Optional[str]:
    """按 params 声明校验实际取值；通过返回 None，否则返回可直接展示给用户的文案"""
    values = values if isinstance(values, dict) else {}
    for pd in params_defs or []:
        if not isinstance(pd, dict) or not pd.get('name'):
            continue
        name = pd['name']
        if pd.get('required') and is_blank(values.get(name)):
            return f"缺少必填参数: {name}"
        choices = pd.get('choices') or []
        if choices and str(pd.get('type', 'str')).lower() == 'str':
            val = values.get(name)
            if not is_blank(val) and str(val) not in [str(c) for c in choices]:
                return (f"参数 {name} 取值 '{val}' 不在可选范围: "
                        + ', '.join(str(c) for c in choices))
    return None
