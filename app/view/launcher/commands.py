"""
Copyright (c) 2026 綦恒智
Email: bmscriptsbox@163.com
SPDX-License-Identifier: MIT
SPDX-License-Identifier: LicenseRef-Commons-Clause

启动器中的配置中心导航命令。
"""
from xsideui import IconName, XI18N

from app.servers.launcher.models import SearchItem
from app.view.config_center.nav_spec import NavId

NAV_PREFIX = "nav:"

_COMMANDS = [
    (NavId.SCRIPTS_INSTALLED, "Installed Scripts", "Manage installed scripts",
     IconName.CODE, ("scripts", "installed", "脚本", "已安装")),
    (NavId.SCRIPTS_MARKET, "Script Market", "Browse the script market",
     IconName.APPLICATION, ("market", "store", "市场", "商店")),
    (NavId.SCRIPTS_PUBLISH, "Publish Script",
     "Publish script to community", IconName.UPLOAD,
     ("publish", "developer", "发布", "开发者")),
    (NavId.SCRIPTS_UPDATE, "Script Update", "Check for script updates",
     IconName.UPDATE, ("update", "更新", "脚本更新")),
    (NavId.AUTO_CONTEXT, "Context Menu Trigger", "Manage context menu triggers",
     IconName.MOUSE, ("context", "menu", "右键", "菜单")),
    (NavId.AUTO_HOTKEY, "Hotkey Trigger", "Manage global hotkeys",
     IconName.KEYBOARD, ("hotkey", "快捷键")),
    (NavId.AUTO_FAST_COPY, "Super Copy Trigger", "Manage Super Copy triggers",
     IconName.CLIPBOARD, ("copy", "clipboard", "复制", "超级复制")),
    (NavId.AUTO_SCHEDULER, "Scheduled", "Manage scheduled tasks",
     IconName.HISTORY, ("scheduler", "task", "定时", "任务")),
    (NavId.SYS_BASIC, "Settings", "Open settings",
     IconName.SETTING, ("setting", "settings", "设置", "基础")),
    (NavId.SYS_ACCOUNT, "Account", "Sign in or manage your account", IconName.ME,
     ("account", "user", "login", "账号", "登录")),
    (NavId.SYS_CHECK_UPDATE, "Updates", "Check for software updates",
     IconName.UPDATE, ("update", "版本", "检查更新")),
]

_BY_ID = {spec[0]: spec for spec in _COMMANDS}


def _make(nav_id):
    target, title, subtitle, icon, keywords = _BY_ID[nav_id]
    title_text = XI18N.x_tr(title, context='BmscriptsBox')
    subtitle_text = XI18N.x_tr(subtitle, context='BmscriptsBox')
    return SearchItem(
        id="nav:%s" % target,
        kind="command",
        title=title_text,
        subtitle=subtitle_text,
        provider="palette",
        payload=NAV_PREFIX + target,
        icon_name=icon.value if hasattr(icon, "value") else str(icon),
        keywords=list(keywords),
        tooltip=subtitle_text,
    )


def make(nav_id):
    return _make(nav_id) if nav_id in _BY_ID else None


def default_commands():
    return []


def matching_commands(query, limit=6):
    text = (query or "").strip().lower()
    if not text:
        return []
    matched = []
    for nav_id, title, subtitle, icon, keywords in _COMMANDS:
        haystack = " ".join((nav_id, title, subtitle, *keywords)).lower()
        if text in haystack:
            matched.append(_make(nav_id))
        if len(matched) >= limit:
            break
    return matched


def target_of(item):
    payload = getattr(item, "payload", "")
    if isinstance(payload, str) and payload.startswith(NAV_PREFIX):
        return payload[len(NAV_PREFIX):]
    return None
