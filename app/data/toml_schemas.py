"""
Copyright (c) 2026 綦恒智
Email: bmscriptsbox@163.com
SPDX-License-Identifier: AGPL-3.0
"""
import os
import re
from dataclasses import dataclass

from pydantic import BaseModel, Field, model_validator, ValidationInfo, field_validator
from typing import List, Dict, Any, Optional
from uuid import UUID



@dataclass
class ScriptLoadResult:
    """脚本加载结果的容器"""
    success: bool
    config: Optional[Any] = None  # 成功时的 Pydantic 对象
    error_messages: List[str] = None  # 失败时的友好错误描述



# --- 1. 基础信息子模型 ---
class ScriptInfo(BaseModel):
    id: UUID
    name: str = Field(min_length=1)
    desc: str = ""
    icon: str = ""
    version: str = Field(pattern=r'^\d+\.\d+\.\d+$')

    @field_validator('icon')
    @classmethod
    def check_not_absolute(cls, v: str) -> str:
        if os.path.isabs(v) or v.startswith('\\\\'):
            raise ValueError(
                "icon 必须是相对于脚本根目录的【相对路径】，不能使用绝对路径"
            )
        return v

    @model_validator(mode='after')
    def resolve_icon_path(self, info: ValidationInfo):
        script_dir = info.context.get("script_dir")
        if script_dir and self.icon and not os.path.isabs(self.icon):
            self.icon = os.path.normpath(os.path.join(script_dir, self.icon))
        return self


# --- 2. 运行时子模型 ---
class ScriptRuntime(BaseModel):
    language: str = Field(min_length=1)
    language_version: str
    entry: str = Field(min_length=1)
    terminal: str = "always"
    binaries: List[Dict[str, str]] = Field(default_factory=list)

    @field_validator('entry')
    @classmethod
    def check_not_absolute(cls, v: str) -> str:
        if os.path.isabs(v) or v.startswith('\\\\'):
            raise ValueError(
                "entry 必须是相对于脚本根目录的【相对路径】，不能使用绝对路径"
            )
        return v

    @model_validator(mode='after')
    def resolve_entry_path(self, info: ValidationInfo):
        script_dir = info.context.get("script_dir")
        if script_dir and self.entry and not os.path.isabs(self.entry):
            self.entry = os.path.normpath(os.path.join(script_dir, self.entry))
        return self

    @model_validator(mode='after')
    def validate_language_and_version(self):
        lang = self.language.lower()
        ver = self.language_version.strip()

        # 1. 如果是 bat，允许为空，直接通过
        if lang in ("bat", "html"):
            return self

        # 2. 如果是其他语言，必须填写版本号
        if not ver:
            raise ValueError(f"当编程语言为 '{self.language}' 时，必须填写 language_version")

        # 3. 校验版本号格式 (要求以比较运算符开头，如 >=3.8, ==3.10)
        # 正则解析：开头必须是 > 或 < 或 = 或 >= 或 <= 或 ==，后面跟着数字和点
        pattern = r'^(>=|<=|==|>|<)(?i:v)?\d+(\.\d+)*$'
        if not re.match(pattern, ver):
            raise ValueError(
                f"language_version 格式错误: '{ver}'。正确示例: '>=3.8'、'==3.10.1' 或 '>=v16.0'"
            )


        return self


# --- 3. 触发器子模型 (重点) ---
class ContextMenuConfig(BaseModel):
    enabled: bool = False
    targets: List[str] = Field(default_factory=list)
    filters: List[str] = Field(default_factory=list)


class ShortcutConfig(BaseModel):
    enabled: bool = False
    input_type: str = ''
    filters: List[str] = Field(default_factory=list)


class QuickCopyConfig(BaseModel):
    enabled: bool = False


class TriggersConfig(BaseModel):
    context_menu: ContextMenuConfig = Field(default_factory=ContextMenuConfig)
    shortcut: ShortcutConfig = Field(default_factory=ShortcutConfig)
    quick_copy: QuickCopyConfig = Field(default_factory=QuickCopyConfig)


# --- 4. IO 与 工作流 ---
class IOParam(BaseModel):
    name: str = ""
    type: str = ""
    exts: List[str] = Field(default_factory=list)
    description: str = ""


# --- 5. 顶层根模型 ---
class ScriptTomlConfig(BaseModel):
    info: ScriptInfo
    runtime: ScriptRuntime
    triggers: Optional[TriggersConfig] = None
    inputs: List[IOParam] = Field(default_factory=list)
    outputs: List[IOParam] = Field(default_factory=list)
    workflow: Dict[str, bool] = Field(default_factory=lambda: {"workflow_enabled": True})

    @model_validator(mode='after')
    def filter_empty_io(self):
        # 如果 name 和 type 都是空的，说明是占位符，直接过滤掉
        self.inputs = [i for i in self.inputs if i.name or i.type]
        self.outputs = [o for o in self.outputs if o.name or o.type]
        return self
