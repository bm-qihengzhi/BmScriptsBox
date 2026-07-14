"""
Copyright (c) 2026 綦恒智
Email: bmscriptsbox@163.com
SPDX-License-Identifier: AGPL-3.0
"""
import shutil
from pathlib import Path
from typing import Optional
from PySide2.QtCore import QObject, Signal
from app.utils import BM_LOG
from app.servers.packages import PackagesManager


class AhkEnvManager(QObject):
    """
    AutoHotkey 环境管理类
    职责：负责 AHK 解释器（V1/V2）的安装、路径获取及环境校验
    """
    ahk_runtime_progress = Signal(dict)

    def __init__(self):
        super().__init__()
        self.package = None  # 延迟加载 PackagesManager

    # --- 核心主流程 ---

    def prepare_env(self, spec_str: str = ">=v1.0.0") -> Optional[str]:
        """
        准备 AHK 运行环境（主控逻辑）

        Args:
            spec_str: 版本要求，例如 ">=v1" 或 ">=v2"
        Returns:
            str: AutoHotkey.exe 的完整路径，失败返回 None
        """
        try:
            self._emit_progress(f"正在获取 AutoHotkey {spec_str} 运行时...")

            # 获取 AHK 路径（内部会调用 PackagesManager 安装或查找）
            ahk_exe_path = self._get_ahk_runtime(spec_str)

            if self._verify_runtime(ahk_exe_path):
                self._emit_progress("AHK 环境就绪", True)
                return ahk_exe_path
            else:
                raise FileNotFoundError(f"未找到 AHK 执行文件: {ahk_exe_path}")

        except Exception as e:
            error_msg = f"AHK 环境配置失败: {str(e)}"
            BM_LOG.error(error_msg)
            self._emit_progress(error_msg, False)
            return None

    # --- 内部功能组件 ---

    def _get_ahk_runtime(self, spec_str: str) -> str:
        """从包管理器获取 AHK 路径"""
        if not self.package:
            self.package = PackagesManager()
            self.package.packages_progress.connect(self.ahk_runtime_progress.emit)

        return self.package.install_cli(package_name='autohotkey', version_requirement=spec_str)

    def _verify_runtime(self, ahk_path: str) -> bool:
        """验证解释器是否真实存在"""
        if not ahk_path:
            return False
        return Path(ahk_path).exists()

    def _emit_progress(self, msg: str, status: bool = True):
        """发送进度信号"""
        self.ahk_runtime_progress.emit({'status': status, 'msg': msg})

    # --- 维护功能 ---

    def cleanup_runtime(self, runtime_dir: str) -> bool:
        """
        删除指定的 ahk 运行环境
        """
        try:
            path = Path(runtime_dir)
            if path.exists():
                shutil.rmtree(path)
                BM_LOG.info(f"成功清理 AHK 运行时: {runtime_dir}")
                return True
            return False
        except Exception as e:
            BM_LOG.error(f"清理 AHK 运行时失败: {e}")
            return False