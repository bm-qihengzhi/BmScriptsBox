"""
Copyright (c) 2026 綦恒智
Email: bmscriptsbox@163.com
SPDX-License-Identifier: AGPL-3.0
"""
import json
import locale
import os
import shlex
import subprocess
import sys
import tempfile
import threading
import webbrowser
from pathlib import Path
from typing import Dict, List, Tuple

from app.data import ScriptDatabase
from app.utils import BM_LOG, BmTools
from app.servers.packages import PackagesManager


class ScriptRunner:
    """处理脚本执行的核心逻辑"""

    # 类级进程注册表 — 跨实例追踪所有正在运行的脚本进程
    _running_processes: Dict[str, subprocess.Popen] = {}
    _running_lock = threading.Lock()

    @classmethod
    def track_process(cls, script_id: str, process: subprocess.Popen):
        with cls._running_lock:
            cls._running_processes[script_id] = process

    @classmethod
    def untrack_process(cls, script_id: str):
        with cls._running_lock:
            cls._running_processes.pop(script_id, None)

    @classmethod
    def terminate_all(cls):
        """强制终止所有正在运行的脚本进程"""
        with cls._running_lock:
            for sid, proc in cls._running_processes.items():
                try:
                    proc.kill()
                except Exception:
                    pass
            cls._running_processes.clear()

    # HTML 应用模式默认窗口尺寸
    HTML_WINDOW_WIDTH = 1000
    HTML_WINDOW_HEIGHT = 800

    def __init__(self):
        self.db = None
        # 语言配置映射：(执行程序名/获取函数, 是否需要额外环境变量)
        self.configs = {
            'bat': {'ext': '.bat', 'cmd_gen': lambda p, v: [p]},
            'powershell': {'ext': '.ps1', 'cmd_gen': lambda p, v: ['pwsh', '-ExecutionPolicy', 'Bypass', '-File', p]},
            'python': {'ext': '.py', 'cmd_gen': self._get_python_cmd},
            'node.js': {'ext': '.js', 'cmd_gen': self._get_node_cmd},
            'autohotkey': {'ext': '.ahk', 'cmd_gen': self._get_ahk_cmd},
            'html': {'ext': '.html', 'cmd_gen': self._get_html_cmd},
            'exe': {'ext': '.exe', 'cmd_gen': lambda p, v: [p]},
        }
    def get_script_info(self, script_id: str) -> tuple:
        """
        获取脚本信息、并返回脚本启动文件路径和show_terminal
        """
        if not self.db:
            self.db = ScriptDatabase()
        results = self.db.get_script_by_id(script_id)
        return (results.entry,
                results.language,
                results.language_version,
                results.terminal)


    def run_script(self, script_id: str, param: str):
        # 1. 获取基础信息
        entry, lang, version, terminal = self.get_script_info(script_id)
        lang = lang.lower()

        if lang not in self.configs:
            raise ValueError(f"不支持的语言: {lang}")

        # 2. 准备执行环境
        script_path = Path(entry)
        if not script_path.exists():
            raise FileNotFoundError(f"脚本不存在: {entry}")

        # 3. 构造基础命令
        config = self.configs[lang]
        cmd = config['cmd_gen'](str(script_path), version)

        # 4. 参数处理 (支持 JSON 路径或普通字符串)
        if param.strip() and lang != 'html':
            cmd.extend(shlex.split(param, posix=False))

        # 5. 执行并清理
        try:
            env = self._prepare_env(lang, cmd[0])
            return self._execute(script_id, cmd, terminal, param, env)
        finally:
            self._cleanup(param)

    def _prepare_env(self, lang: str, runtime_path: str) -> dict:
        """统一处理环境变量"""
        env = os.environ.copy()
        env.pop('PYTHONPATH', None)

        # 自动将运行时所在目录加入 PATH
        runtime_dir = str(Path(runtime_path).parent)
        env['PATH'] = f"{runtime_dir}{os.pathsep}{env.get('PATH', '')}"

        if lang == 'python':
            env.update({'PYTHONIOENCODING': 'utf-8', 'PYTHONUTF8': '1'})
        return env

    def _cleanup(self, param: str):
        """统一清理逻辑：仅清理位于系统临时目录下的 JSON 临时文件"""
        try:
            path = Path(param)
            if not path.exists() or not path.is_file():
                return
            resolved = path.resolve()
            temp_root = Path(tempfile.gettempdir()).resolve()
            if path.suffix == '.json' and str(resolved).startswith(str(temp_root)):
                path.unlink()
                BM_LOG.info(f"清理临时文件: {path}")
        except Exception:
            pass

    def _execute(self, script_id: str, cmd: List[str], terminal_mode: str, params: str, env: dict):
        """
        统一的进程调度器
        terminal_mode: 'never' | 'always' | 'auto' | 'inverse'
        """
        encoding = locale.getpreferredencoding(False)
        is_windows = (sys.platform == 'win32')

        # 1. 核心标志位定义
        CREATE_NO_WINDOW = 0x08000000 if is_windows else 0
        CREATE_NEW_CONSOLE = 0x00000010 if is_windows else 0
        try:
            # 模式 A: 绝不显示窗口 (静默执行)
            if terminal_mode == 'never':
                process = subprocess.Popen(
                    cmd,
                    env=env,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    stdin=subprocess.DEVNULL,
                    creationflags=CREATE_NO_WINDOW,

                )
                ScriptRunner.track_process(script_id, process)
                process.wait()
                ScriptRunner.untrack_process(script_id)
                return True, None, None

            # 模式 B: 始终显示新窗口 (交互模式)
            elif terminal_mode == 'always':
                process = subprocess.Popen(
                    cmd,
                    env=env,
                    creationflags=CREATE_NEW_CONSOLE,
                    encoding=encoding
                )
                ScriptRunner.track_process(script_id, process)
                process.wait()
                ScriptRunner.untrack_process(script_id)
                return True, None, None

            # 模式 C: 自动 (根据是否有参数决定是'静默捕获'还是'弹窗运行')
            elif terminal_mode == 'auto':
                if params.strip():
                    # 有参数：捕获输出并返回给 UI，不弹窗
                    process = subprocess.Popen(
                        cmd,
                        env=env,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE,
                        creationflags=CREATE_NO_WINDOW
                    )
                    ScriptRunner.track_process(script_id, process)
                    stdout_bytes, stderr_bytes = process.communicate()
                    ScriptRunner.untrack_process(script_id)

                    stdout = self._smart_decode(stdout_bytes)
                    stderr = self._smart_decode(stderr_bytes)

                    if process.returncode != 0:
                        raise RuntimeError(f'执行失败: {stderr}')
                    return True, stdout, stderr
                else:
                    # 无参数：直接弹窗让用户操作
                    process = subprocess.Popen(
                        cmd,
                        env=env,
                        creationflags=CREATE_NEW_CONSOLE
                    )
                    ScriptRunner.track_process(script_id, process)
                    process.wait()
                    ScriptRunner.untrack_process(script_id)
                    return True, None, None

            # 模式 D: 与 auto 相反 -- 有参数弹窗，无参数静默
            elif terminal_mode == 'inverse':
                if params.strip():
                    process = subprocess.Popen(
                        cmd, env=env,
                        creationflags=CREATE_NEW_CONSOLE
                    )
                    ScriptRunner.track_process(script_id, process)
                    process.wait()
                    ScriptRunner.untrack_process(script_id)
                    return True, None, None
                else:
                    process = subprocess.Popen(
                        cmd, env=env,
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                        stdin=subprocess.DEVNULL,
                        creationflags=CREATE_NO_WINDOW,
                    )
                    ScriptRunner.track_process(script_id, process)
                    process.wait()
                    ScriptRunner.untrack_process(script_id)
                    return True, None, None

            else:
                raise ValueError(f'无效的终端模式: {terminal_mode}')

        except Exception as e:
            BM_LOG.error(f'子进程启动失败: {e}')
            raise RuntimeError(f'进程调度失败: {e}')

    def _smart_decode(self, data: bytes) -> str:
        """智能解码：优先 UTF-8，其次 GBK，最后忽略错误"""
        if not data: return ""
        for enc in ['utf-8', 'gbk', 'gb18030']:
            try:
                return data.decode(enc)
            except UnicodeDecodeError:
                continue
        return data.decode('utf-8', errors='ignore')



    # --- 具体的命令构造逻辑 ---
    def _get_html_cmd(self, path:str, version: str) -> List[str]:
        return ["webview-cli", path,'--width', str(self.HTML_WINDOW_WIDTH),'--height', str(self.HTML_WINDOW_HEIGHT)]

    def _get_python_cmd(self, path: str, version: str) -> List[str]:
        venv_python = Path(path).parent / '.venv' / 'Scripts' / 'python.exe'
        exe = venv_python if venv_python.exists() else PackagesManager().install_cli('python', version)
        return [str(exe), path]

    def _get_node_cmd(self, path: str, version: str) -> List[str]:
        exe = PackagesManager().install_cli('node', version)
        return [str(exe), path]

    def _get_ahk_cmd(self, path: str, version: str) -> List[str]:
        exe = PackagesManager().install_cli('autohotkey', version)
        return [str(exe), path]




if __name__ == '__main__':
    pass