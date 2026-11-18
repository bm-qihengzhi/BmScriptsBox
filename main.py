"""
Copyright (c) 2026 綦恒智
Email: bmscriptsbox@163.com
SPDX-License-Identifier: MIT
SPDX-License-Identifier: LicenseRef-Commons-Clause
"""
import sys
import ctypes
import faulthandler
import traceback
from datetime import datetime
from pathlib import Path

_ROOT = (Path(sys.executable).parent if getattr(sys, 'frozen', False)
         else Path(__file__).parent.absolute())

if not getattr(sys, 'frozen', False):
    sys.path.insert(0, str(_ROOT))

# 启动早期接管崩溃输出：windowed 版 exe 没有控制台，native 崩溃（如 DLL 缺失、
# PySide6 与解释器版本不匹配）会直接静默退出，这里把栈写进 BmLogs/crash.log
_CRASH_LOG = _ROOT / 'BmLogs' / 'crash.log'
try:
    _CRASH_LOG.parent.mkdir(parents=True, exist_ok=True)
    _crash_stream = open(_CRASH_LOG, 'a', buffering=1, encoding='utf-8', errors='replace')
    _crash_stream.write(f'\n===== {datetime.now():%Y-%m-%d %H:%M:%S} 启动 =====\n')
    _crash_stream.write(f'python {sys.version.split()[0]}  exe={sys.executable}\n')
    faulthandler.enable(file=_crash_stream, all_threads=True)
except Exception:
    _crash_stream = None


def _fatal(message: str):
    """启动阶段失败时的兜底提示：写日志 + 弹窗，避免双击后毫无反应"""
    try:
        if _crash_stream is not None:
            _crash_stream.write(message + '\n')
    except Exception:
        pass
    try:
        ctypes.windll.user32.MessageBoxW(
            0, message, '不忙脚本盒子 - 启动失败', 0x10)
    except Exception:
        pass
    sys.exit(1)



# ---------- 运行环境自愈 ----------
# 1.5.x（Python 3.8 + PySide2）被 2.0.0 覆盖升级时，旧的运行时文件不会随清单删除。
# 残留的 PySide2 / shiboken2（cp38）会被 xsideui 的 xicons_rc「PySide2 优先」导入命中，
# 在 3.12 下直接 access violation。这里在导入 PySide6 之前把已知残留清掉。
_RUNTIME_DIR = _ROOT / 'runtime'
_RUNTIME_RESIDUE = (
    _RUNTIME_DIR / 'Lib' / 'site-packages' / 'PySide2',
    _RUNTIME_DIR / 'Lib' / 'site-packages' / 'shiboken2',
    _RUNTIME_DIR / 'python38.dll',
    _RUNTIME_DIR / 'python38.zip',
    _RUNTIME_DIR / 'python38._pth',
    _RUNTIME_DIR / 'python.cat',
    _RUNTIME_DIR / 'libcrypto-1_1.dll',
    _RUNTIME_DIR / 'libssl-1_1.dll',
    _RUNTIME_DIR / 'libffi-7.dll',
)


def _runtime_residue():
    """仅当解释器已是 3.12 才把旧文件判定为残留，避免误删旧版本自身的运行环境"""
    if sys.version_info[:2] < (3, 12):
        return []
    return [path for path in _RUNTIME_RESIDUE if path.exists()]


def _remove_runtime_residue():
    import shutil

    removed, failed = [], []
    for path in _runtime_residue():
        try:
            if path.is_dir():
                shutil.rmtree(path)
            else:
                path.unlink()
            removed.append(path.name)
        except OSError as exc:
            failed.append('%s (%s)' % (path.name, exc))
    return removed, failed


def _log_repair(message: str):
    try:
        if _crash_stream is not None:
            _crash_stream.write(message + '\n')
    except Exception:
        pass


def _repair_and_relaunch():
    """提权进程入口：清理残留后重新拉起主程序（本次以管理员权限启动）"""
    removed, failed = _remove_runtime_residue()
    _log_repair('运行环境自愈: 删除 %d 项 %s' % (len(removed), removed))
    if failed:
        _fatal('运行环境清理失败：\n\n' + '\n'.join(failed) +
               '\n\n请手动删除上面这些文件后重新启动，或卸载后重新安装。')

    import subprocess

    try:
        subprocess.Popen([sys.executable, str(Path(__file__).resolve())],
                         cwd=str(_ROOT))
    except Exception as exc:
        _fatal('运行环境已修复，但重新启动失败：%s\n请手动打开程序。' % exc)
    return 0


def _ensure_runtime_clean():
    """检测跨版本升级残留；无写权限时请求提权后修复"""
    residue = _runtime_residue()
    if not residue:
        return

    _log_repair('检测到旧运行环境残留: %s' % [path.name for path in residue])
    removed, failed = _remove_runtime_residue()
    if not failed:
        _log_repair('运行环境自愈完成: %s' % removed)
        return

    # 安装目录在 Program Files 等位置时普通进程无写权限，提权重启自身执行修复
    _log_repair('无写权限，请求提权: %s' % failed)
    params = '"%s" --repair-runtime' % Path(__file__).resolve()
    try:
        result = ctypes.windll.shell32.ShellExecuteW(
            None, 'runas', sys.executable, params, str(_ROOT), 1)
    except Exception:
        result = 0

    if int(result or 0) <= 32:
        ctypes.windll.user32.MessageBoxW(
            0,
            '检测到旧版本的运行环境残留，需要管理员权限才能清理。\n\n'
            '请右键本程序选择「以管理员身份运行」再试一次，'
            '或卸载后重新安装。',
            '不忙脚本盒子 - 更新未完成', 0x10)
        sys.exit(1)
    sys.exit(0)


# 提权修复进程：只做清理，随后拉起主程序
if '--repair-runtime' in sys.argv:
    sys.exit(_repair_and_relaunch())

# 跨版本升级残留自愈（必须在导入 PySide6 之前）
_ensure_runtime_clean()

# 加载纯 Python 包 zip（嵌入式打包需要、不用可注释）
_pure_zip = _ROOT / 'runtime' / 'Lib' / 'site-packages' / '_pure_packages.zip'
if _pure_zip.exists():
    sys.path.insert(0, str(_pure_zip))

try:
    from PySide6.QtCore import Qt, QTimer
    from PySide6.QtWidgets import QApplication
    from PySide6.QtNetwork import QLocalServer
except ImportError as exc:
    _fatal(f'PySide6 导入失败：{exc}\n\n运行时目录可能与当前 Python 版本不匹配。\n'
           f'Python: {sys.version.split()[0]}\n运行环境: {sys.executable}')

try:
    from app.view.shell.app_shell import ApplicationShell
    from app.utils.tools import BmTools
except Exception:
    _fatal('应用模块导入失败：\n\n' + traceback.format_exc())


main_window = None

def handle_new_connection(server):
    """当第二个实例尝试启动时触发"""
    socket = server.nextPendingConnection()
    if socket:
        socket.close()
    global main_window
    if main_window:
        main_window.show_launcher()


def watch_console():
    """检测后续代码意外创建的控制台并分离"""
    if sys.platform == 'win32':
        hwnd = ctypes.windll.kernel32.GetConsoleWindow()
        if hwnd:
            ctypes.windll.kernel32.FreeConsole()


def main():
    app_id = "BmScriptsBox_Unique_ID"

    # 1. 预检查
    if BmTools.is_already_running(app_id):
        sys.exit(0)

    # 2. 创建应用实例
    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough)
    app = QApplication(sys.argv)

    # 3.  单例守护
    server = QLocalServer(app)  # 绑定到 app 自动销毁
    if not server.listen(app_id):
        QLocalServer.removeServer(app_id)
        server.listen(app_id)
    server.newConnection.connect(lambda: handle_new_connection(server))

    # 5. 语言/图标设置
    BmTools.set_win32_logo()
    BmTools.set_language()
    app.setQuitOnLastWindowClosed(False)

    # 6. 后台清理上次残留目录
    import threading
    threading.Thread(target=BmTools.cleanup_pending_deletions, daemon=True).start()

    # 7. 启动窗口
    global main_window
    main_window = ApplicationShell()
    main_window.launch()
    sys.exit(app.exec())





if __name__ == '__main__':
    main()

