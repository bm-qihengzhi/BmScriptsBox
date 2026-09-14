"""
Copyright (c) 2026 綦恒智
Email: bmscriptsbox@163.com
SPDX-License-Identifier: MIT
SPDX-License-Identifier: LicenseRef-Commons-Clause

参数表单启动助手：统一弹「参数设置」对话框，返回 (data, params) 或 None（取消）。
自动区分 GUI 线程 / 非 GUI 线程——热键(QThread)、右键(Flask HTTP 线程)等非 GUI 线程
经一个常驻 GUI 线程的桥阻塞等结果。
"""
from PySide2.QtCore import QObject, Signal, Qt, QThread

from app.utils import BmNotify
from .params_prompt_dialog import ParamsPromptDialog


class _PromptBridge(QObject):
    """常驻 GUI 线程的桥：非 GUI 线程 emit 后阻塞，直到 GUI 弹窗完成写回结果。"""
    requested = Signal(dict)

    def _run(self, payload):
        result = None
        try:
            script_info = payload.get('script')
            if script_info is not None:
                dlg = ParamsPromptDialog(
                    script_info,
                    parent=payload.get('parent'),
                    default_data=payload.get('data') or [],
                    prefill_params=payload.get('prefill') or None,
                )
                if dlg.exec_():
                    result = (dlg.get_inputs_value(), dlg.get_params_overrides())
        except Exception as e:
            from app.utils import BM_LOG
            BM_LOG.error(f"参数表单弹窗异常: {e}")
        payload['result'] = result


_bridge = None
_bridge_connected = False


def _ensure_bridge(gui_window):
    global _bridge, _bridge_connected
    if _bridge is None:
        _bridge = _PromptBridge()
        _bridge.moveToThread(gui_window.thread())  # 桥常驻 GUI 线程
    if not _bridge_connected:
        _bridge.requested.connect(_bridge._run, Qt.BlockingQueuedConnection)
        _bridge_connected = True


def _save_memory(script_id, params):
    """参数确认运行后，记住上次的值供下次回填"""
    try:
        from app.data.database import ScriptDatabase
        ScriptDatabase().save_param_memory(script_id, params)
    except Exception:
        pass


def show_params_prompt(script_info, default_data, parent=None):
    """
    弹参数设置对话框。
    返回 (data, params)；用户取消 / 出错 → None（调用方不应启动）。
    可在任意线程调用；非 GUI 线程会阻塞等待用户。
    """
    from app.data.database import ScriptDatabase
    memory = ScriptDatabase().get_param_memory(script_info.id) or {}
    from app.utils import BM_LOG
    window = BmNotify._main_window or parent
    if window is None:
        BM_LOG.warning("[params_form] 无主窗口可承载弹窗，跳过参数表单")
        return default_data, {}

    if QThread.currentThread() is window.thread():
        # 已在 GUI 线程：直接弹
        try:
            dlg = ParamsPromptDialog(script_info, parent=window, default_data=default_data or [],
                                     prefill_params=memory or None)
            if not dlg.exec_():
                return None
            params = dlg.get_params_overrides()
            _save_memory(script_info.id, params)
            return (dlg.get_inputs_value(), params)
        except Exception as e:
            BM_LOG.error(f"参数表单弹窗异常: {e}")
            return default_data, {}

    # 非 GUI 线程：经桥阻塞等 GUI 处理
    _ensure_bridge(window)
    payload = {
        'script': script_info,
        'data': default_data or [],
        'prefill': memory or {},
        'parent': window,
        'result': None,
    }
    try:
        _bridge.requested.emit(payload)  # BlockingQueuedConnection → 阻塞到 GUI 弹窗完成
    except Exception as e:
        BM_LOG.error(f"参数表单桥接异常: {e}")
        return default_data, {}
    result = payload.get('result')
    if result is not None:
        params = result[1]
        _save_memory(script_info.id, params)
    return result