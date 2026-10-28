"""
Copyright (c) 2026 綦恒智
Email: bmscriptsbox@163.com
SPDX-License-Identifier: MIT
SPDX-License-Identifier: LicenseRef-Commons-Clause

脚本卡片搜索用的拼音索引：支持中文原名、全拼、首字母和拼音子串。
"""
import unicodedata
from typing import Dict

try:
    from pypinyin import lazy_pinyin, pinyin, Style
    HAS_PYPINYIN = True
except Exception:
    lazy_pinyin = pinyin = Style = None
    HAS_PYPINYIN = False


def normalize(text) -> str:
    """统一大小写/全半角并去掉所有空白，便于拼音与原名混排匹配"""
    if not text:
        return ""
    text = unicodedata.normalize("NFKC", str(text)).lower()
    return "".join(text.split())


def _join(items) -> str:
    return "".join(item for item in items if item)


class PinyinSearchIndex:
    """按脚本名缓存搜索文本，避免每次输入重复做拼音转换"""

    def __init__(self, max_cache: int = 4096):
        self._cache: Dict[str, str] = {}
        self._max_cache = max_cache

    def blob(self, name: str) -> str:
        name = str(name or "")
        cached = self._cache.get(name)
        if cached is not None:
            return cached
        blob = self._build_blob(name)
        if len(self._cache) >= self._max_cache:
            self._cache.clear()
        self._cache[name] = blob
        return blob

    def matches(self, name: str, query: str) -> bool:
        query = normalize(query)
        if not query:
            return True
        return query in self.blob(name)

    def clear(self):
        self._cache.clear()

    @staticmethod
    def _build_blob(name: str) -> str:
        parts = [normalize(name)]
        if not name or not HAS_PYPINYIN:
            return parts[0]

        try:
            defaults = lazy_pinyin(name, errors="default")
            full_default = normalize(_join(defaults))
            initials_default = normalize(
                "".join(token[0] for token in defaults if token))

            # 多音字：把每个字的全部读音都放进搜索文本（best-effort）
            heteronyms = pinyin(
                name, style=Style.NORMAL, heteronym=True, errors="default")
            full_all = normalize(_join("".join(group) for group in heteronyms))
            initials_all = normalize(
                "".join("".join(token[0] for token in group if token)
                        for group in heteronyms))

            parts.extend([full_default, initials_default, full_all, initials_all])
        except Exception:
            pass

        # 去重并保持顺序，原名为空时 blobs 也为空
        seen = set()
        result = []
        for part in parts:
            if part and part not in seen:
                seen.add(part)
                result.append(part)
        return "\n".join(result)
