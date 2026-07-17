"""
Copyright (c) 2026 綦恒智
Email: bmscriptsbox@163.com
SPDX-License-Identifier: AGPL-3.0
"""
import os
import shutil
import stat
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
    """
    progress_signal = Signal(dict)
    finished_signal = Signal(dict)

    def __init__(self, script_id: str, parent=None):
        super().__init__(parent)
        self.script_id = script_id

    def _emit_progress(self, step: int, message: str):
        self.progress_signal.emit({'step': step, 'message': message, 'script_id': self.script_id})

    def _remove_temp_dir(self, temp_dir: Path) -> bool:
        """带重试和权限修复的临时目录删除"""
        def _try_rmtree(path, use_repair=False):
            if not use_repair:
                shutil.rmtree(path)
            else:
                def on_rm_error(func, p, exc_info):
                    os.chmod(p, stat.S_IWRITE)
                    func(p)
                shutil.rmtree(path, onerror=on_rm_error)

        def _long_rmtree(path):
            long_root = '\\\\?\\' + str(path.resolve())
            for root, dirs, files in os.walk(long_root, topdown=False):
                for name in files:
                    p = os.path.join(root, name)
                    try:
                        os.chmod(p, stat.S_IWRITE)
                        os.remove(p)
                    except Exception:
                        pass
                for name in dirs:
                    p = os.path.join(root, name)
                    try:
                        os.rmdir(p)
                    except Exception:
                        pass
            try:
                os.rmdir(long_root)
            except Exception:
                pass
            return not path.exists()

        # 首次尝试
        try:
            _try_rmtree(temp_dir)
            if not temp_dir.exists():
                return True
        except Exception as e:
            BM_LOG.warning(f"[Step 1] 快速删除失败: {e}")
            # 失败后立即尝试 \\?\ 长路径删除（针对超长路径、损坏 symlink 等场景）
            BM_LOG.info(f"[Step 1] 立即尝试长路径删除: {temp_dir}")
            if _long_rmtree(temp_dir):
                return True
        # 锁定/权限类错误的重试（路径过长类错误已经被 \\?\ 处理掉了）
        max_attempts = 3
        wait = 1
        for attempt in range(max_attempts):
            try:
                _try_rmtree(temp_dir, use_repair=(attempt > 0))
                if not temp_dir.exists():
                    return True
            except Exception as e:
                BM_LOG.warning(f"[Step 1] 删除尝试 {attempt + 1}/{max_attempts} 失败: {e}")
                if attempt < max_attempts - 1:
                    time.sleep(wait)
                    wait *= 2
        # 锁定等待兜底
        try:
            time.sleep(5)
            _try_rmtree(temp_dir, use_repair=True)
            if not temp_dir.exists():
                BM_LOG.info(f"[Step 1] 长等待后删除成功: {temp_dir}")
                return True
        except Exception:
            pass
        # 仍失败则标记重启后删除
        try:
            import ctypes
            ctypes.windll.kernel32.MoveFileExW(str(temp_dir), None, 4)
            BM_LOG.info(f"[Step 1] 已标记重启后删除: {temp_dir}")
            return True
        except Exception as e:
            BM_LOG.warning(f"[Step 1] 标记重启删除失败: {e}")
        return False

    def _rename_script(self, script_dir_path, temp_path):
        """原子重命名（重试 3 次，应对瞬时锁）"""
        for i in range(3):
            try:
                script_dir_path.rename(temp_path)
                return True
            except PermissionError:
                if i < 2:
                    BM_LOG.warning(f"[Uninstall] 目录被占用(重试 {i+1}/3)...")
                    time.sleep(1)
                continue
            except Exception as e:
                BM_LOG.error(f"[Uninstall] 目录重命名失败，原因: {str(e)}")
                return False
        BM_LOG.error(f"[Uninstall] 目录重命名重试 3 次均失败")
        return False

    def run(self):
        script_id = self.script_id
        script_dir_path = BmTools.get_script_dir_path(script_id)
        temp_dir = script_dir_path.parent/ f"{script_id}_uninstall_{int(time.time())}"

        cleanup_results = {
            'directory': False,
            'database': False,
            'context': False,
            'tasks': False,
            'hotkeys': False
        }

        try:
            # 1. 目录清理
            self._emit_progress(1, '正在删除文件...')
            if script_dir_path.exists():
                if not script_dir_path.is_dir():
                    BM_LOG.error(f"[Step 1] 错误: {script_id} 路径不是文件夹")
                    cleanup_results['directory'] = False
                elif self._rename_script(script_dir_path, temp_dir):
                    if self._remove_temp_dir(temp_dir):
                        cleanup_results['directory'] = True
                    else:
                        BM_LOG.warning(f"[Step 1] 文件句柄占用无法删除，残留目录: {temp_dir}")
                        cleanup_results['directory'] = True
                else:
                    BM_LOG.warning("[Step 1] 目录重命名失败，尝试就地删除...")
                    if self._remove_temp_dir(script_dir_path):
                        cleanup_results['directory'] = True
                    else:
                        try:
                            import ctypes
                            ctypes.windll.kernel32.MoveFileExW(str(script_dir_path.resolve()), None, 4)
                            BM_LOG.info("[Step 1] 已标记重启后删除")
                            cleanup_results['directory'] = True
                        except Exception as e:
                            BM_LOG.warning(f"[Step 1] 标记重启删除失败: {e}")
                            cleanup_results['directory'] = False
            else:
                cleanup_results['directory'] = True

            # 2. 数据库记录清理
            self._emit_progress(2, '正在清理数据库...')
            try:
                cleanup_results['database'] = ScriptDatabase.delete_script(script_id)
            except Exception as e:
                BM_LOG.error(f"[Step 2] 数据库清理崩溃: {e}")

            # 3. 菜单清理
            self._emit_progress(3, '正在清理菜单...')
            try:
                ContextManager().remove_script_menu(script_id)
                cleanup_results['context'] = True
            except Exception as e:
                BM_LOG.error(f"[Step 3] 菜单清理崩溃: {e}")

            # 4. 任务清理
            self._emit_progress(4, '正在清理关联任务...')
            try:
                TaskDatabase().delete_task_by_script_id(script_id)
                cleanup_results['tasks'] = True
            except Exception as e:
                BM_LOG.error(f"[Step 4] 任务清理崩溃: {e}")

            # 5. 刷新环境
            self._emit_progress(5, '正在重载快捷键...')
            try:
                HotkeyManager().reload_hotkeys()
                cleanup_results['hotkeys'] = True
            except Exception as e:
                BM_LOG.error(f"[Step 5] 环境重载失败: {e}")

            # --- 结果分析汇总 ---

            if all(cleanup_results.values()):
                BM_LOG.info(f"--- [Success] {script_id} 卸载完全成功 ---")
                self.finished_signal.emit({'state': True, 'message': '卸载成功', 'script_id': script_id})
            else:
                # 找出失败的环节
                failed_steps = [k for k, v in cleanup_results.items() if not v]
                BM_LOG.error(f"--- [Failure] {script_id} 卸载部分失败, 失败环节: {failed_steps} ---")

                if not cleanup_results['directory'] and script_dir_path.exists():
                    msg = '文件被占用，请关闭相关程序后重试'
                else:
                    msg = f"卸载不彻底 ({', '.join(failed_steps)})"

                self.finished_signal.emit({'state': False, 'message': msg, 'script_id': script_id})

        except Exception as e:
            BM_LOG.critical(f"[Critical] 线程运行中抛出未捕获异常: {e}", exc_info=True)
            self.finished_signal.emit({'state': False, 'message': f"致命错误: {str(e)}", 'script_id': script_id})


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
        input_data = inputs[-1] if inputs else {}
        shortcut_config = script_data.triggers_schema.get('shortcut', {})
        input_type = shortcut_config.get('input_type') or ''
        filters = shortcut_config.get('filters') or []

        # 获取路径列表
        paths = self._get_resource_paths(input_type, filters)
        # 构造参数 JSON
        result = ParameterManager().construct_parameters(input_data, paths)
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



