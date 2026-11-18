"""
Copyright (c) 2026 綦恒智
Email: bmscriptsbox@163.com
SPDX-License-Identifier: MIT
SPDX-License-Identifier: LicenseRef-Commons-Clause
"""
from xsideui import IconName, XIcon, XI18N, XMenu


def _t(text):
    return XI18N.x_tr(text, context='BmscriptsBox')


def build_tray_menu(parent, on_launcher, on_config, on_quit):
    menu = XMenu(parent)
    menu.add_action(_t('Open Launcher'),
                    XIcon.get(name=IconName.EYE_ON).icon(), on_launcher)
    menu.add_action(_t('Config Center'),
                    XIcon.get(name=IconName.SETTING).icon(), on_config)
    menu.add_action(_t('Quit'),
                    XIcon.get(name=IconName.POWER).icon(), on_quit)
    return menu
