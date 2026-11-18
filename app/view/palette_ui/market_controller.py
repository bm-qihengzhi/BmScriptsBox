"""
Copyright (c) 2026 綦恒智
Email: bmscriptsbox@163.com
SPDX-License-Identifier: MIT
SPDX-License-Identifier: LicenseRef-Commons-Clause

搜索面板的市场推荐适配：MarketCatalogService → SearchItem。
"""
from typing import Iterable, List, Optional, Tuple

from PySide6.QtCore import QObject

from xsideui import tr

from app.servers.launcher.models import SearchItem
from app.utils import BM_LOG, BmTools


def has_strong_local_result(items) -> bool:
    """本地是否有明确能处理该输入的脚本（直接脚本或高置信输入匹配）。"""
    for item in items or []:
        kind = getattr(item, "kind", "")
        if kind == "script":
            return True
        if kind == "script_input":
            payload = getattr(item, "payload", None)
            if isinstance(payload, dict):
                confidence = str(payload.get("confidence") or "").lower()
                if confidence == "high":
                    return True
    return False


def should_recommend(query: str, items) -> bool:
    """本地没有明确脚本时推荐市场；单字中文也允许（本地索引，无网络成本）。"""
    query = str(query or "").strip()
    if not query or has_strong_local_result(items):
        return False
    if len(query) >= 2:
        return True
    return any(0x4E00 <= ord(ch) <= 0x9FFF for ch in query)


class MarketController(QObject):
    """只读适配层：不发起网络请求，同步由 MarketCatalogService 负责。"""

    def __init__(self, catalog=None, parent=None):
        super().__init__(parent)
        self._catalog = catalog

    @property
    def available(self) -> bool:
        return self._catalog is not None and self._catalog.is_ready

    @property
    def version(self) -> str:
        return self._catalog.version if self._catalog is not None else ""

    def refresh(self):
        """按需触发后台版本检查；索引由快照更新自动失效。"""
        if self._catalog is not None:
            self._catalog.sync_if_stale()

    def recommend(self, query: str,
                  installed_ids: Optional[Iterable[str]] = None,
                  limit: Optional[int] = 5) -> List[SearchItem]:
        if not self.available:
            return []
        query = str(query or "").strip()
        if not query:
            return []
        try:
            hits = self._catalog.index.search(
                query, installed_ids=installed_ids, limit=limit)
        except Exception as exc:
            BM_LOG.error(f"市场推荐查询失败: {exc}")
            return []
        return [self.to_search_item(hit.item) for hit in hits]

    def browse(self, *, search: str = "", classify_id=None,
               language: Optional[str] = None, sort: str = "downloads",
               page: int = 1, page_size: int = 50
               ) -> Tuple[List[dict], int]:
        if not self.available:
            return [], 0
        try:
            return self._catalog.index.browse(
                search=search, classify_id=classify_id, language=language,
                sort=sort, page=page, page_size=page_size)
        except Exception as exc:
            BM_LOG.error(f"市场目录查询失败: {exc}")
            return [], 0

    @staticmethod
    def to_search_item(item: dict) -> SearchItem:
        script_id = str(item.get("script_id") or "")
        name = str(item.get("name") or "")
        desc = str(item.get("description") or "")
        language = str(item.get("language") or "")
        version = str(item.get("version") or "")
        repo = str(item.get("repository_url") or "")
        branch = str(item.get("default_branch") or "master")
        tooltip = f"{name} · v{version} · {language}"
        if desc:
            tooltip += f"\n{desc}"
        return SearchItem(
            id=f"market_script:{script_id}",
            kind="market_script",
            title=name,
            subtitle=desc,
            provider="market",
            payload={
                "type": "market_script",
                "script_id": script_id,
                "repository_url": repo,
                "default_branch": branch,
                "name": name,
                "version": version,
                "language": language,
                "is_node": bool(item.get("is_node")),
            },
            icon_path=(BmTools.get_language_icon_path(language)
                       if language else ""),
            keywords=[name],
            tooltip=tooltip,
            badge=tr("Installable"),
        )
