"""
Copyright (c) 2026 綦恒智
Email: bmscriptsbox@163.com
SPDX-License-Identifier: AGPL-3.0
"""
import json
import shutil
import sys
import tempfile
import time
import traceback
import zipfile
from pathlib import Path

from PySide2.QtCore import Signal, QObject, QCoreApplication

from app.data import ScriptDatabase
from app.utils import BmTools, BM_LOG
from app.servers.context import ContextManager
from app.servers.packages import PackagesManager
from app.servers.environment import TomlManager, GitManager, PyEnvManager, NodeEnvManager, AhkEnvManager


class InstallSignal(QObject):
    progress_signal = Signal(dict)
    """
    格式约定：{'status':True,'msg':"xxx完成"}
    """



class InstallScript(QObject):
    """
    负责协调解压、环境部署、数据库持久化及菜单注册的完整流程
    """
    progress_signal = Signal(dict)  # 过程进度反馈
    finished_signal = Signal(dict)  # 最终结果通知

    def __init__(self):
        super().__init__()
        # 预初始化管理器，避免多次连接信号
        self.py_deploy = PyEnvManager()
        self.node_deploy = NodeEnvManager()
        self.ahk_deploy = AhkEnvManager()

    # --- 主入口 ---

    def install_from_cloud(self, script_id: str, script_git_url: str, branch:str='main'):
        start_time = time.time()
        installed_resources = {
            "target_dir": False,  # 物理目录
            "db_entry": False,  # 数据库记录
            "context_menu": False  # 右键菜单
        }
        try:
            # 1:创建目录
            install_target_dir = self._prepare_directory(script_id)
            installed_resources["target_dir"] = install_target_dir

            # 2：克隆前记录旧依赖状态
            has_git = (install_target_dir / '.git').exists()
            BM_LOG.debug(f"[安装流程] 目录状态: exists={install_target_dir.exists()}, has_git={has_git}")
            old_deps = self._snapshot_deps(install_target_dir)

            # 3：克隆仓库
            self._download_from_git(script_git_url, install_target_dir, branch)

            # 4. 配置加载
            config = self._load_config(install_target_dir)

            # 5. 比对依赖变化，无变动则跳过部署
            need_deploy = self._needs_runtime_deploy(old_deps, install_target_dir, config)
            BM_LOG.debug(f"[安装流程] 脚本 {script_id} 部署判定结果: need_deploy={need_deploy}")
            if need_deploy:
                self._deploy_runtime(install_target_dir, config)
            else:
                BM_LOG.info(f"脚本 {script_id} 依赖无变化，跳过环境部署")

            # 6. 系统集成 (DB与右键菜单)
            self._register_system(config)
            installed_resources["db_entry"] = True  # 标记 DB 已写入
            installed_resources["context_menu"] = True  # 标记菜单已注册

            # 6. 完成通知
            cost = time.time() - start_time
            self._notify_finished(True, f"安装成功！耗时 {cost:.1f}s")
        except Exception as e:
            BM_LOG.error(f"安装失败，启动回滚程序... 错误详情: {traceback.format_exc()}")
            self._perform_rollback(installed_resources, script_id if 'script_id' in locals() else None)
            self._notify_finished(False, self._format_friendly_error(e))


    def install_from_git(self, script_git_url: str, branch: str = 'main'):
        start_time = time.time()
        installed_resources = {"target_dir": False, "db_entry": False, "context_menu": False}
        script_id = None
        temp_dir = None
        try:
            # 1. 克隆到临时目录
            temp_dir = Path(tempfile.mkdtemp(prefix='bms_'))
            installed_resources["target_dir"] = temp_dir
            self._download_from_git(script_git_url, temp_dir, branch)

            # 2. 读取 config 获得 script_id
            config = self._load_config(temp_dir)
            script_id = str(config.info.id)

            # 3. 移动到最终目录（同盘 rename）
            final_dir = BmTools.get_root_path() / 'BmScripts' / script_id
            if final_dir.exists():
                shutil.rmtree(final_dir, ignore_errors=True)
            shutil.copytree(temp_dir, final_dir, dirs_exist_ok=True)
            for _ in range(5):
                try:
                    shutil.rmtree(temp_dir)
                    break
                except PermissionError:
                    time.sleep(1)
            temp_dir = None
            installed_resources["target_dir"] = final_dir

            # 4~6. 部署 + 注册 + 完成
            config = self._load_config(final_dir)
            self._deploy_runtime(final_dir, config)
            self._register_system(config, '本地')
            installed_resources["db_entry"] = True
            installed_resources["context_menu"] = True

            cost = time.time() - start_time
            self._notify_finished(True, f"安装成功！耗时 {cost:.1f}s")

        except Exception as e:
            BM_LOG.error(f"安装失败，启动回滚程序... 错误详情: {traceback.format_exc()}")
            self._perform_rollback(installed_resources, script_id)
            self._notify_finished(False, self._format_friendly_error(e))

        finally:
            if temp_dir and Path(temp_dir).exists():
                shutil.rmtree(temp_dir, ignore_errors=True)
                BM_LOG.info(f"已清理临时目录: {temp_dir}")

    def install_from_local(self, script_zip_path: str):
        """本地 Zip 安装主流程（带回滚机制）"""
        start_time = time.time()
        installed_resources = {
            "target_dir": False,  # 物理目录
            "db_entry": False,  # 数据库记录
            "context_menu": False  # 右键菜单
        }
        try:
            script_id = TomlManager().read_toml_id_from_zip(script_zip_path)
            install_target_dir = self._prepare_directory(script_id)
            installed_resources["target_dir"] = install_target_dir  # 标记目录已创建

            # 2. 物理部署（解压）
            actual_script_dir = self._extract_package(script_zip_path, install_target_dir)

            # 3. 配置加载
            config = self._load_config(actual_script_dir)

            # 4. 环境与依赖部署 (耗时操作)
            self._deploy_runtime(actual_script_dir, config)

            # 5. 系统集成 (DB与右键菜单)
            self._register_system(config, '本地')
            installed_resources["db_entry"] = True  # 标记 DB 已写入
            installed_resources["context_menu"] = True  # 标记菜单已注册

            # 6. 完成通知
            cost = time.time() - start_time
            self._notify_finished(True, f"安装成功！耗时 {cost:.1f}s")

        except Exception as e:
            BM_LOG.error(f"安装失败，启动回滚程序... 错误详情: {traceback.format_exc()}")
            self._perform_rollback(installed_resources, script_id if 'script_id' in locals() else None)
            self._notify_finished(False, self._format_friendly_error(e))

    # --- 私有步骤拆解 ---
    def _download_from_git(self, script_git_url: str, script_dir: Path, branch:str='main') -> bool:
        """从Git仓库下载"""
        self._emit_progress("正在克隆脚本...")
        success = GitManager().download_script_from_git(script_git_url, str(script_dir), branch)
        if success:
            BM_LOG.info("Git仓库克隆成功")
        return success

    def _snapshot_deps(self, script_dir: Path) -> dict:
        """git pull 前记录旧依赖/二进制状态，首次安装时返回空 dict"""
        snapshot = {}
        if not script_dir.exists():
            BM_LOG.debug(f"[快照] 目录不存在，判定为首次安装: {script_dir}")
            return snapshot

        files = [p.name for p in script_dir.iterdir()]
        BM_LOG.debug(f"[快照] 目录文件列表 ({len(files)} 项): {files[:20]}")

        # Python 依赖快照
        pyproject_file = script_dir / 'pyproject.toml'
        if pyproject_file.exists():
            try:
                data = TomlManager().read_pyproject_toml_from_dir(str(script_dir))
                project = data.get('project', {})
                snapshot['python_deps'] = project.get('dependencies', [])
                snapshot['python_requires'] = project.get('requires-python', '')
                BM_LOG.debug(f"[快照] Python 旧依赖: {snapshot['python_deps']}, requires: {snapshot['python_requires']}")
            except Exception as e:
                BM_LOG.debug(f"[快照] 读取旧 pyproject.toml 失败: {e}")
        else:
            BM_LOG.debug("[快照] 旧 pyproject.toml 不存在")

        # Node 依赖快照
        pkg_file = script_dir / 'package.json'
        if pkg_file.exists():
            try:
                with open(pkg_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                snapshot['node_deps'] = data.get('dependencies', {})
                snapshot['node_dev_deps'] = data.get('devDependencies', {})
                deps_count = len(snapshot['node_deps'])
                dev_count = len(snapshot['node_dev_deps'])
                BM_LOG.debug(f"[快照] Node 旧依赖: {deps_count} 个, devDeps: {dev_count} 个")
            except Exception as e:
                BM_LOG.debug(f"[快照] 读取旧 package.json 失败: {e}")
        else:
            BM_LOG.debug("[快照] 旧 package.json 不存在")

        # Binaries 列表快照
        result = TomlManager().read_toml_from_dir(str(script_dir))
        if result.success and result.config:
            snapshot['binaries'] = list(result.config.runtime.binaries or [])
            BM_LOG.debug(f"[快照] 旧 binaries 列表: {snapshot['binaries']}")
        else:
            BM_LOG.debug("[快照] 旧配置文件不存在或解析失败")

        return snapshot

    def _needs_runtime_deploy(self, old: dict, script_dir: Path, config) -> bool:
        """比对旧快照与新配置，判断是否需要重新部署"""
        # 首次安装 → 必须部署
        if not old:
            BM_LOG.debug("[部署判定] 首次安装或旧状态为空，需要部署")
            return True

        BM_LOG.debug(f"[部署判定] 旧快照内容: {old}")
        lang = config.runtime.language.lower()

        # Python 环境：比对 pyproject.toml 的依赖 + requires-python
        if lang == 'python':
            if not (script_dir / '.venv').exists():
                BM_LOG.debug("[部署判定] .venv 目录不存在，需要部署")
                return True
            if 'python_deps' not in old:
                BM_LOG.debug("[部署判定] 旧快照无 Python 依赖信息，需要部署")
                return True
            pyproject_file = script_dir / 'pyproject.toml'
            if not pyproject_file.exists():
                BM_LOG.debug("[部署判定] pyproject.toml 不存在，需要部署")
                return True
            try:
                new_data = TomlManager().read_pyproject_toml_from_dir(str(script_dir))
                new_project = new_data.get('project', {})
                new_deps = new_project.get('dependencies', [])
                new_requires = new_project.get('requires-python', '')
                if old['python_deps'] != new_deps or old['python_requires'] != new_requires:
                    BM_LOG.debug(f"[部署判定] Python 依赖变更: 旧={old['python_deps']}, 新={new_deps}")
                    return True
            except Exception as e:
                BM_LOG.debug(f"[部署判定] 读取新 pyproject.toml 异常: {e}，保守部署")
                return True

        # Node 环境：比对 package.json 的 dependencies + devDependencies
        elif lang == 'node.js':
            if not (script_dir / 'node_modules').exists():
                BM_LOG.debug("[部署判定] node_modules 目录不存在，需要部署")
                return True
            if 'node_deps' not in old:
                BM_LOG.debug("[部署判定] 旧快照无 Node 依赖信息，需要部署")
                return True
            pkg_file = script_dir / 'package.json'
            if not pkg_file.exists():
                BM_LOG.debug("[部署判定] package.json 不存在，需要部署")
                return True
            try:
                with open(pkg_file, 'r', encoding='utf-8') as f:
                    new_data = json.load(f)
                new_deps = new_data.get('dependencies', {})
                new_dev_deps = new_data.get('devDependencies', {})
                if old['node_deps'] != new_deps or old['node_dev_deps'] != new_dev_deps:
                    BM_LOG.debug(f"[部署判定] Node 依赖变更: 旧 {len(old['node_deps'])} 个, 新 {len(new_deps)} 个")
                    return True
                BM_LOG.debug("[部署判定] Node 依赖无变化")
            except Exception as e:
                BM_LOG.debug(f"[部署判定] 读取新 package.json 异常: {e}，保守部署")
                return True

        # 其他语言（AHK、bat 等）→ 无依赖可跳过，始终返回 True（由 deploy 自己短路）
        else:
            BM_LOG.debug(f"[部署判定] 语言 '{lang}' 无依赖管理，始终部署")
            return True

        # Binaries 比对
        new_binaries = list(config.runtime.binaries or [])
        old_binaries = old.get('binaries')
        if old_binaries != new_binaries:
            BM_LOG.debug(f"[部署判定] binaries 变更: 旧={old_binaries}, 新={new_binaries}")
            return True
        BM_LOG.debug("[部署判定] binaries 无变化")

        BM_LOG.debug("[部署判定] 所有维度均无变化，跳过部署")
        return False

    def _perform_rollback(self, resources: dict, script_id: str):
        """执行回滚清理"""
        self._emit_progress("安装中断，正在清理残留资源...")

        try:
            # 1. 清理右键菜单
            if resources["context_menu"]:
                ContextManager().remove_script_menu(script_id=script_id)

            # 2. 清理数据库
            if resources["db_entry"]:
                ScriptDatabase().delete_script(script_id)

            # 3. 清理物理文件 (最重要的一步)
            if resources.get("target_dir") and resources["target_dir"].exists():
                # 释放可能的文件占用（可选）
                import gc;
                gc.collect()
                shutil.rmtree(resources["target_dir"], ignore_errors=True)
                BM_LOG.info(f"已清理残留目录: {resources['target_dir']}")

            self._emit_progress("残留资源清理完毕")

        except Exception as rollback_err:
            BM_LOG.critical(f"回滚过程中发生二次错误: {rollback_err}")

    def _prepare_directory(self, script_id: str) -> Path:
        """创建安装目标目录"""
        try:
            # 建议将基础路径提取为配置常量
            base_dir = BmTools.get_root_path() / 'BmScripts'
            script_dir = base_dir / script_id
            script_dir.mkdir(parents=True, exist_ok=True)
            self._emit_progress("初始化脚本目录完成")
            return script_dir
        except Exception as e:
            raise RuntimeError(f"目录初始化失败: {e}")

    def _extract_package(self, zip_path: str, target_dir: Path) -> Path:
        """解压并定位配置文件目录"""
        try:
            with zipfile.ZipFile(zip_path, 'r') as z:
                z.extractall(target_dir)

            # 寻找配置文件
            toml_files = list(target_dir.rglob("bm-scripts-box-rc.toml"))
            if not toml_files:
                raise FileNotFoundError("压缩包内缺失 bm-scripts-box-rc.toml 配置文件")

            self._emit_progress("解压包文件完成")
            return toml_files[0].parent
        except Exception as e:
            raise RuntimeError(f"解压过程出错: {e}")

    def _load_config(self, script_dir: Path):
        """
        解析并校验 TOML 配置
        对接 TomlManager().read_toml_from_dir 的 ScriptLoadResult 结构
        """
        # 显式转换 Path 为 str，因为你的函数签名要求 str
        result = TomlManager().read_toml_from_dir(str(script_dir))
        # 检查 ScriptLoadResult 的 success 标志
        if not result.success:
            # 聚合所有错误信息并抛出，由 install_from_local 的 try-except 统一捕获
            error_details = " | ".join(result.error_messages)
            raise ValueError(f"配置文件读取失败: {error_details}")

        # 返回序列化后的 config 对象
        return result.config

    def _deploy_runtime(self, script_dir: Path, config):
        """部署运行环境（支持多语言扩展）"""
        lang = config.runtime.language.lower()

        if lang == 'python':
            # 获取依赖项
            pyproject = TomlManager().read_pyproject_toml_from_dir(str(script_dir))
            deps = pyproject.get('project', {}).get('dependencies', [])

            # 校验版本一致性
            if config.runtime.language_version != pyproject.get('project', {}).get('requires-python'):
                BM_LOG.warning("警告：TOML 与 pyproject 的 Python 版本声明不一致")
                error_msg = (
                    f"环境定义冲突 pyproject.toml与bm-scripts-box-rc.toml文件中的 Python 版本声明不一致"
                )
                raise RuntimeError(error_msg)
            self.py_deploy = PyEnvManager()
            self.py_deploy.py_runtime_install_progress.connect(self.progress_signal.emit)
            self.py_deploy.create_venv(
                script_dir=str(script_dir),
                spec_str=config.runtime.language_version,
                dependencies=deps
            )

        if lang == 'node.js':
            self.node_deploy = NodeEnvManager()
            self.node_deploy.node_runtime_install_progress.connect(self.progress_signal.emit)
            self.node_deploy.prepare_env(script_dir=str(script_dir), node_spec=config.runtime.language_version)

        if lang == 'autohotkey':
            self.ahk_deploy = AhkEnvManager()
            self.ahk_deploy.ahk_runtime_progress.connect(self.progress_signal.emit)
            self.ahk_deploy.prepare_env(spec_str=config.runtime.language_version)

        # 处理二进制资源下载
        if config.runtime.binaries:
            self._emit_progress("同步外部二进制资源...")
            pm = PackagesManager()
            pm.packages_progress.connect(self.progress_signal.emit)
            pm.batch_install_cli(config.runtime.binaries)

    def _register_system(self, config, badge:str=''):
        """执行数据库持久化和系统菜单注册"""
        self._emit_progress("正在注册系统组件...")

        # 1. 入库
        ScriptDatabase().from_config_model(config, badge)

        # 2. 右键菜单
        if config.triggers and config.triggers.context_menu.enabled:
            ContextManager().add_script_menu(
                script_id=str(config.info.id),
                name=config.info.name,
                icon=config.info.icon,
                language=config.runtime.language,
                context_data=config.triggers.context_menu
            )

    # --- 辅助工具 ---
    def _emit_progress(self, msg: str):
        """发射进度条信号"""
        self.progress_signal.emit({'status': True, 'msg': msg})

    def _notify_finished(self, success: bool, msg: str):
        """发射完成信号"""
        self.finished_signal.emit({'status': success, 'msg': msg})

    def _format_friendly_error(self, error: Exception) -> str:
        err_str = str(error).strip()

        # 拦截已知网络问题
        if "ProxyError" in err_str: return "网络代理异常..."
        if "timeout" in err_str.lower(): return "请求超时..."

        first_line = err_str.split('\n')[0]
        if len(first_line) > 120:
            first_line = first_line[:117] + "..."

        return f"安装由于意外中断: {first_line}"




