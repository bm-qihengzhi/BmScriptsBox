"""
Copyright (c) 2026 綦恒智
Email: bmscriptsbox@163.com
SPDX-License-Identifier: MIT
SPDX-License-Identifier: LicenseRef-Commons-Clause

后台桌面应用图标提取：PowerShell/.NET -> PNG，完全避开 Qt UI 线程。
"""
import json
import shutil
import subprocess
import tempfile
import threading
from pathlib import Path

from PySide6.QtCore import QThread, Signal

from app.utils import BM_LOG

_POWERSHELL_SCRIPT = r"""
param([string]$JobsPath)
[Console]::OutputEncoding=[Text.Encoding]::UTF8
Add-Type -AssemblyName System.Drawing
$jobs = Get-Content -LiteralPath $JobsPath -Raw -Encoding UTF8 | ConvertFrom-Json
$results = @()
foreach ($job in @($jobs)) {
    try {
        $icon = [System.Drawing.Icon]::ExtractAssociatedIcon([string]$job.path)
        if ($icon) {
            $bmp = $icon.ToBitmap()
            $bmp.Save([string]$job.output, [System.Drawing.Imaging.ImageFormat]::Png)
            $bmp.Dispose()
            $icon.Dispose()
            $results += [pscustomobject]@{ key = [string]$job.key; ok = $true }
        } else {
            $results += [pscustomobject]@{ key = [string]$job.key; ok = $false }
        }
    } catch {
        $results += [pscustomobject]@{ key = [string]$job.key; ok = $false }
    }
}
$results | ConvertTo-Json -Compress
"""


class IconExtractWorker(QThread):
    processed = Signal(list, list)

    def __init__(self, jobs, parent=None):
        super().__init__(parent)
        self._jobs = list(jobs)
        self._cancelled = threading.Event()
        self._process = None
        self._process_lock = threading.Lock()

    def cancel(self):
        self._cancelled.set()
        with self._process_lock:
            process = self._process
        if process is not None:
            try:
                process.terminate()
                process.wait(timeout=1)
            except Exception:
                try:
                    process.kill()
                except Exception:
                    pass

    def _set_process(self, process):
        with self._process_lock:
            self._process = process

    def run(self):
        keys = [job[1] for job in self._jobs]
        if not self._jobs or self._cancelled.is_set():
            self.processed.emit([], [])
            return

        powershell = shutil.which("powershell") or "powershell.exe"
        temp_dir = Path(tempfile.gettempdir()) / "bm-icon-worker"
        temp_dir.mkdir(parents=True, exist_ok=True)
        jobs_file = temp_dir / ("jobs_%s.json" % id(self))
        script_file = temp_dir / "extract_icon.ps1"
        try:
            payload = [
                {"path": path, "output": output, "key": key}
                for path, key, output in self._jobs
            ]
            jobs_file.write_text(json.dumps(payload, ensure_ascii=False),
                                 encoding="utf-8")
            script_file.write_text(_POWERSHELL_SCRIPT, encoding="utf-8-sig")

            process = subprocess.Popen(
                [powershell, "-NoProfile", "-NonInteractive",
                 "-ExecutionPolicy", "Bypass", "-File", str(script_file),
                 str(jobs_file)],
                stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
            self._set_process(process)
            stdout, stderr = process.communicate(timeout=60)
            self._set_process(None)

            if self._cancelled.is_set():
                self.processed.emit([], [])
                return
            if process.returncode != 0:
                BM_LOG.warning("图标提取失败: %s" % (
                    (stderr or b"").decode("utf-8", "replace")[-500:]))
                self.processed.emit([], keys)
                return

            text = (stdout or b"").decode("utf-8-sig", "replace").strip()
            data = json.loads(text or "[]")
            if isinstance(data, dict):
                data = [data]
            success = []
            failed = []
            for entry in data:
                key = str(entry.get("key") or "")
                if not key:
                    continue
                if entry.get("ok"):
                    success.append(key)
                else:
                    failed.append(key)
            missing = [key for key in keys if key not in success and key not in failed]
            failed.extend(missing)
            self.processed.emit(success, failed)
        except subprocess.TimeoutExpired:
            self.cancel()
            self.processed.emit([], keys)
        except Exception as exc:
            BM_LOG.warning("图标提取异常: %s" % exc)
            self.processed.emit([], keys)
        finally:
            self._set_process(None)
            for path in (jobs_file, script_file):
                try:
                    path.unlink()
                except OSError:
                    pass
