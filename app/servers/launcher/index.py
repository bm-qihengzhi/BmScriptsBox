"""
Copyright (c) 2026 綦恒智
Email: bmscriptsbox@163.com
SPDX-License-Identifier: MIT
SPDX-License-Identifier: LicenseRef-Commons-Clause

开始菜单、UWP 应用扫描与命令面板缓存。
"""
import json
import os
import shutil
import subprocess
import time
from pathlib import Path
from typing import List, Tuple

from app.utils import BM_LOG, BmTools

CACHE_VERSION = 1


def start_menu_dirs() -> List[Path]:
    dirs = []
    appdata = os.environ.get("APPDATA")
    programdata = os.environ.get("ProgramData")
    if appdata:
        dirs.append(Path(appdata) / "Microsoft" / "Windows" / "Start Menu" / "Programs")
    if programdata:
        dirs.append(Path(programdata) / "Microsoft" / "Windows" / "Start Menu" / "Programs")
    return [path for path in dirs if path.is_dir()]


def scan_start_menu() -> List[dict]:
    results = []
    seen = set()
    for root in start_menu_dirs():
        try:
            paths = list(root.rglob("*.lnk")) + list(root.rglob("*.url"))
        except OSError as exc:
            BM_LOG.warning("扫描开始菜单失败 %s: %s" % (root, exc))
            continue
        for path in paths:
            name = path.stem.strip()
            if not name:
                continue
            lowered = name.lower()
            if "uninstall" in lowered or "卸载" in name or "readme" in lowered:
                continue
            key = (name.lower(), str(path).lower())
            if key in seen:
                continue
            seen.add(key)
            results.append({"name": name, "path": str(path)})
    results.sort(key=lambda item: item["name"].lower())
    return results


def scan_uwp(on_process=None, stop_event=None):
    powershell = shutil.which("powershell") or "powershell.exe"
    command = (
        "[Console]::OutputEncoding=[Text.Encoding]::UTF8; "
        "Get-StartApps | Select-Object Name,AppID | ConvertTo-Json -Compress"
    )
    process = None
    try:
        process = subprocess.Popen(
            [powershell, "-NoProfile", "-NonInteractive",
             "-ExecutionPolicy", "Bypass", "-Command", command],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        if on_process:
            on_process(process)
        started = time.monotonic()
        while True:
            if stop_event is not None and stop_event.is_set():
                process.terminate()
                try:
                    process.communicate(timeout=2)
                except subprocess.TimeoutExpired:
                    process.kill()
                return [], False
            try:
                stdout, stderr = process.communicate(timeout=0.2)
                break
            except subprocess.TimeoutExpired:
                if time.monotonic() - started > 30:
                    process.kill()
                    process.communicate()
                    BM_LOG.warning("获取 Get-StartApps 超时")
                    return [], False
    except Exception as exc:
        BM_LOG.warning("读取 Get-StartApps 失败: %s" % exc)
        return [], False
    finally:
        if on_process:
            on_process(None)

    if process.returncode != 0:
        BM_LOG.warning(
            "读取 Get-StartApps 失败: %s" % (
                (stderr or b"").decode("utf-8", "replace").strip()))
        return [], False

    output = (stdout or b"").decode("utf-8-sig", "replace").strip()
    if not output:
        return [], True

    try:
        data = json.loads(output)
    except ValueError as exc:
        BM_LOG.warning("解析 Get-StartApps 输出失败: %s" % exc)
        return [], False

    if isinstance(data, dict):
        data = [data]

    results = []
    for entry in data or []:
        if not isinstance(entry, dict):
            continue
        name = str(entry.get("Name") or "").strip()
        app_id = str(entry.get("AppID") or "").strip()
        if not name or "!" not in app_id:
            continue
        results.append({"name": name, "appid": app_id})

    results.sort(key=lambda item: item["name"].lower())
    return results, True


def cache_path() -> Path:
    path = BmTools.get_root_path() / "BmCache" / "launcher"
    path.mkdir(parents=True, exist_ok=True)
    return path / "apps.json"


def load_cache() -> Tuple[List[dict], List[dict]]:
    path = cache_path()
    if not path.exists():
        return [], []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        BM_LOG.warning("读取命令面板缓存失败: %s" % exc)
        return [], []
    if data.get("version") != CACHE_VERSION:
        return [], []
    start_menu = data.get("start_menu")
    uwp = data.get("uwp")
    return (start_menu if isinstance(start_menu, list) else [],
            uwp if isinstance(uwp, list) else [])


def save_cache(start_menu: List[dict], uwp: List[dict]):
    path = cache_path()
    data = {
        "version": CACHE_VERSION,
        "start_menu": start_menu,
        "uwp": uwp,
    }
    temp = path.with_suffix(".tmp")
    try:
        temp.write_text(json.dumps(data, ensure_ascii=False, indent=2),
                        encoding="utf-8")
        os.replace(str(temp), str(path))
    except OSError as exc:
        BM_LOG.warning("写入命令面板缓存失败: %s" % exc)
        try:
            temp.unlink()
        except OSError:
            pass
