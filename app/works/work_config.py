"""
Copyright (c) 2026 綦恒智
Email: bmscriptsbox@163.com
SPDX-License-Identifier: AGPL-3.0
"""
import json
from PySide2.QtCore import QThread, Signal
from app.data import ProjectGlobal
from app.utils import BmTools


class ConfigWork(QThread):
    config_error = Signal(str)
    config_loaded = Signal()

    def __init__(self, parent=None):
        super(ConfigWork, self).__init__(parent)

    def run(self):
        """
        运行
        """
        config_path = BmTools.get_resources_path() / "configs.json"
        if not config_path:
            self.config_error.emit("未找到配置文件")
            return
        with open(config_path, "r", encoding="utf-8") as f:
            try:
                configs = json.load(f)
            except json.JSONDecodeError as e:
                self.config_error.emit(f"配置文件解析失败: {e}")
                return
            ProjectGlobal.PROXIES = configs.get("PROXIES", ProjectGlobal.PROXIES)
            ProjectGlobal.LANGUAGE = configs.get("LANGUAGE", "zh_CN")
        self.config_loaded.emit()



