"""
Copyright (c) 2026 綦恒智
Email: bmscriptsbox@163.com
SPDX-License-Identifier: MIT
SPDX-License-Identifier: LicenseRef-Commons-Clause

脚本右键菜单的公共构建逻辑。
"""
import webbrowser

from PySide6.QtCore import QUrl
from PySide6.QtGui import QDesktopServices

from xsideui import XColor, XIcon, XMenu, IconName, tr

from app.data import ProjectGlobal
from app.utils import BM_LOG, BmTools
from app.utils.badge import is_local_badge


def popup_script_menu(parent, script_info, position, on_run, on_uninstall,
                      on_changed=None):
    """在指定全局坐标弹出脚本操作菜单。"""
    menu = XMenu(parent)
    menu.add_action(
        icon=XIcon(IconName.PLAY, color=XColor.SUCCESS).icon(),
        text=tr('Run'),
        triggered=on_run,
    )
    menu.add_action(
        icon=XIcon(IconName.DELETE, color=XColor.DANGER).icon(),
        text=tr('Uninstall'),
        triggered=on_uninstall,
    )
    if script_info.pin:
        menu.add_action(
            text=tr('Unpin'),
            triggered=lambda: _toggle_pin(script_info, on_changed),
        )
    else:
        menu.add_action(
            icon=XIcon(IconName.PIN_FILL).icon(),
            text=tr('Pin'),
            triggered=lambda: _toggle_pin(script_info, on_changed),
        )
    menu.add_action(
        text=tr('Details'),
        icon=XIcon(IconName.INFO).icon(),
        triggered=lambda: _show_info(script_info),
    )
    if not is_local_badge(script_info.badge):
        menu.add_action(
            text=tr('Star'),
            icon=XIcon(IconName.STAR).icon(),
            triggered=lambda: _show_info(script_info),
        )
        menu.add_action(
            text=tr('Report'),
            icon=XIcon(IconName.REPORT).icon(),
            triggered=lambda: _show_info(script_info),
        )
    menu.add_action(
        text=tr('Open Location'),
        icon=XIcon(IconName.FOLDER).icon(),
        triggered=lambda: _show_folder(script_info),
    )
    menu.exec(position)


def _toggle_pin(script_info, on_changed):
    try:
        from app.data import ScriptDatabase

        ScriptDatabase().update_status(
            script_info.id, 'pin', not script_info.pin)
        if on_changed:
            on_changed()
    except Exception as exc:
        BM_LOG.error("切换脚本置顶失败: %s" % exc)


def _show_info(script_info):
    webbrowser.open_new_tab(
        ProjectGlobal.API_GATEWAY + '/detail/' + script_info.id)


def _show_folder(script_info):
    path = BmTools.get_base_scripts_path() / script_info.id
    if path.exists():
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(path.absolute())))
