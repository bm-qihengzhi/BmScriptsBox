"""
Copyright (c) 2026 綦恒智
Email: bmscriptsbox@163.com
SPDX-License-Identifier: AGPL-3.0
"""
import os
import time
import shutil
import subprocess
import threading
from pathlib import Path
from typing import Optional, Tuple, List
from PySide2.QtCore import QObject, Signal, QCoreApplication

from app.utils import BM_LOG
from app.servers.packages import PackagesManager

class PyEnvManager(QObject):
    """
    Python 脚本环境依赖管理类
    职责：负责虚拟环境创建、Tkinter 补丁、依赖安装及环境校验
    """
    py_runtime_install_progress = Signal(dict)

    # 路径常量配置
    VENV_NAME = ".venv"
    SCRIPTS_DIR = "Scripts" if os.name == 'nt' else "bin"
    PYTHON_EXE = "python.exe" if os.name == 'nt' else "python"

    def __init__(self):
        super().__init__()
        self.uv_path: Optional[str] = None
        self.python_path: Optional[str] = None
        self.package = PackagesManager()
        # 信号转发：将 PackagesManager 的进度直接透传
        self.package.packages_progress.connect(self.py_runtime_install_progress.emit)

    # --- 核心主流程 ---

    def create_venv(self, script_dir: str, spec_str: str = ">=3.8",
                    dependencies: list = None, timeout: int = 120) -> bool:
        """
        为脚本创建虚拟环境（主控逻辑）
        """
        venv_path = Path(script_dir) / self.VENV_NAME

        try:
            # 1. 前置验证
            self._validate_before_install(script_dir, venv_path)

            # 2. 准备基础工具路径
            self.uv_path = self._get_uv_path()
            self.python_path = self._get_python_path(spec_str)

            if not dependencies:
                BM_LOG.info(f"脚本 {script_dir} 无第三方依赖，跳过环境创建")
                return True

            # 3. 创建虚拟环境
            self._emit_progress("正在创建 Python 虚拟环境...")
            self._exec_uv_venv(script_dir, venv_path, timeout)

            # 4. 验证并执行后续增强
            if self._verify_venv(venv_path):
                # 打 Tkinter 补丁
                self._apply_tkinter_patch(venv_path, spec_str)
                # 安装依赖
                self.install_dependencies(script_dir, 360)

                self._emit_progress("Python 环境配置已完成", True)
                return True
            else:
                raise RuntimeError("虚拟环境文件校验未通过")

        except Exception as e:
            error_msg = f"环境配置失败: {str(e)}"
            BM_LOG.error(error_msg)
            self._emit_progress(error_msg, False)
            raise RuntimeError(error_msg)

    def install_dependencies(self, script_dir: str, timeout: int = 300) -> bool:
        """
        同步脚本依赖 (uv sync)，流式输出进度
        """
        self._emit_progress("正在同步第三方依赖包...")

        script_path = Path(script_dir)
        venv_python = self._find_python_path(script_dir)

        if not venv_python:
            raise RuntimeError("无法定位虚拟环境中的 Python 解释器")

        # 清理过期构建缓存，防止 python38.dll 与 python310.dll 冲突
        self._clean_uv_build_cache(script_path)

        # 执行 uv sync（流式，逐行发射进度）
        cmd_args = ['sync', '--python', str(venv_python)]
        self._run_uv_streaming(cmd_args, script_path, "依赖同步", timeout)

        self._emit_progress("依赖包安装完成")
        return True

    def _clean_uv_build_cache(self, cwd: Path):
        """清理 uv 构建缓存目录，避免跨 Python 版本的构建沙箱冲突"""
        try:
            cache_result = subprocess.run(
                [str(self.uv_path), 'cache', 'dir'],
                capture_output=True, text=True, cwd=cwd,
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
            )
            cache_dir = cache_result.stdout.strip()
            builds_dir = Path(cache_dir) / 'builds-v0'
            if builds_dir.exists():
                shutil.rmtree(builds_dir)
                BM_LOG.info(f"已清理 uv 构建缓存: {builds_dir}")
        except Exception as e:
            BM_LOG.warning(f"清理 uv 构建缓存失败（不影响安装）: {e}")

    # --- 内部功能组件 ---

    def _exec_uv_venv(self, script_dir: str, venv_path: Path, timeout: int):
        """执行 uv venv 命令"""
        start_time = time.time()
        args = [
            'venv',
            '--python', str(self.python_path),
            '--system-site-packages',
            str(venv_path)
        ]

        result = self._run_subprocess(args, Path(script_dir), "创建虚拟环境", timeout)

        exec_time = time.time() - start_time
        BM_LOG.info(f"虚拟环境创建成功，耗时: {exec_time:.2f}s")
        if result.stdout:
            BM_LOG.debug(f"UV 输出: {result.stdout.strip()}")

    def _apply_tkinter_patch(self, venv_path: Path, spec_str: str):
        """为环境安装并覆盖 Tkinter 库"""
        self._emit_progress("正在配置 GUI 组件库...")
        venv_scripts = venv_path / self.SCRIPTS_DIR

        # 通过包管理器获取 tk 资源
        tk_dir = self.package.install_cli('tkinter', spec_str)

        source = Path(tk_dir)
        if not source.exists():
            raise FileNotFoundError(f"Tkinter 源目录不存在: {tk_dir}")

        try:
            for item in source.iterdir():
                if item.suffix in ('.pth', '._pth'):
                    continue  # 跳过嵌入式 Python 的 sys.path 控制文件
                dest = venv_scripts / item.name
                if item.is_dir():
                    shutil.copytree(item, dest, dirs_exist_ok=True)
                else:
                    shutil.copy2(item, dest)
        except Exception as e:
            raise RuntimeError(f"Tkinter 补丁应用失败: {e}")

    # --- 辅助与校验方法 ---

    def _run_subprocess(self, args: List[str], cwd: Path, task_name: str, timeout: int) -> subprocess.CompletedProcess:
        """通用子进程执行器"""
        if not self.uv_path:
            self.uv_path = self._get_uv_path()

        cmd = [str(self.uv_path)] + args
        CLEAN_ENV_KEYS = {'VIRTUAL_ENV', 'PYTHONPATH', 'PYTHONHOME', 'PYTHONSTARTUP'}
        env = {k: v for k, v in os.environ.items() if k not in CLEAN_ENV_KEYS}
        env['PYTHONUTF8'] = '1'

        try:
            result = subprocess.run(
                cmd, capture_output=True, text=True,
                encoding='utf-8', errors='ignore',
                timeout=timeout, cwd=cwd, env=env,
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
            )

            if result.returncode != 0:
                BM_LOG.error(f"子进程失败 (exit={result.returncode}): {' '.join(cmd)}")
                if result.stdout.strip():
                    BM_LOG.error(f"stdout:\n{result.stdout.strip()}")
                if result.stderr.strip():
                    BM_LOG.error(f"stderr:\n{result.stderr.strip()}")
                error_msg = self._parse_error_details(result)
                raise RuntimeError(f"{task_name}失败: {error_msg}")
            return result

        except subprocess.TimeoutExpired:
            raise RuntimeError(f"{task_name}操作超时（{timeout}秒）")
        except Exception as e:
            raise RuntimeError(f"调用系统组件异常: {e}")

    def _validate_before_install(self, script_dir: str, venv_path: Path):
        """安装前的全量检查"""
        # 1. 目录检查
        if not Path(script_dir).exists():
            raise FileNotFoundError(f"脚本工作目录不存在: {script_dir}")

        # 2. 磁盘空间检查
        if not self._check_disk_space(script_dir, min_mb=500):
            raise RuntimeError("磁盘空间不足，建议保留至少 500MB 可用空间")

        # 3. 如果环境已存在，仅记录日志，不阻断流程
        if venv_path.exists():
            BM_LOG.warning(f"虚拟环境目录已存在，将执行覆盖安装: {venv_path}")

    def _check_disk_space(self, target_path: str, min_mb: int) -> bool:
        """检查磁盘空间"""
        try:
            usage = shutil.disk_usage(target_path)
            free_mb = usage.free / (1024 * 1024)
            return free_mb >= min_mb
        except Exception:
            return True  # 读取失败则放行

    def _verify_venv(self, venv_path: Path) -> bool:
        """环境完整性校验"""
        checks = [
            venv_path / 'pyvenv.cfg',
            venv_path / self.SCRIPTS_DIR / self.PYTHON_EXE
        ]
        return all(p.exists() for p in checks)

    def _find_python_path(self, script_dir: str) -> Optional[str]:
        """寻找环境内的 Python 解释器"""
        path = Path(script_dir) / self.VENV_NAME / self.SCRIPTS_DIR / self.PYTHON_EXE
        return str(path) if path.exists() else None

    def _emit_progress(self, msg: str, status: bool = True):
        """统一发射进度信号"""
        self.py_runtime_install_progress.emit({'status': status, 'msg': msg})

    def _get_uv_path(self) -> str:
        return self.package.get_uv()

    def _get_python_path(self, spec_str: str) -> str:
        return self.package.get_python(version_requirement=spec_str)

    @staticmethod
    def _should_forward_uv_line(line: str) -> bool:
        """过滤无意义的进度行：warning、逐包明细、说明文本"""
        if not line:
            return False
        lower = line.lstrip().lower()
        if lower.startswith('warning:'):
            return False
        if lower.startswith('+ '):
            return False
        if lower.startswith('if '):
            return False
        return True

    def _run_uv_streaming(self, args: list, cwd: Path, task_name: str, timeout: int):
        """
        流式运行 uv 子进程，逐行读取 stderr 并发射进度信号
        """
        if not self.uv_path:
            self.uv_path = self._get_uv_path()

        cmd = [str(self.uv_path)] + args

        CLEAN_ENV_KEYS = {'VIRTUAL_ENV', 'PYTHONPATH', 'PYTHONHOME', 'PYTHONSTARTUP'}
        env = {k: v for k, v in os.environ.items() if k not in CLEAN_ENV_KEYS}
        env['PYTHONUTF8'] = '1'

        process = subprocess.Popen(
            cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            text=True, encoding='utf-8', errors='ignore',
            cwd=cwd, env=env,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
        )

        stdout_lines = []
        stderr_lines = []
        last_emit_time = time.time()
        last_heartbeat_time = time.time()

        def _read_stdout():
            try:
                for line in process.stdout:
                    stdout_lines.append(line)
            except:
                pass

        def _read_stderr():
            nonlocal last_emit_time
            try:
                for line in process.stderr:
                    line = line.rstrip('\n\r')
                    stderr_lines.append(line)
                    stripped = line.strip()
                    if not stripped:
                        continue
                    if self._should_forward_uv_line(stripped):
                        self._emit_progress(stripped)
                        last_emit_time = time.time()
            except:
                pass

        stdout_thread = threading.Thread(target=_read_stdout, daemon=True)
        stderr_thread = threading.Thread(target=_read_stderr, daemon=True)
        stdout_thread.start()
        stderr_thread.start()

        _wait_start = time.time()
        while True:
            QCoreApplication.processEvents()
            # 心跳：超过 10 秒没有进度信号时发占位信息
            now = time.time()
            if now - last_emit_time > 10 and now - last_heartbeat_time > 10:
                self._emit_progress("正在解析脚本依赖，请稍候...")
                last_heartbeat_time = now
            if process.poll() is not None:
                break
            if time.time() - _wait_start > timeout:
                process.kill()
                raise RuntimeError(f"{task_name}操作超时（{timeout}秒）")
            time.sleep(0.05)

        stdout_thread.join(timeout=5)
        stderr_thread.join(timeout=5)

        if process.returncode != 0:
            stderr_text = '\n'.join(stderr_lines)
            stdout_text = ''.join(stdout_lines)
            BM_LOG.error(f"子进程失败 (exit={process.returncode}): {' '.join(cmd)}")
            if stdout_text.strip():
                BM_LOG.error(f"stdout:\n{stdout_text.strip()}")
            if stderr_text.strip():
                BM_LOG.error(f"stderr:\n{stderr_text.strip()}")
            error_msg = self._parse_error_from_text(stderr_text or stdout_text)
            raise RuntimeError(f"{task_name}失败: {error_msg}")

    def _parse_error_details(self, result: subprocess.CompletedProcess) -> str:
        """从结果中提取核心错误信息"""
        err = result.stderr.strip() or result.stdout.strip()
        if not err:
            return f"Code({result.returncode})"
        lines = err.split('\n')
        # 过滤掉 uv/pip 的通用帮助提示行，保留实际错误
        skip_keywords = ['help:', 'Build failures usually indicate']
        useful = [l for l in lines if not any(kw in l.lower() for kw in skip_keywords)]
        useful = [l for l in useful if l.strip()]
        if useful:
            tail = '\n'.join(useful[-5:])
        else:
            tail = '\n'.join(lines[-3:])
        return f"Code({result.returncode}): {tail}"

    def _parse_error_from_text(self, error_text: str) -> str:
        """从纯文本中提取核心错误信息（供流式子进程使用）"""
        if not error_text:
            return ""
        lines = error_text.split('\n')
        skip_keywords = ['help:', 'Build failures usually indicate']
        useful = [l for l in lines if not any(kw in l.lower() for kw in skip_keywords)]
        useful = [l for l in useful if l.strip()]
        if useful:
            return '\n'.join(useful[-5:])
        return '\n'.join(lines[-3:])

    def cleanup_venv(self, script_dir: str) -> Tuple[bool, str]:
        """清理环境"""
        venv_path = Path(script_dir) / self.VENV_NAME
        if not venv_path.exists():
            return True, "无需清理"
        try:
            shutil.rmtree(venv_path)
            return True, "清理成功"
        except Exception as e:
            return False, f"清理失败: {e}"
