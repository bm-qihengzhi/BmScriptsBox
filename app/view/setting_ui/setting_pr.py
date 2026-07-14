"""
Copyright (c) 2026 綦恒智
Email: bmscriptsbox@163.com
SPDX-License-Identifier: AGPL-3.0
"""
import json
import os
import sys
import webbrowser
import winreg
import subprocess
from pathlib import Path

from PySide2.QtCore import QThread, Signal, QTimer


from xsideui import XLoadingMask, XNotif, XI18N, theme_manager

from app.data import ScriptDatabase, ProjectGlobal, ConfigDatabase, TaskDatabase
from app.utils import BmNotify, async_logger_manager, BmTools, BM_LOG
from app.servers.monitor import get_double_monitor
from app.servers.packages import PackagesManager



class SettingPresenter:
    """软件设置"""
    def __init__(self, view):
        self.config_work = None
        self.view = view
        self.db = None
        self.get_config_work()


    def get_config_work(self):
        """
        获取软件配置
        """
        self.config_work = ReadConfigThread()
        self.config_work.start()
        self.config_work.finished.connect(self.view.update_setting)

    def update_language(self, index):
        """设置软件语言"""
        if index == 0:
            XI18N.set_language('zh_CN')
        else:
            XI18N.set_language('en_US')


        language = XI18N.current_lang
        ProjectGlobal.LANGUAGE = language
        config_path = BmTools.get_resources_path() / 'configs.json'
        if not config_path.exists():
            BM_LOG.error('No configs.json found')
            BmNotify().show_error_notify('save language failed')
            return
        try:
            with open(str(config_path), 'r', encoding='utf-8') as json_file:
                json_data = json.load(json_file)
                json_data['LANGUAGE'] = language

                # 将修改后的数据写回文件
                with open(str(config_path), 'w', encoding='utf-8') as json_file:
                    json.dump(json_data, json_file, indent=2, ensure_ascii=False)

        except Exception as e:
            BmNotify().show_error_notify('save language failed')


    def update_theme(self, index):
        """明暗切换"""
        if index == 0:
            theme_manager.set_theme('light')
        else:
            theme_manager.set_theme('dark')



    def update_hotkey(self, index):
        hotkey = self.view.hotkey_combo.currentText()
        ConfigDatabase.update_item('shortcut_key_rouse', [hotkey.lower()])
        # 热更新
        get_double_monitor().update_configs(new_keys=[hotkey])

    def update_setting(self, state,  name):
        ConfigDatabase.update_item(name, state)
        ProjectGlobal.CONFIG = ConfigDatabase.get_all()

    def check_log(self):
        """
        查看日志
        """
        async_logger_manager.open_log_file()

    def clear_log(self):
        """
        清空日志
        """
        try:
            async_logger_manager.clear_log_content()
            BmNotify().show_success_notify('日志已清空',in_window = True, position=XNotif.Pos.CENTER)
        except Exception as e:
            BM_LOG.error(f'清理日志失败:{e}')
            BmNotify().show_error_notify('清理日志失败',in_window = True, position=XNotif.Pos.CENTER)


    def clean_cache(self):
        """
        清理未使用的依赖缓存
        """
        try:
            uv_path = PackagesManager().get_uv()
            base_path = BmTools.get_root_path()
            cmd = [uv_path, 'cache', 'prune']
            subprocess.Popen(
                cmd,  # 使用cmd显式调用
                cwd=base_path,
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
            )
            BmNotify().show_success_notify('缓存已清理', in_window=True, position=XNotif.Pos.CENTER)
        except Exception as e:
            BM_LOG.error(f'清理缓存失败:{e}')
            BmNotify().show_error_notify('清理缓存失败', in_window=True, position=XNotif.Pos.CENTER)



    def add_to_startup(self, state):
        """添加到启动项"""
        if state:
            self._add_to_startup_registry()
        else:
            self._remove_from_startup_registry()


    def _add_to_startup_registry(self):
        """通过注册表添加到启动项"""
        try:
            key = winreg.HKEY_CURRENT_USER
            subkey = r"Software\Microsoft\Windows\CurrentVersion\Run"

            with winreg.OpenKey(key, subkey, 0, winreg.KEY_SET_VALUE) as reg_key:
                exe_path = Path(sys.executable)
                winreg.SetValueEx(reg_key, "BmScriptsBox", 0, winreg.REG_SZ, f'"{exe_path}"')
            self.update_setting(True, 'follow_start')
            return True
        except Exception as e:
            return False

    def _remove_from_startup_registry(self):
        """从注册表移除启动项"""
        try:
            key = winreg.HKEY_CURRENT_USER
            subkey = r"Software\Microsoft\Windows\CurrentVersion\Run"

            with winreg.OpenKey(key, subkey, 0, winreg.KEY_SET_VALUE) as reg_key:
                winreg.DeleteValue(reg_key, "BmScriptsBox")
            self.update_setting(False, 'follow_start')
            return True
        except Exception as e:
            return False







class ReadConfigThread(QThread):
    """
    读取配置文件线程
    """
    finished = Signal(dict)
    def __init__(self):
        super().__init__()
        self.db = None

    def run(self):
        if self.db is None:
            self.db = ConfigDatabase()
        config = self.db.get_all()
        ProjectGlobal.CONFIG = config
        self.finished.emit(config)


if __name__ == '__main__':
    from app.utils import BmTools
    log_path = BmTools.get_root_path() / 'BmLogs' / 'BmLogs.log'
    if log_path.exists():
        webbrowser.open(f"file://{log_path.absolute()}")