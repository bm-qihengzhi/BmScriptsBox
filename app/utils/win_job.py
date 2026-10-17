"""
Copyright (c) 2026 綦恒智
Email: bmscriptsbox@163.com
SPDX-License-Identifier: MIT
SPDX-License-Identifier: LicenseRef-Commons-Clause

Windows Job Object 封装：把脚本进程加入启用了 KILL_ON_JOB_CLOSE 的作业对象，
关闭作业句柄时连同其子孙进程一并结束，避免关盒后残留后台进程。
非 Windows 平台或创建/加入失败时，assign 返回 False，调用方回退 proc.kill()。
"""
import sys
import threading

_IS_WINDOWS = (sys.platform == 'win32')

if _IS_WINDOWS:
    import ctypes
    from ctypes import wintypes

    _kernel32 = ctypes.WinDLL('kernel32', use_last_error=True)

    _JobObjectExtendedLimitInformation = 9
    _JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE = 0x00002000

    class _IO_COUNTERS(ctypes.Structure):
        _fields_ = [
            ("ReadOperationCount", ctypes.c_ulonglong),
            ("WriteOperationCount", ctypes.c_ulonglong),
            ("OtherOperationCount", ctypes.c_ulonglong),
            ("ReadTransferCount", ctypes.c_ulonglong),
            ("WriteTransferCount", ctypes.c_ulonglong),
            ("OtherTransferCount", ctypes.c_ulonglong),
        ]

    class _JOBOBJECT_BASIC_LIMIT_INFORMATION(ctypes.Structure):
        _fields_ = [
            ("PerProcessUserTimeLimit", ctypes.c_longlong),
            ("PerJobUserTimeLimit", ctypes.c_longlong),
            ("LimitFlags", wintypes.DWORD),
            ("MinimumWorkingSetSize", ctypes.c_size_t),
            ("MaximumWorkingSetSize", ctypes.c_size_t),
            ("ActiveProcessLimit", wintypes.DWORD),
            ("Affinity", ctypes.c_size_t),
            ("PriorityClass", wintypes.DWORD),
            ("SchedulingClass", wintypes.DWORD),
        ]

    class _JOBOBJECT_EXTENDED_LIMIT_INFORMATION(ctypes.Structure):
        _fields_ = [
            ("BasicLimitInformation", _JOBOBJECT_BASIC_LIMIT_INFORMATION),
            ("IoInfo", _IO_COUNTERS),
            ("ProcessMemoryLimit", ctypes.c_size_t),
            ("JobMemoryLimit", ctypes.c_size_t),
            ("PeakProcessMemoryUsed", ctypes.c_size_t),
            ("PeakJobMemoryUsed", ctypes.c_size_t),
        ]

    _kernel32.CreateJobObjectW.restype = wintypes.HANDLE
    _kernel32.CreateJobObjectW.argtypes = [wintypes.LPVOID, wintypes.LPCWSTR]
    _kernel32.SetInformationJobObject.restype = wintypes.BOOL
    _kernel32.SetInformationJobObject.argtypes = [
        wintypes.HANDLE, ctypes.c_int, wintypes.LPVOID, wintypes.DWORD]
    _kernel32.AssignProcessToJobObject.restype = wintypes.BOOL
    _kernel32.AssignProcessToJobObject.argtypes = [wintypes.HANDLE, wintypes.HANDLE]
    _kernel32.CloseHandle.restype = wintypes.BOOL
    _kernel32.CloseHandle.argtypes = [wintypes.HANDLE]


class WinJob:
    """进程树作业对象；assign 失败或非 Windows 时 close/kill 均为安全无操作。"""

    def __init__(self):
        self._handle = None
        self._closed = False
        if not _IS_WINDOWS:
            return
        try:
            handle = _kernel32.CreateJobObjectW(None, None)
            if not handle:
                return
            info = _JOBOBJECT_EXTENDED_LIMIT_INFORMATION()
            info.BasicLimitInformation.LimitFlags = _JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
            ok = _kernel32.SetInformationJobObject(
                handle, _JobObjectExtendedLimitInformation,
                ctypes.byref(info), ctypes.sizeof(info))
            if not ok:
                _kernel32.CloseHandle(handle)
                return
            self._handle = handle
        except Exception:
            self._handle = None

    def assign(self, process) -> bool:
        """把已启动进程加入作业；成功返回 True（close 时连带结束子孙进程）。"""
        if not self._handle or self._closed:
            return False
        try:
            ph = getattr(process, '_handle', None)
            if ph is None:
                return False
            return bool(_kernel32.AssignProcessToJobObject(
                self._handle, wintypes.HANDLE(int(ph))))
        except Exception:
            return False

    def close(self):
        if self._handle and not self._closed:
            try:
                _kernel32.CloseHandle(self._handle)
            except Exception:
                pass
            self._closed = True
            self._handle = None


# --- 会话级单例作业 ---
# 盒子存活期间只持有一个作业句柄：把每个脚本进程加入其中，正常退出时不打扰脚本
# 自行游离的子孙进程；仅在盒子关闭（terminate_all）时关闭作业句柄，连同残留的
# 子孙进程一并结束。避免“启动器脚本拉起应用后退出”被误杀，也避免每轮泄漏句柄。
_GLOBAL_JOB = None
_GLOBAL_LOCK = threading.Lock()


def get_global_job():
    """获取（必要时创建）会话级作业对象；创建失败返回句柄为空的实例（assign 恒 False）。"""
    global _GLOBAL_JOB
    with _GLOBAL_LOCK:
        if _GLOBAL_JOB is None:
            _GLOBAL_JOB = WinJob()
        return _GLOBAL_JOB


def close_global_job():
    """关闭会话级作业（KILL_ON_JOB_CLOSE 结束其中仍存活的所有子孙进程）。"""
    global _GLOBAL_JOB
    with _GLOBAL_LOCK:
        if _GLOBAL_JOB is not None:
            _GLOBAL_JOB.close()
            _GLOBAL_JOB = None
