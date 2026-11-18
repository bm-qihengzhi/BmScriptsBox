"""
Copyright (c) 2026 綦恒智
Email: bmscriptsbox@163.com
SPDX-License-Identifier: MIT
SPDX-License-Identifier: LicenseRef-Commons-Clause

搜索结果的跨来源去重映射：同一 Windows 程序可能同时以应用和系统工具出现。
"""
from typing import Dict, List

from app.utils.pinyin_search import normalize

_DEDUPE_ALIASES: Dict[str, tuple] = {
    "calc": ("计算器", "Calculator", "Windows Calculator", "calc"),
    "notepad": ("记事本", "Notepad", "Windows Notepad", "notepad"),
    "paint": ("画图", "Paint", "mspaint"),
    "snippingtool": ("截图工具", "Snipping Tool", "ScreenSketch", "snip"),
    "explorer": ("文件资源管理器", "资源管理器", "File Explorer", "explorer"),
    "controlpanel": ("控制面板", "Control Panel", "control"),
    "mstsc": ("远程桌面", "远程桌面连接", "Remote Desktop",
              "Remote Desktop Connection", "mstsc"),
    "taskmgr": ("任务管理器", "Task Manager", "taskmgr"),
    "regedit": ("注册表编辑器", "Registry Editor", "regedit"),
    "cmd": ("命令提示符", "Command Prompt", "cmd"),
    "powershell": ("PowerShell", "Windows PowerShell", "pwsh"),
    "services": ("服务", "Services", "service"),
    "eventvwr": ("事件查看器", "Event Viewer", "eventvwr"),
    "devmgmt": ("设备管理器", "Device Manager", "devmgmt"),
    "diskmgmt": ("磁盘管理", "Disk Management", "diskmgmt"),
    "taskschd": ("任务计划", "任务计划程序", "Task Scheduler", "taskschd"),
    "compmgmt": ("计算机管理", "Computer Management", "compmgmt"),
    "perfmon": ("性能监视器", "Performance Monitor", "perfmon"),
    "settings": ("设置", "Settings", "Windows Settings"),
}

_ALIAS_TO_KEY: Dict[str, str] = {}
for _key, _aliases in _DEDUPE_ALIASES.items():
    for _alias in _aliases:
        _ALIAS_TO_KEY[normalize(_alias)] = _key

_UWP_APPID_KEYS = (
    ("microsoft.windowscalculator", "calc"),
    ("microsoft.windowsnotepad", "notepad"),
    ("microsoft.paint", "paint"),
    ("microsoft.screensketch", "snippingtool"),
    ("microsoft.windows.explorer", "explorer"),
    ("microsoft.remotedesktop", "mstsc"),
)

_SYSTEM_TOOL_KEYS = {
    "control": "controlpanel",
    "taskmgr": "taskmgr",
    "calc": "calc",
    "notepad": "notepad",
    "mspaint": "paint",
    "snippingtool": "snippingtool",
    "explorer": "explorer",
    "mstsc": "mstsc",
    "regedit": "regedit",
    "cmd": "cmd",
    "powershell": "powershell",
    "services": "services",
    "eventvwr": "eventvwr",
    "devmgmt": "devmgmt",
    "diskmgmt": "diskmgmt",
    "taskschd": "taskschd",
    "compmgmt": "compmgmt",
    "perfmon": "perfmon",
}


def app_dedupe_key(title: str, app_id: str = "") -> str:
    key = _ALIAS_TO_KEY.get(normalize(title))
    if key:
        return key
    lowered = (app_id or "").lower()
    for token, known_key in _UWP_APPID_KEYS:
        if token in lowered:
            return known_key
    return ""


def system_dedupe_key(item_id: str) -> str:
    return _SYSTEM_TOOL_KEYS.get(item_id, "")


def aliases_for_key(key: str) -> List[str]:
    if not key:
        return []
    return list(_DEDUPE_ALIASES.get(key, ()))
