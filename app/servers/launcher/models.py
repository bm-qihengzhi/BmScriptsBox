"""
Copyright (c) 2026 綦恒智
Email: bmscriptsbox@163.com
SPDX-License-Identifier: MIT
SPDX-License-Identifier: LicenseRef-Commons-Clause

命令面板的统一结果模型。
"""
from dataclasses import dataclass, field
from typing import Any, List, Optional


@dataclass
class SearchItem:
    id: str
    kind: str                 # script / script_input / app / uwp / setting / tool
    title: str
    subtitle: str
    provider: str
    payload: Any
    icon_path: str = ""
    icon_name: str = ""
    keywords: List[str] = field(default_factory=list)
    description: str = ""
    aux_text: str = ""
    pin: bool = False
    tooltip: Optional[str] = None
    norm_title: str = ""
    compact_title: str = ""
    norm_keywords: List[str] = field(default_factory=list)
    compact_keywords: List[str] = field(default_factory=list)
    norm_description: str = ""
    compact_description: str = ""
    norm_aux: str = ""
    compact_aux: str = ""
    usage_boost: float = 0.0
    pinyin_blob: str = ""
    dedupe_key: str = ""
    display_title: str = ""
    badge: str = ""
    status: str = ""
    state: str = ""
