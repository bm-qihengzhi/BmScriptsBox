"""
Copyright (c) 2026 綦恒智
Email: bmscriptsbox@163.com
SPDX-License-Identifier: MIT
SPDX-License-Identifier: LicenseRef-Commons-Clause

兼容入口：设置页已拆分为 ConfigCenter 中的独立节点。
"""
from .settings_controller import SettingsController


class SettingWidget(SettingsController):
    """已废弃：请使用 SettingsController。"""


__all__ = ["SettingWidget", "SettingsController"]
