"""
Copyright (c) 2026 綦恒智
Email: bmscriptsbox@163.com
SPDX-License-Identifier: MIT
SPDX-License-Identifier: LicenseRef-Commons-Clause

配置中心导航 ID、节点声明与可见性。
"""
from xsideui import IconName, XI18N


def _t(text):
    return XI18N.x_tr(text, context='BmscriptsBox')


class NavId:
    CONFIG = "config"

    SCRIPTS_INSTALLED = "scripts.installed"
    SCRIPTS_MARKET = "scripts.market"
    SCRIPTS_PUBLISH = "scripts.publish"
    SCRIPTS_UPDATE = "scripts.update"

    AUTO_CONTEXT = "automation.context"
    AUTO_HOTKEY = "automation.hotkey"
    AUTO_FAST_COPY = "automation.fastcopy"
    AUTO_SCHEDULER = "automation.scheduler"

    SYS_BASIC = "system.basic"
    SYS_PUSH = "system.push"
    SYS_ACCOUNT = "system.account"
    SYS_ABOUT = "system.about"
    SYS_CHECK_UPDATE = "system.update"


GROUP_SCRIPTS = "group.scripts"
GROUP_AUTOMATION = "group.automation"
GROUP_SYSTEM = "group.system"

DEFAULT_NAV_ID = NavId.SCRIPTS_INSTALLED

ACTION_NAV_IDS = frozenset({NavId.SYS_CHECK_UPDATE})

PAGE_NAV_IDS = frozenset({
    NavId.SCRIPTS_INSTALLED,
    NavId.SCRIPTS_MARKET,
    NavId.SCRIPTS_PUBLISH,
    NavId.SCRIPTS_UPDATE,
    NavId.AUTO_CONTEXT,
    NavId.AUTO_HOTKEY,
    NavId.AUTO_FAST_COPY,
    NavId.AUTO_SCHEDULER,
    NavId.SYS_BASIC,
    NavId.SYS_PUSH,
    NavId.SYS_ACCOUNT,
    NavId.SYS_ABOUT,
})


def _leaf(nav_id, title, icon, keywords=(), action=False):
    return {
        "id": nav_id,
        "text": _t(title),
        "icon": icon,
        "keywords": tuple(keywords),
        "action": bool(action),
    }


def build_tree(visible_ids=None):
    """构造 XNavTree 节点配置；visible_ids 为 None 时展示全部。"""
    scripts = [
        _leaf(NavId.SCRIPTS_INSTALLED, "Installed Scripts", IconName.CODE,
              ("scripts", "installed", "脚本", "已安装")),
        _leaf(NavId.SCRIPTS_MARKET, "Script Market", IconName.APPLICATION,
              ("market", "store", "市场", "商店")),
        _leaf(NavId.SCRIPTS_PUBLISH, "Publish Script", IconName.UPLOAD,
              ("publish", "developer", "发布", "开发者")),
        _leaf(NavId.SCRIPTS_UPDATE, "Script Update", IconName.UPDATE,
              ("update", "更新", "脚本更新")),
    ]
    automation = [
        _leaf(NavId.AUTO_CONTEXT, "Context Menu", IconName.MOUSE,
              ("context", "menu", "右键", "菜单")),
        _leaf(NavId.AUTO_HOTKEY, "Hotkeys", IconName.KEYBOARD,
              ("hotkey", "快捷键")),
        _leaf(NavId.AUTO_FAST_COPY, "Super Copy", IconName.CLIPBOARD,
              ("copy", "clipboard", "复制", "超级复制")),
        _leaf(NavId.AUTO_SCHEDULER, "Scheduled", IconName.HISTORY,
              ("scheduler", "task", "定时", "任务")),
    ]
    system = [
        _leaf(NavId.SYS_BASIC, "Settings", IconName.SETTING,
              ("setting", "settings", "设置", "基础")),
        _leaf(NavId.SYS_ACCOUNT, "Account", IconName.ME,
              ("account", "user", "login", "账号", "登录")),
        _leaf(NavId.SYS_ABOUT, "About", IconName.INFO,
              ("about", "version", "关于", "版本")),
        _leaf(NavId.SYS_PUSH, "Push", IconName.MESSAGE,
              ("push", "wechat", "推送", "微信")),
        _leaf(NavId.SYS_CHECK_UPDATE, "Updates", IconName.UPDATE,
              ("update", "版本", "检查更新"), action=True),
    ]

    groups = [
        (GROUP_SCRIPTS, "Scripts", IconName.SYSTEM, scripts, True),
        (GROUP_AUTOMATION, "Triggers", IconName.OPTIONAL, automation, True),
        (GROUP_SYSTEM, "System", IconName.EQUALIZER, system, False),
    ]

    tree = []
    for group_id, title, icon, children, expanded in groups:
        if visible_ids is not None:
            children = [child for child in children
                        if child["id"] in visible_ids]
        if not children:
            continue
        tree.append({
            "id": group_id,
            "text": _t(title),
            "icon": icon,
            "navigable": False,
            "expanded": expanded,
            "children": children,
        })
    return tree


def all_leaf_ids():
    return [node["id"] for group in build_tree() for node in group["children"]]
