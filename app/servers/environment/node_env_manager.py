"""
Copyright (c) 2026 綦恒智
Email: bmscriptsbox@163.com
SPDX-License-Identifier: AGPL-3.0
"""
import os
import subprocess
import threading
import time
from pathlib import Path
from typing import Optional, Dict
from PySide2.QtCore import QObject, Signal, QCoreApplication
from app.utils import BmTools, BM_LOG
from app.servers.packages import PackagesManager


class NodeEnvManager(QObject):
    """
    Node.js 环境管理类
    职责：负责 Node.js 运行时分发、PNPM 配置生成、依赖安装及环境校验
    """
    node_runtime_install_progress = Signal(dict)

    def __init__(self):
        super().__init__()
        self.package = None  # 延迟加载 PackagesManager
        self.node_path: Optional[str] = None
        self.pnpm_path: Optional[str] = None

    # --- 核心主流程 ---

    def prepare_env(self, script_dir: str, node_spec: str = ">=v16.0", timeout: int = 300) -> bool:
        """
        为 Node 脚本准备环境（主控逻辑）
        """
        try:
            # 1. 前置校验
            script_path = Path(script_dir)
            if not (script_path / "package.json").exists():
                BM_LOG.info(f"目录 {script_dir} 无 package.json，跳过依赖安装")
                return True

            # 2. 获取工具路径
            self._emit_progress("正在获取 Node.js 运行时...")
            self.node_path = self._get_node_path(node_spec)
            self.pnpm_path = self._get_pnpm_path()

            # 3. 配置 .npmrc (锁定缓存与镜像源)
            self._emit_progress("正在配置全局缓存策略...")
            self._create_npmrc(script_dir)

            # 4. 安装依赖
            return self.install_dependencies(script_dir, timeout)

        except Exception as e:
            error_msg = f"Node 环境配置失败: {str(e)}"
            BM_LOG.error(error_msg)
            self._emit_progress(error_msg, False)
            raise RuntimeError(error_msg)

    @staticmethod
    def _should_forward_pnpm_line(line: str) -> bool:
        """过滤 pnpm 输出的无用行"""
        if not line:
            return False
        # 纯进度动画行：全是 + 和 ·
        if all(c in '+·' for c in line.strip()):
            return False
        lower = line.lower()
        if lower.startswith('packages are hard linked'):
            return False
        if lower.startswith('content-addressable store'):
            return False
        if lower.startswith('virtual store is at'):
            return False
        if lower.startswith('dependencies:'):
            return False
        if lower.startswith('+ '):
            return False
        return True

    def install_dependencies(self, script_dir: str, timeout: int = 300) -> bool:
        """
        使用 PNPM 安装依赖（流式输出进度）
        """
        self._emit_progress("正在同步 Node 依赖包 (pnpm)...")

        # 准备环境变量：将 Node 路径注入 PATH 头部
        env = self._get_isolated_env()

        # 构建命令：使用 --reporter append-only 减少不必要的动画输出，适合日志记录
        cmd = [
            str(self.pnpm_path),
            'install',
            '--reporter', 'append-only'
        ]
        process = subprocess.Popen(
            cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            text=True, encoding='utf-8', errors='replace',
            cwd=script_dir, env=env,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
        )

        stderr_lines = []
        stdout_lines = []
        last_emit_time = time.time()
        last_heartbeat_time = time.time()

        def _read_stdout():
            nonlocal last_emit_time
            try:
                for line in process.stdout:
                    line = line.rstrip('\n\r')
                    stdout_lines.append(line)
                    stripped = line.strip()
                    if stripped and self._should_forward_pnpm_line(stripped):
                        self._emit_progress(stripped)
                        last_emit_time = time.time()
            except:
                pass

        def _read_stderr():
            try:
                for line in process.stderr:
                    stderr_lines.append(line)
            except:
                pass

        stdout_thread = threading.Thread(target=_read_stdout, daemon=True)
        stderr_thread = threading.Thread(target=_read_stderr, daemon=True)
        stdout_thread.start()
        stderr_thread.start()

        _wait_start = time.time()
        while True:
            QCoreApplication.processEvents()
            now = time.time()
            if now - last_emit_time > 10 and now - last_heartbeat_time > 10:
                self._emit_progress("正在安装依赖，请稍候...")
                last_heartbeat_time = now
            if process.poll() is not None:
                break
            if time.time() - _wait_start > timeout:
                process.kill()
                raise RuntimeError(f"依赖安装超时（{timeout}秒）")

        stdout_thread.join(timeout=5)
        stderr_thread.join(timeout=5)

        if process.returncode == 0:
            self._emit_progress("Node 依赖安装完成", True)
            return True
        else:
            stderr_text = '\n'.join(stderr_lines)
            stdout_text = ''.join(stdout_lines)
            error_info = stderr_text or stdout_text
            raise RuntimeError(f"PNPM 安装退出码({process.returncode}): {error_info}")

    # --- 内部功能组件 ---

    def _get_isolated_env(self) -> Dict[str, str]:
        """构建隔离的 PATH 环境变量，确保子进程使用指定的 Node"""
        env = os.environ.copy()
        # 将我们分发的 node.exe 所在目录放到 PATH 最前面
        node_bin_dir = str(Path(self.node_path).parent)
        env['PATH'] = f"{node_bin_dir}{os.pathsep}{env.get('PATH', '')}"
        # 强制强制 UTF-8
        env['NODE_OPTIONS'] = '--input-type=module' if os.name != 'nt' else ''
        return env

    def _create_npmrc(self, script_dir: str):
        """创建 .npmrc 配置文件，优化缓存与路径"""
        # 路径逻辑参考 PyEnvManager 的 BmCache 统一管理
        base_cache = BmTools.get_root_path() / 'BmPackages' / 'BmCache' / 'node'
        cache_path = base_cache / 'pnpm-cache'
        store_path = base_cache / 'pnpm-store'

        # 确保缓存目录存在
        cache_path.mkdir(parents=True, exist_ok=True)
        store_path.mkdir(parents=True, exist_ok=True)

        npmrc_content = (
            "registry=https://registry.npmmirror.com/\n"
            f"cache-dir={cache_path}\n"
            f"store-dir={store_path}\n"
            "use-hardlinks=true\n"
            "symlink=true\n"
            "package-import-method=hardlink\n"
            "confirm-verifying-pnpm-version=false\n"
        )

        npmrc_path = Path(script_dir) / '.npmrc'
        # 仅在不存在或配置需要更新时写入
        with open(npmrc_path, 'w', encoding='utf-8') as f:
            f.write(npmrc_content)

    def _get_node_path(self, spec_str: str) -> str:
        if not self.package:
            self.package = PackagesManager()
            self.package.packages_progress.connect(self.node_runtime_install_progress.emit)

        path = self.package.install_cli('node',spec_str)
        if not path: raise RuntimeError(f"未能获取到满足 {spec_str} 的 Node.js 运行时")
        return path

    def _get_pnpm_path(self) -> str:
        if not self.package:
            self.package = PackagesManager()
        path = self.package.install_cli('pnpm')
        if not path: raise RuntimeError("未能获取到 PNPM 工具")
        return path

    def _emit_progress(self, msg: str, status: bool = True):
        self.node_runtime_install_progress.emit({'status': status, 'msg': msg})


if __name__ == '__main__':
    demo = NodeEnvManager()
    demo._get_pnpm_path()