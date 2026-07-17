"""
Copyright (c) 2026 綦恒智
Email: bmscriptsbox@163.com
SPDX-License-Identifier: AGPL-3.0
"""
import json
import locale
import sys
import ctypes
from pathlib import Path
from typing import List
from PySide2.QtNetwork import QLocalSocket
from xsideui import XI18N

from app.data import ProjectGlobal
from app.utils import BM_LOG


class BmTools:

    @staticmethod
    def get_root_path() -> Path:
        """获取项目根目录（存放 BmScripts/BmPackages/BmData 等运行时目录）"""
        return Path(__file__).parents[2]

    @staticmethod
    def get_resources_path() -> Path:
        """获取资源文件目录（configs.json/图片/i18n 等）"""
        return Path(__file__).parent.parent / 'resources'

    @staticmethod
    def get_script_dir_path(script_id: str) -> Path:
        """获取脚本目录路径"""
        return BmTools.get_root_path() / 'BmScripts' / script_id

    @staticmethod
    def get_temp_context(file_path: str) -> List[str]:
        """
        获取文件中一行一行的内容，返回列表

        Args:
            file_path: 文件路径

        Returns:
            去除换行符后的每行内容列表
        """
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                return [line.rstrip('\n') for line in f]
        except FileNotFoundError:
            return []


    @staticmethod
    def get_logo_path() -> str:
        """获取logo路径"""
        return str(BmTools.get_resources_path() / 'imgs' / 'logo.svg')

    @staticmethod
    def get_language_icon_path(language) -> str:
        """获取编程语言图标"""
        return str(BmTools.get_resources_path() / 'language' / f"{language}.png")

    @staticmethod
    def set_win32_logo():
        """设置 Windows 任务栏进程标识符以确保图标正确显示"""
        if sys.platform == 'win32':
            # 确保windows任务栏能正确显示图标，字符串标识符（格式：公司名.产品名.子模块.版本号）
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(
                '瞎忙软件开发工作室.不忙脚本盒子.不忙脚本盒子.v0.0.1')

    @staticmethod
    def get_base_scripts_path() -> Path:
        """返回BmScripts Path路径"""
        return BmTools.get_root_path() / 'BmScripts'

    @staticmethod
    def is_chinese_env() -> bool:
        """判断运行环境是否为中文"""
        lang, _ = locale.getdefaultlocale()
        if lang and lang.startswith('zh'):
            return True
        return False

    @staticmethod
    def set_language():
        """程序初始化时根据配置设置软件语言"""
        # 设置自定义语言包
        XI18N.add_custom_lang_path(str(BmTools.get_resources_path() / 'i18n'), 'BmscriptsBox')
        config_path = BmTools.get_resources_path() / 'configs.json'
        if not config_path.exists():
            BM_LOG.error("No configs.json found")
            return

        with open(config_path, "r", encoding="utf-8") as f:
            configs = json.load(f)
            language = configs.get("LANGUAGE")
            if not language:
                language = "zh_CN" if BmTools.is_chinese_env() else "en_US"
            ProjectGlobal.LANGUAGE = language
            XI18N.set_language(language)
            ProjectGlobal.PROXIES = configs.get("PROXIES", ProjectGlobal.PROXIES)

    @staticmethod
    def is_already_running(app_name):
        socket = QLocalSocket()
        socket.connectToServer(app_name)
        return socket.waitForConnected(500)



