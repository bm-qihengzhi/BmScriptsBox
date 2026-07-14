"""
Copyright (c) 2026 綦恒智
Email: bmscriptsbox@163.com
SPDX-License-Identifier: AGPL-3.0
"""
from pydantic import BaseModel, Field, ConfigDict
from typing import List, Optional, Dict, Any
from datetime import datetime


class ScriptEntity(BaseModel):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    # --- 1. 基础信息 (对应数据库固定字段) ---
    id: str
    name: str
    icon: str = ""
    version: str = "0.1.0"
    desc: str = ""
    badge: str = ""
    pin: bool = False

    # --- 2. 运行环境 ---
    language: str
    language_version:str
    entry: str
    terminal: str = "never"
    binaries: List[Dict[str, str]] = Field(default_factory=list)
    dependencies: List[str] = Field(default_factory=list)

    # --- 3. IO 契约 ---
    inputs_schema: List[Dict[str, Any]] = Field(default_factory=list)
    outputs_schema: List[Dict[str, Any]] = Field(default_factory=list)
    workflow_enabled: bool = True

    # --- 4. 触发器配置 (原始 JSON 存储) ---
    triggers_schema: Dict[str, Any] = Field(default_factory=dict)
    hotkey: Optional[str] = None
    hotkey_active: bool = False
    quick_copy_active: bool = False

    # --- 5. 审计信息 ---
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    run_count: int = 0
    last_run_at: Optional[datetime] = None

    # --- 6. 快捷访问属性 (Computed Fields) ---
    @property
    def is_context_enabled(self) -> bool:
        return self.triggers_schema.get("context_menu", {}).get("enabled", False)

    @property
    def context_targets(self) -> List[str]:
        return self.triggers_schema.get("context_menu", {}).get("targets", [])

    @property
    def is_shortcut_enabled(self) -> bool:
        return self.triggers_schema.get("shortcut", {}).get("enabled", False)

    @property
    def is_quick_copy_enabled(self) -> bool:
        return self.triggers_schema.get("quick_copy", {}).get("enabled", False)