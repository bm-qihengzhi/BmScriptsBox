"""
Copyright (c) 2026 綦恒智
Email: bmscriptsbox@163.com
SPDX-License-Identifier: MIT
SPDX-License-Identifier: LicenseRef-Commons-Clause
"""
import json
import webbrowser

from PySide6.QtCore import Signal, QObject
from xsideui import tr
from app.utils import BmNotify, BmTools, BM_LOG
from app.utils.pinyin_search import PinyinSearchIndex, HAS_PYPINYIN


class ScriptPresenter(QObject):
    """脚本逻辑处理器 - 负责业务逻辑处理"""

    scripts_loaded = Signal(list)
    banner_loaded = Signal(list)
    banner_clicked = Signal(str)

    def __init__(self):
        super().__init__()
        self.banner_data = None
        self._execute_workers = {}
        self._uninstall_workers = {}
        self._read_threads = set()
        self._search_index = PinyinSearchIndex()
        if not HAS_PYPINYIN:
            BM_LOG.warning("pypinyin 不可用，脚本卡片搜索仅支持原名匹配")

    def lazy_loading(self):
        self.load_banner()
        self.load_scripts()

    def load_banner(self):
        try:
            self._load_banner()
        except Exception as e:
            BM_LOG.error(f"加载 banner 失败: {e}")

    def load_scripts(self):
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
            BM_LOG.warning(f"添加banner图片失败: {e}")
            return

    def _load_scripts(self):
        from app.works.script_work import ReadScriptsThread
        thread = ReadScriptsThread()
        thread.get_scripts_signal.connect(self._on_scripts_loaded)
        thread.finished.connect(lambda t=thread: self._read_threads.discard(t))
        self._read_threads.add(thread)
        thread.start()

    def _on_scripts_loaded(self, scripts_data: list):
        self.scripts_loaded.emit(scripts_data)

    def filter_scripts(self, filter_text, all_scripts):
        if not filter_text or not filter_text.strip():
            return all_scripts
        return [
            script for script in all_scripts
            if self._search_index.matches(script.name, filter_text)
        ]

    def on_banner_clicked(self, index):
        if not self.banner_data:
            return
        banners = self.banner_data.get("banners", [])
        if not (0 <= index < len(banners)):
            return
        link = banners[index].get("link")
        if link:
            webbrowser.open_new_tab(link)
            self.banner_clicked.emit(link)

    def refresh_scripts(self):
        self._load_scripts()

    def shutdown(self):
        """退出前等待在读库线程结束，避免 QThread 在运行中被销毁"""
        for thread in list(self._read_threads):
            if thread.isRunning():
                thread.wait(2000)
        self._read_threads.clear()

    def _on_uninstall_script(self, data):
        if data.get('state'):
            self.refresh_scripts()
            BmNotify().show_success_notify(content=tr('Uninstalled'), in_window=True)
            return
        else:
            BmNotify().show_error_notify(content=tr('Uninstall failed'), in_window=True)
            return

    def execute_script(self, script_id, data=None, params_overrides=None,
                       source='card'):
        from app.servers.scripts import (
            ScriptLaunchService, ScriptBusyError, ScriptNotFoundError)
        from app.works.script_work import ExecuteScriptWork

        try:
            ctx = ScriptLaunchService.prepare(
                script_id, data=data, params_overrides=params_overrides,
                invoke_mode='manual', allow_params_form=True,
                reserve_first=True, source=source)
        except ScriptBusyError:
            BM_LOG.warning(f"脚本 {script_id} 正在执行中，跳过重复触发")
            BmNotify().show_warning_notify(tr("The script is running, please wait"))
            return
        except ScriptNotFoundError as e:
            BmNotify().show_error_notify(content=str(e))
            return
        if ctx is None:  # 参数表单被取消
            return

        worker = ExecuteScriptWork(ctx)
        worker.execute_signal.connect(self._on_executed)
        worker.finished.connect(lambda sid=script_id: self._execute_workers.pop(sid, None))
        self._execute_workers[script_id] = worker
        try:
            worker.start()
        except Exception as e:
            # 兜底：线程未能启动时释放占用并清理参数文件，避免脚本永久"运行中"
            self._execute_workers.pop(script_id, None)
            ScriptLaunchService.cleanup(ctx)
            BM_LOG.error(f"启动执行线程失败 {script_id}: {e}")
            BmNotify().show_error_notify(content=tr('Execution Failed'))

    def uninstall_script(self, script_id):
        from app.works.script_work import UninstallScriptWork
        if script_id in self._uninstall_workers:
            BM_LOG.warning(f"脚本 {script_id} 正在卸载中，跳过重复操作")
            return
        worker = UninstallScriptWork(script_id)
        worker.finished_signal.connect(self._on_uninstall_script)
        worker.finished.connect(lambda sid=script_id: self._uninstall_workers.pop(sid, None))
        self._uninstall_workers[script_id] = worker
        worker.start()

    def _on_executed(self, state):
        if state:
            BmNotify().show_info_notify(content=tr('Running script'))
        else:
            BmNotify().show_error_notify(content=tr('The script failed, see the log for details'))

