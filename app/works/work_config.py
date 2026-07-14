"""
Copyright (c) 2026 綦恒智
Email: bmscriptsbox@163.com
SPDX-License-Identifier: AGPL-3.0
"""
import json
from pathlib import Path
from pprint import pprint

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
            ProjectGlobal.API_GATEWAY = configs.get("API_GATEWAY", "")
            ProjectGlobal.BANNER_DATA_URL = configs.get("BANNER_DATA_URL", "")
            ProjectGlobal.BM_BINARY_RESOURCE_UR = configs.get("BM_BINARY_RESOURCE_UR", "")
            ProjectGlobal.REMOTE_VERSION_URL = configs.get("REMOTE_VERSION_URL", "")
            ProjectGlobal.PROXIES = configs.get("PROXIES", ProjectGlobal.PROXIES)
            ProjectGlobal.LANGUAGE = configs.get("LANGUAGE", "zh_CN")
        self.config_loaded.emit()


if __name__ == '__main__':
    from app.utils import BmTools
    config_path = BmTools.get_resources_path() / "configs.json"
    with open(config_path, "r", encoding="utf-8") as f:
        config = json.load(f)
        print(type(config))
        pprint(config)
