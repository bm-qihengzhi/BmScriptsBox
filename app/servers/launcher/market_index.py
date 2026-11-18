"""
Copyright (c) 2026 綦恒智
Email: bmscriptsbox@163.com
SPDX-License-Identifier: MIT
SPDX-License-Identifier: LicenseRef-Commons-Clause

脚本市场本地索引：名称 / 标签 / 分类 / 描述匹配，已装过滤与排序。
"""
import math
from dataclasses import dataclass
from datetime import datetime
from typing import Iterable, List, Optional, Tuple

from app.utils.pinyin_search import PinyinSearchIndex, normalize

from .text_score import compact, field_score, normalize_terms, term_coverage

_W_NAME = 1.0
_W_ID = 0.9
_W_TAGS = 0.8
_W_CLASSIFY = 0.55
_W_DESC = 0.5


def _parse_ts(value) -> float:
    if not value:
        return 0.0
    try:
        return datetime.fromisoformat(
            str(value).replace("Z", "+00:00")).timestamp()
    except (TypeError, ValueError):
        return 0.0


def _int(value) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


@dataclass(frozen=True)
class MarketHit:
    item: dict
    score: float = 0.0
    downloads: int = 0
    likes: int = 0
    created_ts: float = 0.0
    updated_ts: float = 0.0
    sort_name: str = ""


@dataclass
class _Entry:
    item: dict
    script_id: str
    script_norm: str
    script_compact: str
    name: str
    name_compact: str
    name_blob: str
    tags: str
    tags_compact: str
    tags_blob: str
    classify: str
    classify_compact: str
    classify_blob: str
    desc: str
    desc_compact: str
    language: str
    classify_key: Optional[str]
    downloads: int
    likes: int
    created_ts: float
    updated_ts: float
    sort_name: str


class MarketCatalogIndex:
    """把市场快照构建成可快速过滤/打分的本地索引。"""

    def __init__(self, items: Optional[Iterable[dict]] = None,
                 classifies: Optional[Iterable[dict]] = None):
        self._entries: List[_Entry] = []
        self._by_id = {}
        self._classifies: List[dict] = []
        self._pinyin = PinyinSearchIndex()
        if items is not None:
            self.rebuild(items, classifies)

    # ---------- 构建 ----------

    def rebuild(self, items: Optional[Iterable[dict]],
                classifies: Optional[Iterable[dict]] = None):
        self._classifies = [dict(c) for c in (classifies or [])
                            if isinstance(c, dict)]
        classify_map = {
            str(c.get("id")): str(c.get("name") or "")
            for c in self._classifies if c.get("id") is not None
        }
        self._entries = []
        self._by_id = {}
        for item in items or []:
            entry = self._build_entry(item, classify_map)
            if entry is None:
                continue
            self._entries.append(entry)
            self._by_id[entry.script_id] = entry

    def _build_entry(self, item: dict, classify_map: dict) -> Optional[_Entry]:
        if not isinstance(item, dict):
            return None
        script_id = str(item.get("script_id") or "")
        if not script_id:
            return None
        name = str(item.get("name") or "")
        tags_list = item.get("tags") if isinstance(item.get("tags"), list) else []
        tags = " ".join(str(t) for t in tags_list if t)
        classify_id = item.get("classify_id")
        classify = ""
        classify_key = None
        if classify_id is not None:
            classify_key = str(classify_id)
            classify = classify_map.get(classify_key, "")
        desc = str(item.get("description") or "")
        updated_raw = item.get("content_updated_at") or item.get("updated_at")
        return _Entry(
            item=item,
            script_id=script_id,
            script_norm=normalize(script_id),
            script_compact=compact(script_id),
            name=normalize(name),
            name_compact=compact(name),
            name_blob=self._pinyin.blob(name),
            tags=normalize(tags),
            tags_compact=compact(tags),
            tags_blob=self._pinyin.blob(tags),
            classify=normalize(classify),
            classify_compact=compact(classify),
            classify_blob=self._pinyin.blob(classify),
            desc=normalize(desc),
            desc_compact=compact(desc),
            language=str(item.get("language") or "").lower(),
            classify_key=classify_key,
            downloads=_int(item.get("downloads_count")),
            likes=_int(item.get("likes_count")),
            created_ts=_parse_ts(item.get("created_at")),
            updated_ts=_parse_ts(updated_raw),
            sort_name=normalize(name),
        )

    # ---------- 只读 ----------

    def __len__(self) -> int:
        return len(self._entries)

    @property
    def is_ready(self) -> bool:
        return bool(self._entries)

    @property
    def classifies(self) -> List[dict]:
        return [dict(c) for c in self._classifies]

    def get(self, script_id: str) -> Optional[dict]:
        entry = self._by_id.get(str(script_id))
        return entry.item if entry is not None else None

    # ---------- 查询 ----------

    def search(
        self,
        query: str = "",
        *,
        installed_ids: Optional[Iterable[str]] = None,
        limit: Optional[int] = 5,
        classify_id=None,
        language: Optional[str] = None,
        sort: str = "relevance",
    ) -> List[MarketHit]:
        q_norm = normalize(query)
        q_compact = compact(query)
        q_terms = normalize_terms(query)
        installed = {str(x) for x in (installed_ids or ())}
        language_key = str(language or "").strip().lower()
        uncategorized = classify_id is not None and str(classify_id) == "-1"
        classify_key = None if classify_id is None else str(classify_id)

        hits: List[MarketHit] = []
        for entry in self._entries:
            if entry.script_id in installed:
                continue
            if language_key and entry.language != language_key:
                continue
            if uncategorized:
                if entry.classify_key is not None:
                    continue
            elif classify_key is not None and entry.classify_key != classify_key:
                continue

            score = 0.0
            if q_norm:
                score = self._score(entry, q_norm, q_compact, q_terms)
                if score <= 0:
                    continue
            hits.append(MarketHit(
                item=entry.item,
                score=score,
                downloads=entry.downloads,
                likes=entry.likes,
                created_ts=entry.created_ts,
                updated_ts=entry.updated_ts,
                sort_name=entry.sort_name,
            ))

        hits.sort(key=lambda hit: _sort_key(hit, sort))
        if limit is not None:
            return hits[:max(0, int(limit))]
        return hits

    def browse(
        self,
        *,
        search: str = "",
        classify_id=None,
        language: Optional[str] = None,
        sort: str = "downloads",
        page: int = 1,
        page_size: int = 50,
    ) -> Tuple[List[dict], int]:
        hits = self.search(
            search,
            limit=None,
            classify_id=classify_id,
            language=language,
            sort=sort,
        )
        total = len(hits)
        size = max(1, int(page_size))
        start = max(0, (max(1, int(page)) - 1) * size)
        return [hit.item for hit in hits[start:start + size]], total

    # ---------- 打分 ----------

    def _score(self, entry: _Entry, q_norm: str, q_compact: str,
               q_terms: List[str]) -> float:
        script_id = 0.0
        if len(q_norm) >= 2:
            script_id = field_score(entry.script_norm, entry.script_compact,
                                    q_norm, q_compact) * _W_ID
        name = field_score(entry.name, entry.name_compact, q_norm, q_compact,
                           entry.name_blob) * _W_NAME
        tags = field_score(entry.tags, entry.tags_compact, q_norm, q_compact,
                           entry.tags_blob) * _W_TAGS
        classify = field_score(entry.classify, entry.classify_compact, q_norm,
                               q_compact, entry.classify_blob) * _W_CLASSIFY
        desc = field_score(entry.desc, entry.desc_compact, q_norm,
                           q_compact) * _W_DESC

        score = max(
            script_id, name, tags, classify, desc,
            term_coverage(q_terms, lambda term: self._term_in(term, entry),
                          all_bonus=8.0),
        )
        if score <= 0:
            return 0.0
        score += min(math.log10(entry.downloads + 1) / 4.0, 1.0) * 3.0
        return score

    @staticmethod
    def _term_in(term: str, entry: _Entry) -> bool:
        for text, compact, blob in (
            (entry.script_norm, entry.script_compact, ""),
            (entry.name, entry.name_compact, entry.name_blob),
            (entry.tags, entry.tags_compact, entry.tags_blob),
            (entry.classify, entry.classify_compact, entry.classify_blob),
            (entry.desc, entry.desc_compact, ""),
        ):
            if term in text or term in compact:
                return True
            if blob and term in blob:
                return True
        return False


def _sort_key(hit: MarketHit, sort: str):
    sid = str(hit.item.get("script_id") or "")
    if sort == "downloads":
        return (-hit.downloads, -hit.score, hit.sort_name, sid)
    if sort == "likes":
        return (-hit.likes, -hit.downloads, -hit.score, hit.sort_name, sid)
    if sort == "updated":
        return (-hit.updated_ts, -hit.score, -hit.downloads, hit.sort_name, sid)
    if sort == "newest":
        return (-hit.created_ts, -hit.score, -hit.downloads, hit.sort_name, sid)
    return (-hit.score, -hit.downloads, hit.sort_name, sid)
