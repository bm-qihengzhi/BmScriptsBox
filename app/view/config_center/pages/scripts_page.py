"""
Copyright (c) 2026 綦恒智
Email: bmscriptsbox@163.com
SPDX-License-Identifier: MIT
SPDX-License-Identifier: LicenseRef-Commons-Clause

配置中心「已安装脚本」页。
"""
from app.view.config_center.nav_spec import NavId
from app.view.script_ui import ScriptsWidget


class ScriptsPage(ScriptsWidget):
    def __init__(self, presenter, navigator, parent=None):
        super().__init__(presenter=presenter, auto_load=False,
                         connect_scripts=False)
        self.setParent(parent)
        self._navigator = navigator
        self.ScriptHub.connect(
            lambda: navigator.navigate(NavId.SCRIPTS_MARKET))
        self.global_search_requested.connect(navigator.show_launcher)
        self.login_signal.connect(
            lambda _: navigator.show_config(NavId.SYS_ACCOUNT))
        self.load_banner()

    def refresh(self):
        self.presenter.refresh_scripts()

    def shutdown(self):
        self.cancel_preload()
