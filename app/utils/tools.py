"""
Copyright (c) 2026 綦恒智
Email: bmscriptsbox@163.com
SPDX-License-Identifier: AGPL-3.0
"""
import json
import locale
import os
import shutil
import stat
import sys
import threading
import time
import ctypes
from pathlib import Path
from typing import List
from PySide2.QtNetwork import QLocalSocket
from xsideui import XI18N

from app.data import ProjectGlobal
from app.utils import BM_LOG

# 待删队列文件读写锁（启动清理线程与卸载线程可能并发）
_pending_deletions_lock = threading.RLock()


class BmTools:

    @staticmethod
    def get_root_path() -> Path:
        """获取项目根目录（存放 BmScripts/BmPackages/BmData 等运行时目录）"""
        return Path(__file__).parents[2]

    @staticmethod
    def get_resources_path() -> Path:
        """获取资源文件目录（configs.json/图片/i18n 等）"""
        return Path(__file__).parent.parent / 'resources'

    @staticmethod
    def get_script_dir_path(script_id: str) -> Path:
        """获取脚本目录路径"""
        return BmTools.get_root_path() / 'BmScripts' / script_id

    @staticmethod
    def get_temp_context(file_path: str) -> List[str]:
        """
        获取文件中一行一行的内容，返回列表

        Args:
            file_path: 文件路径

        Returns:
            去除换行符后的每行内容列表
        """
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                return [line.rstrip('\n') for line in f]
        except FileNotFoundError:
            return []


    @staticmethod
    def get_logo_path() -> str:
        """获取logo路径"""
        return str(BmTools.get_resources_path() / 'imgs' / 'logo.svg')

    @staticmethod
    def get_language_icon_path(language) -> str:
        """获取编程语言图标"""
        return str(BmTools.get_resources_path() / 'language' / f"{language}.png")

    @staticmethod
    def set_win32_logo():
        """设置 Windows 任务栏进程标识符以确保图标正确显示"""
        if sys.platform == 'win32':
            # 确保windows任务栏能正确显示图标，字符串标识符（格式：公司名.产品名.子模块.版本号）
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(
                '瞎忙软件开发工作室.不忙脚本盒子.不忙脚本盒子.v0.0.1')

    @staticmethod
    def get_base_scripts_path() -> Path:
        """返回BmScripts Path路径"""
        return BmTools.get_root_path() / 'BmScripts'

    @staticmethod
    def is_chinese_env() -> bool:
        """判断运行环境是否为中文"""
        lang, _ = locale.getdefaultlocale()
        if lang and lang.startswith('zh'):
            return True
        return False

    @staticmethod
    def set_language():
        """程序初始化时根据配置设置软件语言"""
        # 设置自定义语言包
        XI18N.add_custom_lang_path(str(BmTools.get_resources_path() / 'i18n'), 'BmscriptsBox')
        config_path = BmTools.get_resources_path() / 'configs.json'
        if not config_path.exists():
            BM_LOG.error("No configs.json found")
            return

        with open(config_path, "r", encoding="utf-8") as f:
            configs = json.load(f)
            language = configs.get("LANGUAGE")
            if not language:
                language = "zh_CN" if BmTools.is_chinese_env() else "en_US"
            ProjectGlobal.LANGUAGE = language
            XI18N.set_language(language)
            ProjectGlobal.PROXIES = configs.get("PROXIES", ProjectGlobal.PROXIES)

    # --- 待删队列：处理无法立即删除的目录（启动时重试） ---

    @staticmethod
    def _pending_deletions_file() -> Path:
        return BmTools.get_root_path() / 'BmData' / 'pending_deletions.json'

    @staticmethod
    def load_pending_deletions() -> List[str]:
        """读取待删路径列表"""
        with _pending_deletions_lock:
            try:
                file = BmTools._pending_deletions_file()
                if file.exists():
                    return json.loads(file.read_text(encoding='utf-8'))
            except Exception as e:
                BM_LOG.warning(f"读取待删队列失败: {e}")
            return []

    @staticmethod
    def add_pending_deletion(path: Path):
        """记录待删路径，下次启动时重试"""
        with _pending_deletions_lock:
            try:
                paths = BmTools.load_pending_deletions()
                p = str(path.resolve())
                if p not in paths:
                    paths.append(p)
                file = BmTools._pending_deletions_file()
                file.parent.mkdir(parents=True, exist_ok=True)
                file.write_text(json.dumps(paths, ensure_ascii=False), encoding='utf-8')
                BM_LOG.info(f"已加入启动清理队列: {p}")
            except Exception as e:
                BM_LOG.warning(f"记录待删路径失败: {e}")

    @staticmethod
    def cleanup_pending_deletions():
        """应用启动时重试删除待删路径"""
        with _pending_deletions_lock:
            try:
                paths = BmTools.load_pending_deletions()
                if not paths:
                    return
                remaining = []
                for p in paths:
                    path = Path(p)
                    if path.exists() and BmTools.remove_dir(path):
                        BM_LOG.info(f"启动时清理残留目录成功: {path}")
                    elif path.exists():
                        remaining.append(p)
                file = BmTools._pending_deletions_file()
                file.write_text(json.dumps(remaining, ensure_ascii=False), encoding='utf-8')
            except Exception as e:
                BM_LOG.warning(f"启动清理待删目录失败: {e}")

    @staticmethod
    def mark_reboot_delete(path: Path) -> bool:
        """
        标记重启后删除（需管理员权限，非管理员会失败）。
        返回 True 表示已成功标记；False 表示不可用，需走待删队列
        """
        try:
            movefileex = ctypes.windll.kernel32.MoveFileExW
            movefileex.restype = ctypes.c_bool
            if movefileex(str(path.resolve()), None, 4):
                BM_LOG.info(f"已标记重启后删除: {path}")
                return True
            BM_LOG.warning("标记重启删除失败（通常因非管理员权限），将走启动清理队列")
        except Exception as e:
            BM_LOG.warning(f"标记重启删除异常: {e}")
        return False

    @staticmethod
    def remove_dir(path: Path, max_retries: int = 3) -> bool:
        """
        带只读文件处理和重试的目录删除，兼容 Python 3.8+
        内部依次尝试：onerror 修复权限 → \\?\ 长路径绕过 → 重试 → 重启删除/待删队列

        Args:
            path: 要删除的目录
            max_retries: 重试次数（默认 3）

        Returns:
            True 删除成功或目录不存在，False 删除失败（可能已标记重启删除或进待删队列）
        """
        if not path.exists():
            return True

        def _on_rm_error(func, p, exc_info):
            os.chmod(p, stat.S_IWRITE)
            func(p)

        def _long_rmtree(p: Path):
            long_root = '\\\\?\\' + str(p.resolve())
            try:
                for root, dirs, files in os.walk(long_root, topdown=False):
                    for name in files:
                        fp = os.path.join(root, name)
                        try:
                            os.chmod(fp, stat.S_IWRITE)
                            os.remove(fp)
                        except Exception:
                            pass
                    for name in dirs:
                        fp = os.path.join(root, name)
                        try:
                            os.rmdir(fp)
                        except Exception:
                            pass
                os.rmdir(long_root)
            except Exception:
                pass
            return not p.exists()

        def _try_once(use_long_path=False):
            if use_long_path:
                return _long_rmtree(path)
            shutil.rmtree(path, onerror=_on_rm_error)
            return not path.exists()

        # 首次尝试（onerror 修复只读）
        try:
            if _try_once():
                return True
        except Exception:
            pass

        # 首次失败后立即 \\?\ 长路径 fallback
        if _long_rmtree(path):
            return True

        # 重试 + 指数退避
        wait = 1
        for attempt in range(max_retries):
            try:
                if _try_once(use_long_path=(attempt > 0)):
                    return True
            except Exception:
                pass
            if attempt < max_retries - 1:
                time.sleep(wait)
                wait *= 2

        # 最后兜底：标记重启后删除（失败则进待删队列，启动时重试）
        if not BmTools.mark_reboot_delete(path):
            BmTools.add_pending_deletion(path)

        return False

    @staticmethod
    def is_already_running(app_name):
        socket = QLocalSocket()
        socket.connectToServer(app_name)
        return socket.waitForConnected(500)



