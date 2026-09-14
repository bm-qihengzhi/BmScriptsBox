"""
Copyright (c) 2026 綦恒智
Email: bmscriptsbox@163.com
SPDX-License-Identifier: MIT
SPDX-License-Identifier: LicenseRef-Commons-Clause
"""
import time
from pathlib import Path
import pythoncom
from PySide2.QtCore import QThread, Signal
from app.data import ProjectGlobal
from app.data import ScriptDatabase
from app.data.database import TaskDatabase
from app.utils import BM_LOG, ParameterManager, BmTools
from app.servers.context import ContextManager
from app.servers.scripts import ScriptRunner, InstallScript
from app.utils.parameter_generate import build_launch_env
from app.servers.monitor import HotkeyManager
from app.servers.explorer import COMManager, SelectedFilesInExplorer, SelectedFolderInExplorer, \
    SelectedFilesAndFolderInExplorer, FileExplorerManager



class InstallCloudScriptWork(QThread):
    """
    安装云端脚本工作线程
    """

    progress_signal = Signal(dict)
    finished_signal = Signal(dict)

    def __init__(self, script_id:str, script_git_url:str, branch:str='main'):
        super().__init__()
        self.script_git_url = script_git_url
        self.script_id = script_id
        self.branch = branch

    def run(self):
        install = InstallScript()
        install.progress_signal.connect(self.progress_back)
        install.finished_signal.connect(self.finished_back)
        install.install_from_cloud(script_id=self.script_id, script_git_url=self.script_git_url, branch=self.branch)

    def progress_back(self, message):
        self.progress_signal.emit(message)

    def finished_back(self, message):
        self.finished_signal.emit(message)


class InstallLocalScriptWork(QThread):
    """
    安装本地脚本工作线程
    """

    progress_signal = Signal(dict)
    finished_signal = Signal(dict)

    def __init__(self, script_path):
        super().__init__()
        self.script_path = script_path

    def run(self):
        install = InstallScript()
        install.progress_signal.connect(self.progress_back)
        install.finished_signal.connect(self.finished_back)
        install.install_from_local(self.script_path)

    def progress_back(self, message):
        self.progress_signal.emit(message)

    def finished_back(self, message):
        self.finished_signal.emit(message)



class InstallGitScriptWork(QThread):
    """
    安装仓库脚本工作线程
    """

    progress_signal = Signal(dict)
    finished_signal = Signal(dict)

    def __init__(self, git_url, branch):
        super().__init__()
        self.git_url = git_url
        self.branch = branch

    def run(self):
        install = InstallScript()
        install.progress_signal.connect(self.progress_back)
        install.finished_signal.connect(self.finished_back)
        install.install_from_git(self.git_url, self.branch)

    def progress_back(self, message):
        self.progress_signal.emit(message)

    def finished_back(self, message):
        self.finished_signal.emit(message)


class UninstallScriptWork(QThread):
    """
    卸载异步线程
    先删数据库/菜单/快捷键，立即刷新 UI，后台再重试删目录
    """
    progress_signal = Signal(dict)
    finished_signal = Signal(dict)

    def __init__(self, script_id: str, parent=None):
        super().__init__(parent)
        self.script_id = script_id

    def _emit_progress(self, step: int, message: str):
        self.progress_signal.emit({'step': step, 'message': message, 'script_id': self.script_id})

    def run(self):
        script_id = self.script_id
        script_dir_path = BmTools.get_script_dir_path(script_id)
        results = {'database': False, 'context': False, 'tasks': False, 'hotkeys': False}

        try:
            # === 快速路径：数据库 + 菜单 + 任务 + 快捷键 ===
            results['database'] = ScriptDatabase.delete_script(script_id)

            self._emit_progress(1, '正在清理菜单...')
            ContextManager().remove_script_menu(script_id)
            results['context'] = True

            self._emit_progress(2, '正在清理关联任务...')
            TaskDatabase().delete_task_by_script_id(script_id)
            results['tasks'] = True

            self._emit_progress(3, '正在重载快捷键...')
            HotkeyManager().reload_hotkeys()
            results['hotkeys'] = True

            # 通知 UI 刷新（脚本从列表消失）
            self.finished_signal.emit({'state': True, 'message': '卸载成功', 'script_id': script_id})

            # === 慢速路径：删目录（静默重试）===
            if script_dir_path.exists():
                for attempt in range(4):
                    if BmTools.remove_dir(script_dir_path):
                        BM_LOG.info(f"后台清理目录成功: {script_dir_path}")
                        return
                    if attempt < 3:
                        time.sleep(2)  # 等文件锁释放
                # 兜底：标记重启删除（非管理员则进待删队列，下次启动重试）
                if not BmTools.mark_reboot_delete(script_dir_path):
                    BmTools.add_pending_deletion(script_dir_path)
                BM_LOG.warning(f"目录被占用，无法立即删除，已加入重启/启动清理: {script_dir_path}")

        except Exception as e:
            BM_LOG.error(f"卸载异常: {e}", exc_info=True)
            self.finished_signal.emit({'state': False, 'message': f"卸载出错: {str(e)}", 'script_id': script_id})


class ExecuteScriptWork(QThread):
    """
    执行脚本工作线程
    """
    execute_signal = Signal(bool)

    def __init__(self, script_id, script_args=''):
        super().__init__()
        self.script_id = script_id
        self.script_args = script_args

    def run(self):
        with ProjectGlobal.RUNNING_SCRIPTS_LOCK:
            ProjectGlobal.RUNNING_SCRIPTS.add(self.script_id)
        try:
            self.execute_signal.emit(True)
            execute = ScriptRunner()
            execute.run_script(self.script_id, self.script_args)
        except Exception as e:
            self.execute_signal.emit(False)
        finally:
            with ProjectGlobal.RUNNING_SCRIPTS_LOCK:
                ProjectGlobal.RUNNING_SCRIPTS.discard(self.script_id)



class ExecuteScriptFromHotkeyWork(QThread):
    """
    从快捷键执行脚本工作线程
    """
    execute_script_signal = Signal(dict)
    """
    约定格式{'status':bool,'message':str}
    """

    def __init__(self, script_id):
        super().__init__()
        self.script_id = script_id

    def run(self):
        pythoncom.CoInitialize()
        with ProjectGlobal.RUNNING_SCRIPTS_LOCK:
            ProjectGlobal.RUNNING_SCRIPTS.add(self.script_id)
        try:
            self.execute_script_signal.emit({'status': True, 'message': '正在准备参数...'})
            json_path = self._prepare_params_file()
            if json_path is None:  # 参数表单被取消
                return
            ScriptRunner().run_script(self.script_id, str(json_path))
        except Exception as e:
            BM_LOG.error(f"执行失败: {e}")
            self.execute_script_signal.emit({'status': False, 'message': f"执行出错: {e}"})
        finally:
            with ProjectGlobal.RUNNING_SCRIPTS_LOCK:
                ProjectGlobal.RUNNING_SCRIPTS.discard(self.script_id)
            pythoncom.CoUninitialize()

    def _prepare_params_file(self):
        """获取资源路径并写入临时文件"""
        script_data = ScriptDatabase().get_script_by_id(self.script_id)
        inputs = script_data.inputs_schema
        input_data = inputs[0] if inputs else {}
        shortcut_config = script_data.triggers_schema.get('shortcut', {})
        input_type = shortcut_config.get('input_type') or ''
        filters = shortcut_config.get('filters') or []

        # 获取路径列表
        paths = self._get_resource_paths(input_type, filters)
        params_overrides = {}
        if getattr(script_data, 'params_form_enabled', False):
            from app.view.script_ui.params_prompt import show_params_prompt
            res = show_params_prompt(script_data, paths)
            if res is None:  # 用户取消 → 不启动
                return None
            paths, params_overrides = res

        # 构造参数 JSON（注入 params 默认值，使本脚本可作为联动发起方）
        params_defs = script_data.params_schema or []
        env_extra = build_launch_env(self.script_id)
        result = ParameterManager().construct_parameters(
            input_data, paths,
            params_defs=params_defs,
            params_overrides=params_overrides,
            env_extra=env_extra,
        )
        return str(result) if result else ""

    def _get_resource_paths(self, input_type: str, filters: list) -> list:
        """根据类型获取 Explorer 中的路径"""
        # 获取 COM Shell 实例
        shell = COMManager.get_shell()
        mapping = {
            'files': lambda: SelectedFilesInExplorer(shell).get_selected_files(),
            'folders': lambda: SelectedFolderInExplorer(shell).get_selected_folder(),
            'active': lambda: FileExplorerManager(shell).get_active_tab_path(),
            'items': lambda: SelectedFilesAndFolderInExplorer(shell).get_selected_folder_and_files()
        }

        get_func = mapping.get(input_type)
        if not get_func:
            return []

        paths = get_func()

        # 统一处理过滤逻辑
        if filters and input_type == 'files':
            suffix_set = set(filters)
            paths = [p for p in paths if Path(p).suffix in suffix_set]
            if not paths:
                raise ValueError(f"类型不匹配：仅支持 {', '.join(filters)}")

        return paths if isinstance(paths, list) else [paths]


class ReadScriptsThread(QThread):
    """
    读取数据库脚本信息线程
    """
    get_scripts_signal = Signal(list)

    def __init__(self):
        super().__init__()
        self.db = None

    def run(self):
        if self.db is None:
            self.db = ScriptDatabase()
        scripts_data = self.db.get_all_scripts()
        ProjectGlobal.SCRIPTS = scripts_data  # 全局变量
        self.get_scripts_signal.emit(scripts_data)



