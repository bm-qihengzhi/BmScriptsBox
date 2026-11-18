"""
Copyright (c) 2026 綦恒智
Email: bmscriptsbox@163.com
SPDX-License-Identifier: MIT
SPDX-License-Identifier: LicenseRef-Commons-Clause

命令面板内置的系统工具与 Windows 设置目录。
"""
import os
import shutil
from pathlib import Path
from typing import List

from xsideui import IconName

from app.servers.launcher.dedupe import system_dedupe_key
from app.servers.launcher.models import SearchItem


def _system_exe(name: str) -> str:
    root = os.environ.get("SystemRoot", r"C:\Windows")
    return str(Path(root) / "System32" / name)


def _tool(item_id, title, aliases, path, icon, subtitle="系统工具") -> SearchItem:
    return SearchItem(
        id="tool:%s" % item_id,
        kind="tool",
        title=title,
        subtitle=subtitle,
        provider="system",
        payload={"type": "path", "path": path},
        icon_path=path,
        icon_name=icon,
        keywords=list(aliases),
        dedupe_key=system_dedupe_key(item_id),
    )


def _setting(item_id, title, aliases, uri) -> SearchItem:
    return SearchItem(
        id="setting:%s" % item_id,
        kind="setting",
        title=title,
        subtitle="系统设置",
        provider="system",
        payload={"type": "uri", "uri": uri},
        icon_name=IconName.SETTING,
        keywords=list(aliases),
        dedupe_key="settings" if item_id == "home" else "",
    )


def system_items() -> List[SearchItem]:
    items = []

    tools = [
        ("taskmgr", "任务管理器", ["taskmgr", "task manager", "renwu"], "taskmgr.exe", IconName.APPLICATION),
        ("control", "控制面板", ["control", "control panel", "kongzhi"], "control.exe", IconName.SETTING),
        ("cmd", "命令提示符", ["cmd", "command prompt", "mingling"], "cmd.exe", IconName.TERMINAL),
        ("powershell", "PowerShell", ["powershell", "ps", "shell"], "WindowsPowerShell/v1.0/powershell.exe", IconName.TERMINAL),
        ("regedit", "注册表编辑器", ["regedit", "registry", "zhucebiao"], "regedit.exe", IconName.TOOL),
        ("services", "服务", ["services", "service", "fuwu"], "services.msc", IconName.TOOL),
        ("eventvwr", "事件查看器", ["eventvwr", "event viewer", "shijian"], "eventvwr.exe", IconName.TOOL),
        ("devmgmt", "设备管理器", ["devmgmt", "device manager", "shebei"], "devmgmt.msc", IconName.TOOL),
        ("diskmgmt", "磁盘管理", ["diskmgmt", "disk management", "cipan"], "diskmgmt.msc", IconName.TOOL),
        ("taskschd", "任务计划程序", ["taskschd", "task scheduler", "renwu jihua"], "taskschd.msc", IconName.TOOL),
        ("compmgmt", "计算机管理", ["compmgmt", "computer management", "jisuanji"], "compmgmt.msc", IconName.TOOL),
        ("perfmon", "性能监视器", ["perfmon", "performance monitor", "xingneng"], "perfmon.exe", IconName.TOOL),
        ("mstsc", "远程桌面连接", ["mstsc", "remote desktop", "yuancheng"], "mstsc.exe", IconName.WINDOWS),
        ("explorer", "文件资源管理器", ["explorer", "file explorer", "wenjian"], "explorer.exe", IconName.FOLDER),
        ("notepad", "记事本", ["notepad", "notepad", "jishiben"], "notepad.exe", IconName.APPLICATION),
        ("calc", "计算器", ["calc", "calculator", "jisuanqi"], "calc.exe", IconName.APPLICATION),
        ("mspaint", "画图", ["mspaint", "paint", "huatu"], "mspaint.exe", IconName.APPLICATION),
        ("snippingtool", "截图工具", ["snippingtool", "snip", "jietu"], "SnippingTool.exe", IconName.APPLICATION),
    ]

    for item_id, title, aliases, name, icon in tools:
        if "/" in name:
            path = _system_exe(name)
        else:
            path = _system_exe(name)
        resolved = path if path and Path(path).exists() else (shutil.which(name) or "")
        if resolved:
            items.append(_tool(item_id, title, aliases, resolved, icon))

    for item_id, title, aliases, name in [
        ("appwiz", "程序和功能", ["appwiz", "programs and features", "chengxu"], "appwiz.cpl"),
        ("desk", "显示设置", ["desk", "display", "xianshi"], "desk.cpl"),
        ("sysdm", "系统属性", ["sysdm", "system properties", "xitong"], "sysdm.cpl"),
        ("ncpa", "网络连接", ["ncpa", "network connections", "wangluo"], "ncpa.cpl"),
        ("powercfg", "电源选项", ["powercfg", "power options", "dianyuan"], "powercfg.cpl"),
        ("mmsys", "声音设置", ["mmsys", "sound", "shengyin"], "mmsys.cpl"),
        ("timedate", "日期和时间", ["timedate", "date and time", "shijian"], "timedate.cpl"),
        ("firewall", "Windows 防火墙", ["firewall", "fanghuoqiang"], "firewall.cpl"),
    ]:
        path = _system_exe(name)
        resolved = path if Path(path).exists() else (shutil.which(name) or "")
        if resolved:
            items.append(_tool(item_id, title, aliases, resolved, IconName.SETTING, "控制面板"))

    settings = [
        ('home', '设置', ['settings', 'shezhi']),
        ("display", "显示", ["display", "xianshi"]),
        ("sound", "声音", ["sound", "shengyin"]),
        ("notifications", "通知和操作", ["notifications", "tongzhi"]),
        ("powersleep", "电源和睡眠", ["power", "sleep", "dianyuan"]),
        ("battery", "电池", ["battery", "dianchi"]),
        ("network", "网络和 Internet", ["network", "internet", "wangluo"]),
        ("wifi", "Wi-Fi", ["wifi", "wireless", "wuxian"]),
        ("bluetooth", "蓝牙", ["bluetooth", "lanya"]),
        ("appsfeatures", "应用和功能", ["apps", "applications", "yingyong"]),
        ("defaultapps", "默认应用", ["default apps", "moren"]),
        ("windowsupdate", "Windows 更新", ["windows update", "update", "gengxin"]),
        ("privacy", "隐私", ["privacy", "yinsi"]),
        ("personalization", "个性化", ["personalization", "theme", "zhuti"]),
        ("datetime", "日期和时间", ["date time", "shijian"]),
        ("language", "语言和区域", ["language", "region", "yuyan"]),
        ("gaming", "游戏", ["gaming", "game", "youxi"]),
    ]
    for item_id, title, aliases in settings:
        uri = "ms-settings:" if item_id == "home" else "ms-settings:%s" % item_id
        items.append(_setting(item_id, title, aliases, uri))

    return items
