"""
Copyright (c) 2026 綦恒智
Email: bmscriptsbox@163.com
SPDX-License-Identifier: AGPL-3.0
"""
import json
import webbrowser

from PySide2.QtCore import Signal, QObject

from app.data import ScriptEntity
from app.utils import BmNotify, BmTools, BM_LOG


class ScriptPresenter(QObject):
    """脚本逻辑处理器 - 负责业务逻辑处理"""

    scripts_loaded = Signal(list)
    banner_loaded = Signal(list)
    banner_clicked = Signal(str)

    def __init__(self):
        super().__init__()
        self.banner_data = None
        self._script_work_thread = None
        self._execute_workers = {}
        self.uninstall = None

    def lazy_loading(self):
        self._load_banner()
        self._load_scripts()

    def _load_banner(self):
        resources_path = BmTools.get_resources_path()
        try:
            banner_path = resources_path / "banner.json"
            if not banner_path.exists():
                return
            with open(banner_path, "r", encoding="utf-8") as f:
                self.banner_data = json.load(f)
                banner_list = []
                for item in self.banner_data.get("banners", []):
                    banner_list.append(str(resources_path / "banner_images" / item["img"]))
                self.banner_loaded.emit(banner_list)
        except Exception as e:
            raise Exception(f"添加banner图片失败: {e}")

    def _load_scripts(self):
        from app.works.script_work import ReadScriptsThread
        self._script_work_thread = ReadScriptsThread()
        self._script_work_thread.get_scripts_signal.connect(self._on_scripts_loaded)
        self._script_work_thread.start()

    def _on_scripts_loaded(self, scripts_data: list):
        self.scripts_loaded.emit(scripts_data)

    def filter_scripts(self, filter_text, all_scripts):
        if not filter_text:
            return all_scripts
        filter_text = filter_text.lower().strip()
        return [
            script for script in all_scripts
            if filter_text in script.name.lower()
        ]

    def on_banner_clicked(self, index):
        if not self.banner_data:
            return
        link = self.banner_data.get("banners", [{}])[index].get("link")
        if link:
            webbrowser.open_new_tab(link)
            self.banner_clicked.emit(link)

    def refresh_scripts(self):
        self._load_scripts()

    def _on_uninstall_script(self, data):
        if data.get('state'):
            self.refresh_scripts()
            BmNotify().show_success_notify(content='卸载完成', in_window=True)
            return
        else:
            BmNotify().show_error_notify(content='卸载失败', in_window=True)
            return

    def execute_script(self,script_id):
        from app.data import ProjectGlobal, ScriptDatabase
        with ProjectGlobal.RUNNING_SCRIPTS_LOCK:
            if script_id in ProjectGlobal.RUNNING_SCRIPTS:
                BM_LOG.warning(f"脚本 {script_id} 正在执行中，跳过重复触发")
                entity = ScriptDatabase.get_script_by_id(script_id)
                name = entity.name if entity else script_id
                BmNotify().show_warning_notify(f"脚本「{name}」正在运行中，请等待完成")
                return
        from app.works.script_work import ExecuteScriptWork
        worker = ExecuteScriptWork(script_id)
        worker.execute_signal.connect(self._on_executed)
        worker.finished.connect(lambda sid=script_id: self._execute_workers.pop(sid, None))
        self._execute_workers[script_id] = worker
        worker.start()

    def uninstall_script(self, script_id):
        from app.works.script_work import UninstallScriptWork
        self.uninstall =UninstallScriptWork(script_id)
        self.uninstall.finished_signal.connect(self._on_uninstall_script)
        self.uninstall.start()

    def _on_executed(self,state):
        BmNotify().show_info_notify(content='正在执行脚本')

