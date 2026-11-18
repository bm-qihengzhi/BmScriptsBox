"""
Copyright (c) 2026 綦恒智
Email: bmscriptsbox@163.com
SPDX-License-Identifier: MIT
SPDX-License-Identifier: LicenseRef-Commons-Clause

搜索面板的市场脚本行内安装：复用 InstallCloudScriptWork，全局串行。
"""
from PySide6.QtCore import QObject, QTimer, Signal

from xsideui import tr

from app.utils import BM_LOG


class MarketInstallController(QObject):
    state_changed = Signal(str, str, str)     # item_id, state, detail
    finished = Signal(str, bool, str)         # item_id, ok, msg
    scripts_changed = Signal()

    def __init__(self, parent=None, work_factory=None):
        super().__init__(parent)
        self._work_factory = work_factory
        self._work = None
        self._download_work = None
        self._active_id = ""
        self._active_script_id = ""
        self._parent_widget = None
        self._closing = False

    @property
    def is_busy(self) -> bool:
        return bool(self._active_id)

    def install(self, item, parent=None) -> bool:
        if self._closing or item is None:
            return False
        if getattr(item, "kind", "") != "market_script":
            return False
        state = getattr(item, "state", "") or ""
        if state in ("installed", "installing"):
            return False
        if self._active_id == getattr(item, "id", ""):
            return False

        payload = item.payload if isinstance(item.payload, dict) else {}
        script_id = str(payload.get("script_id") or "")
        repo = str(payload.get("repository_url") or "")
        branch = str(payload.get("default_branch") or "master")
        if not script_id or not repo:
            self.state_changed.emit(item.id, "invalid", "")
            self.finished.emit(item.id, False, tr("Incomplete install info"))
            return False

        if self._active_id:
            self.state_changed.emit(item.id, "waiting", "")
            QTimer.singleShot(
                2500, lambda iid=item.id: self._clear_busy_status(iid))
            return False

        work_cls = self._work_factory
        if work_cls is None:
            from app.works.script_work import InstallCloudScriptWork
            work_cls = InstallCloudScriptWork
        work = work_cls(script_id=script_id, script_git_url=repo,
                        branch=branch)
        work.progress_signal.connect(
            lambda data: self._on_progress(item.id, data))
        work.finished_signal.connect(
            lambda data: self._on_finished(item.id, data))
        work.consent_signal.connect(self._on_consent)
        work.finished.connect(work.deleteLater)

        self._work = work
        self._active_id = item.id
        self._active_script_id = script_id
        self._parent_widget = parent
        self.state_changed.emit(item.id, "installing", "")
        work.start()
        return True

    def shutdown(self):
        self._closing = True
        work = self._work
        if work is not None:
            try:
                if not work.wait(3000):
                    work.terminate()
                    work.wait(1000)
            except Exception:
                pass
        self._work = None
        self._active_id = ""
        self._active_script_id = ""

    # ---------- 回调 ----------

    def _on_progress(self, item_id: str, data):
        if self._closing:
            return
        msg = ""
        if isinstance(data, dict):
            msg = str(data.get("msg") or "").strip()
        self.state_changed.emit(item_id, "installing", msg)

    def _on_finished(self, item_id: str, data):
        if self._closing:
            return
        script_id = self._active_script_id
        self._work = None
        self._active_id = ""
        self._active_script_id = ""
        ok = bool(isinstance(data, dict) and data.get("status"))
        msg = str(data.get("msg") or "") if isinstance(data, dict) else ""
        if ok:
            self.state_changed.emit(item_id, "installed", "")
            self._record_download(script_id)
            self.finished.emit(item_id, True, msg)
            self.scripts_changed.emit()
        else:
            self.state_changed.emit(item_id, "failed", msg)
            self.finished.emit(item_id, False, msg)

    def _ask_consent(self, payload):
        from app.view.script_ui.binary_consent_dialog import (
            BinaryConsentDialog)
        dialog = BinaryConsentDialog(payload, parent=self._parent_widget)
        dialog.exec()
        return dialog.get_result()

    def _on_consent(self, payload):
        allow, remember = False, False
        try:
            allow, remember = self._ask_consent(payload)
        except Exception as exc:
            BM_LOG.error(f"二进制确认弹窗异常: {exc}")
        finally:
            payload["_result"] = {"allow": allow, "remember": remember}
            event = payload.get("_event")
            if event is not None:
                event.set()

    def _record_download(self, script_id: str):
        if not script_id:
            return
        try:
            from app.cloud.works.market_work import AddDownloadWork
            work = AddDownloadWork(script_id)
            work.finished.connect(work.deleteLater)
            work.start()
            self._download_work = work
        except Exception as exc:
            BM_LOG.warning(f"记录市场下载失败: {exc}")

    def _clear_busy_status(self, item_id: str):
        if item_id != self._active_id:
            self.state_changed.emit(item_id, "", "")
