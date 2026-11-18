"""
Copyright (c) 2026 綦恒智
Email: bmscriptsbox@163.com
SPDX-License-Identifier: MIT
SPDX-License-Identifier: LicenseRef-Commons-Clause

命令面板聚合搜索与索引服务。
"""
import math
import os
import re
import subprocess
import threading
from datetime import datetime
from pathlib import Path
from typing import List, Optional

from PySide6.QtCore import QFileSystemWatcher, QObject, QThread, QTimer, Signal

from xsideui import IconName

from app.utils import BM_LOG, BmTools
from app.utils.pinyin_search import PinyinSearchIndex, normalize

from .dedupe import aliases_for_key, app_dedupe_key
from .index import (load_cache, save_cache, scan_start_menu, scan_uwp,
                    start_menu_dirs)
from .input_match import InputMatchIndex
from .models import SearchItem
from .system_catalog import system_items
from .text_score import (compact, field_score, has_cjk, normalize_terms,
                         term_coverage)

_PROVIDER_WEIGHT = {
    "scripts": 1.0,
    "start_menu": 0.96,
    "uwp": 0.94,
    "system": 0.90,
}
_PROVIDER_PRIORITY = {
    "scripts": 4,
    "start_menu": 3,
    "uwp": 2,
    "system": 1,
}
def _script_aux_text(script) -> str:
    parts = []
    for schema in (getattr(script, "inputs_schema", None) or []):
        if isinstance(schema, dict):
            parts.extend((schema.get("label"), schema.get("description")))
    for param in (getattr(script, "params_schema", None) or []):
        if isinstance(param, dict):
            parts.extend((param.get("label"), param.get("description")))
    return " ".join(str(part) for part in parts if part)


def _script_usage_boost(script) -> float:
    try:
        run_count = int(getattr(script, "run_count", 0) or 0)
    except (TypeError, ValueError):
        run_count = 0
    boost = min(math.log10(run_count + 1), 2.0) * 2.0
    last_run = getattr(script, "last_run_at", None)
    if last_run:
        try:
            age = (datetime.now() - last_run).total_seconds()
            if 0 <= age <= 7 * 86400:
                boost += 2.0
        except (TypeError, ValueError):
            pass
    return boost


def _input_preview(text, limit=80):
    value = re.sub(r"\s+", " ", str(text or "")).strip()
    if len(value) <= limit:
        return value
    return value[:limit - 1] + "…"


def _preferred_tool_title(title: str, dedupe_key: str, tool_titles: dict) -> str:
    if not dedupe_key or has_cjk(title):
        return ""
    tool_title = tool_titles.get(dedupe_key, "")
    return tool_title if has_cjk(tool_title) else ""


class IndexWorker(QThread):
    loaded = Signal(list, list, bool)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._cancelled = threading.Event()
        self._process = None
        self._process_lock = threading.Lock()

    def _set_process(self, process):
        with self._process_lock:
            self._process = process

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

    def run(self):
        start_menu = scan_start_menu()
        if self._cancelled.is_set():
            return
        uwp, ok = scan_uwp(self._set_process, self._cancelled)
        if self._cancelled.is_set():
            return
        self.loaded.emit(start_menu, uwp, ok)


class PinyinWarmWorker(QThread):
    """在后台为中文标题/别名生成拼音 blob，避免首次输入卡 UI。"""

    updated = Signal()

    def __init__(self, items, parent=None):
        super().__init__(parent)
        self._items = list(items)

    def run(self):
        index = PinyinSearchIndex()
        for item in self._items:
            if item.pinyin_blob:
                continue
            fields = [item.title] + list(item.keywords or [])
            if not any(has_cjk(field) for field in fields):
                continue
            parts = []
            for field in fields:
                try:
                    parts.append(index.blob(field))
                except Exception:
                    continue
            item.pinyin_blob = "\n".join(part for part in parts if part)
        self.updated.emit()


class LauncherService(QObject):
    index_started = Signal()
    index_finished = Signal()
    index_updated = Signal()
    search_keys_updated = Signal()
    index_error = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._start_menu: List[dict] = []
        self._uwp: List[dict] = []
        self._system = system_items()
        self._script_items: List[SearchItem] = []
        self._app_items: List[SearchItem] = []
        self._input_index = InputMatchIndex()
        self._worker: Optional[IndexWorker] = None
        self._warm_worker: Optional[PinyinWarmWorker] = None
        self._pending_refresh = False
        self._pending_warm = False
        self._indexing = False
        self._closing = False

        self._start_menu, self._uwp = load_cache()
        for item in self._system:
            self._prepare_item(item)
        self._rebuild_apps()

        self._watcher = QFileSystemWatcher(self)
        self._watch_start_menu()
        self._watcher.directoryChanged.connect(self._on_watch_changed)

        self._refresh_timer = QTimer(self)
        self._refresh_timer.setSingleShot(True)
        self._refresh_timer.timeout.connect(self.refresh)

        self._uwp_refresh_timer = QTimer(self)
        self._uwp_refresh_timer.setInterval(30 * 60 * 1000)
        self._uwp_refresh_timer.timeout.connect(self.refresh)

    @property
    def indexing(self) -> bool:
        return self._indexing

    def warmable_items(self):
        return [item for item in self._system + self._app_items
                if item.icon_path]

    @staticmethod
    def _prepare_item(item: SearchItem):
        item.description = (item.description or "")[:300]
        item.aux_text = (item.aux_text or "")[:300]
        item.norm_title = normalize(item.title)
        item.compact_title = compact(item.title)
        item.norm_keywords = [normalize(value) for value in item.keywords or []]
        item.compact_keywords = [compact(value) for value in item.keywords or []]
        item.norm_description = normalize(item.description)
        item.compact_description = compact(item.description)
        item.norm_aux = normalize(item.aux_text)
        item.compact_aux = compact(item.aux_text)

    @staticmethod
    def _warm_pinyin_now(items):
        index = PinyinSearchIndex()
        for item in items:
            if item.pinyin_blob:
                continue
            fields = [item.title] + list(item.keywords or [])
            if not any(has_cjk(field) for field in fields):
                continue
            parts = []
            for field in fields:
                try:
                    parts.append(index.blob(field))
                except Exception:
                    continue
            item.pinyin_blob = "\n".join(part for part in parts if part)

    def _start_pinyin_warm(self):
        if self._closing:
            return
        if self._warm_worker is not None:
            self._pending_warm = True
            return
        items = self._script_items + self._system + self._app_items
        if not items:
            return
        worker = PinyinWarmWorker(items, self)
        worker.updated.connect(self._on_warm_updated)
        worker.finished.connect(self._on_warm_finished)
        worker.finished.connect(worker.deleteLater)
        self._warm_worker = worker
        worker.start()

    def _on_warm_updated(self):
        self.search_keys_updated.emit()

    def _on_warm_finished(self):
        self._warm_worker = None
        if self._pending_warm:
            self._pending_warm = False
            self._start_pinyin_warm()

    def start(self):
        self._uwp_refresh_timer.start()
        self.refresh()

    def refresh(self):
        if self._closing:
            return
        if self._worker is not None:
            self._pending_refresh = True
            return
        self._indexing = True
        self.index_started.emit()
        worker = IndexWorker(self)
        worker.loaded.connect(self._on_index_loaded)
        worker.finished.connect(self._on_worker_finished)
        worker.finished.connect(worker.deleteLater)
        self._worker = worker
        worker.start()

    def _on_index_loaded(self, start_menu, uwp, uwp_ok):
        self._start_menu = start_menu
        if uwp_ok:
            self._uwp = uwp
        self._rebuild_apps()
        self._watch_start_menu()
        save_cache(self._start_menu, self._uwp)
        if not uwp_ok:
            self.index_error.emit("应用索引更新失败，使用缓存")
        else:
            self.index_error.emit("")
        self.index_updated.emit()

    def _on_worker_finished(self):
        self._worker = None
        self._indexing = False
        self.index_finished.emit()
        if self._pending_refresh:
            self._pending_refresh = False
            self.refresh()

    def _watch_start_menu(self):
        paths = []
        for root in start_menu_dirs():
            paths.append(str(root))
            try:
                paths.extend(str(path) for path in root.rglob("*")
                             if path.is_dir())
            except OSError:
                pass
        if paths:
            self._watcher.addPaths(paths)

    def _on_watch_changed(self, _path):
        self._refresh_timer.start(1500)

    def refresh_scripts(self, scripts):
        items = []
        ordered = sorted(
            scripts or [],
            key=lambda script: (
                0 if script.pin else 1,
                -(script.last_run_at.timestamp()
                  if getattr(script, 'last_run_at', None) else 0),
                -int(getattr(script, 'run_count', 0) or 0),
                (script.name or '').lower(),
            ),
        )
        for script in ordered:
            icon_path = script.icon or BmTools.get_language_icon_path(
                script.language)
            item = SearchItem(
                id="script:%s" % script.id,
                kind="script",
                title=script.name,
                subtitle="脚本",
                provider="scripts",
                payload=script.id,
                icon_path=icon_path,
                keywords=[script.name],
                description=script.desc or "",
                aux_text=_script_aux_text(script),
                usage_boost=_script_usage_boost(script),
                pin=bool(script.pin),
                tooltip=script.desc or script.name,
                badge=script.badge or "",
            )
            self._prepare_item(item)
            items.append(item)
        self._script_items = items
        self._input_index.rebuild(ordered)
        self._warm_pinyin_now(items[:120])
        self._start_pinyin_warm()

    def script_suggestions(self, limit=None):
        if limit is None:
            return list(self._script_items)
        return list(self._script_items[:limit])

    def input_suggestions(self, query, include_low=True, limit=8):
        if self._closing:
            return []
        matches = self._input_index.match(
            query, include_low=include_low, limit=limit)
        results = []
        for match in matches:
            script = match.script
            schema = match.input_schema or {}
            input_name = str(schema.get("name") or "input")
            input_label = str(schema.get("label") or input_name or "输入")
            icon_path = script.icon or BmTools.get_language_icon_path(
                script.language)
            preview = _input_preview(match.value)
            result = SearchItem(
                id="script_input:%s:%s" % (script.id, input_name),
                kind="script_input",
                title=script.name,
                subtitle="%s：%s" % (input_label, preview),
                provider="scripts",
                payload={
                    "type": "script_input",
                    "script_id": str(script.id),
                    "value": match.value,
                    "matched_kind": match.kind,
                    "confidence": match.confidence,
                },
                icon_path=icon_path,
                keywords=[script.name],
                pin=bool(script.pin),
                tooltip="%s · %s\n%s" % (
                    script.name, input_label, match.value),
                badge=script.badge or "",
            )
            results.append(result)
        return results

    def _rebuild_apps(self):
        items = []
        tool_icons = {
            item.dedupe_key: item.icon_path
            for item in self._system
            if item.dedupe_key and item.icon_path
        }
        tool_titles = {
            item.dedupe_key: item.title
            for item in self._system
            if item.dedupe_key and item.title
        }
        for entry in self._start_menu:
            name = str(entry.get("name") or "").strip()
            path = str(entry.get("path") or "").strip()
            if not name or not path:
                continue
            dedupe_key = app_dedupe_key(name)
            keywords = list(dict.fromkeys(
                [name, Path(path).stem] + aliases_for_key(dedupe_key)))
            item = SearchItem(
                id="app:%s" % path,
                kind="app",
                title=name,
                subtitle="应用",
                provider="start_menu",
                payload={"type": "path", "path": path},
                icon_path=path,
                keywords=keywords,
                tooltip=path,
                dedupe_key=dedupe_key,
                display_title=_preferred_tool_title(
                    name, dedupe_key, tool_titles),
            )
            self._prepare_item(item)
            items.append(item)
        for entry in self._uwp:
            name = str(entry.get("name") or "").strip()
            app_id = str(entry.get("appid") or "").strip()
            if not name or not app_id:
                continue
            dedupe_key = app_dedupe_key(name, app_id)
            keywords = list(dict.fromkeys(
                [name] + aliases_for_key(dedupe_key)))
            icon_path = tool_icons.get(dedupe_key, "")
            item = SearchItem(
                id="uwp:%s" % app_id,
                kind="uwp",
                title=name,
                subtitle="应用",
                provider="uwp",
                payload={"type": "uwp", "appid": app_id},
                icon_path=icon_path,
                icon_name=IconName.APPLICATION,
                keywords=keywords,
                tooltip=app_id,
                dedupe_key=dedupe_key,
                display_title=_preferred_tool_title(
                    name, dedupe_key, tool_titles),
            )
            self._prepare_item(item)
            items.append(item)
        self._app_items = items
        self._start_pinyin_warm()

    def search(self, query: str) -> List[SearchItem]:
        query = (query or "").strip()
        if not query:
            return []

        q = normalize(query)
        q_compact = compact(query)
        q_terms = normalize_terms(query) if len(q) >= 2 else []
        candidates = []

        for index, item in enumerate(
                self._script_items + self._app_items + self._system):
            score = self._score(item, q, q_compact, q_terms)
            if score <= 0:
                continue
            weight = _PROVIDER_WEIGHT.get(item.provider, 0.9)
            priority = _PROVIDER_PRIORITY.get(item.provider, 0)
            candidates.append((score * weight, priority, index, item))

        candidates.sort(key=lambda row: (-row[0], -row[1], row[2]))

        grouped = {}
        others = []
        for row in candidates:
            item = row[3]
            key = item.dedupe_key if item.kind in (
                "app", "uwp", "tool", "setting") else ""
            if key:
                grouped.setdefault(key, []).append(row)
            else:
                others.append(row)

        selected = []
        for rows in grouped.values():
            apps = [row for row in rows if row[3].kind in ("app", "uwp")]
            pool = apps or rows
            selected.append(max(pool, key=lambda row: (row[0], row[1], -row[2])))
        selected.extend(others)
        selected.sort(key=lambda row: (-row[0], -row[1], row[2]))

        results = []
        seen_apps = set()
        for _, _, _, item in selected:
            if item.kind in ("app", "uwp"):
                key = item.norm_title
                if key in seen_apps:
                    continue
                seen_apps.add(key)
            results.append(item)
            if len(results) >= 60:
                break
        return results

    @staticmethod
    def _term_in_item(item: SearchItem, term: str) -> bool:
        fields = [(item.norm_title, item.compact_title)]
        fields.extend(zip(item.norm_keywords, item.compact_keywords))
        fields.append((item.norm_description, item.compact_description))
        fields.append((item.norm_aux, item.compact_aux))
        for value, compact_value in fields:
            if term in value or term in compact_value:
                return True
        return bool(item.pinyin_blob and term in item.pinyin_blob)

    @classmethod
    def _score(cls, item: SearchItem, q: str, q_compact: str,
               q_terms: List[str]) -> float:
        best = 0.0
        fields = [(item.norm_title, item.compact_title, item.pinyin_blob)]
        fields.extend(
            (value, compact_value, "")
            for value, compact_value in zip(item.norm_keywords,
                                            item.compact_keywords)
        )
        for value, compact_value, blob in fields:
            best = max(best, field_score(value, compact_value, q, q_compact,
                                         blob))

        best = max(
            best,
            field_score(item.norm_description, item.compact_description,
                        q, q_compact) * 0.6,
            field_score(item.norm_aux, item.compact_aux, q, q_compact) * 0.4,
        )

        best = max(
            best,
            term_coverage(q_terms,
                          lambda term: cls._term_in_item(item, term),
                          all_bonus=5.0),
        )

        if best <= 0:
            return 0.0
        if item.pin:
            best += 2.0
        best += item.usage_boost
        return best

    def launch(self, item: SearchItem):
        try:
            payload = item.payload
            if item.kind == "uwp":
                subprocess.Popen(
                    ["explorer.exe", "shell:AppsFolder\\" + payload["appid"]],
                    creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
                )
            elif item.kind == "setting":
                os.startfile(payload["uri"])
            elif item.kind in ("app", "tool"):
                os.startfile(payload["path"])
            else:
                return "未知的结果类型: %s" % item.kind
            return None
        except OSError as exc:
            BM_LOG.error("启动命令面板结果失败 %s: %s" % (item.id, exc))
            return str(exc)

    def shutdown(self):
        self._closing = True
        self._refresh_timer.stop()
        self._uwp_refresh_timer.stop()
        try:
            self._watcher.directoryChanged.disconnect(self._on_watch_changed)
        except (RuntimeError, TypeError):
            pass
        worker = self._worker
        if worker is not None:
            worker.cancel()
            if not worker.wait(3000):
                worker.terminate()
                worker.wait(1000)
        warm_worker = self._warm_worker
        if warm_worker is not None:
            if not warm_worker.wait(3000):
                warm_worker.terminate()
                warm_worker.wait(1000)
        self._worker = None
        self._warm_worker = None
