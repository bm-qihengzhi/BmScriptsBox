"""
Copyright (c) 2026 綦恒智
Email: bmscriptsbox@163.com
SPDX-License-Identifier: MIT
SPDX-License-Identifier: LicenseRef-Commons-Clause

搜索文本打分公共工具：分词、字段分档与词项覆盖率。

命令面板的本地搜索与脚本市场索引共用这三项基础规则，
字段权重与排序加成仍由各自业务决定，避免规则各自演化后出现
「面板搜不到、市场页能搜到」的不一致。
"""
import re
import unicodedata
from typing import Callable, Iterable, List

from app.utils.pinyin_search import normalize

MATCH_EXACT = 100.0
MATCH_PREFIX = 85.0
MATCH_SUBSTR = 70.0
MATCH_PINYIN = 55.0
MATCH_TERMS = 60.0
TERM_MIN_COVERAGE = 0.6

_CJK_RE = re.compile(r"[\u4e00-\u9fff]")
_RUN_RE = re.compile(r"[\u4e00-\u9fff]+|[0-9a-z]+")
_COMPACT_RE = re.compile(r"[^0-9a-z\u4e00-\u9fff]+")


def compact(text) -> str:
    """去掉空白与标点，只保留中英文数字，便于跨符号匹配。"""
    return _COMPACT_RE.sub("", normalize(text))


def has_cjk(text) -> bool:
    return bool(_CJK_RE.search(str(text or "")))


def normalize_terms(query) -> List[str]:
    """查询拆词：中文按 2 字分块，英文/数字按词，保序去重。"""
    raw = unicodedata.normalize("NFKC", str(query or "")).lower()
    terms: List[str] = []
    for token in _RUN_RE.findall(raw):
        if has_cjk(token) and len(token) > 2:
            for i in range(0, len(token), 2):
                chunk = token[i:i + 2]
                if len(chunk) == 2:
                    terms.append(chunk)
        else:
            terms.append(token)
    seen = set()
    result: List[str] = []
    for term in terms:
        if term and term not in seen:
            seen.add(term)
            result.append(term)
    return result


def field_score(value: str, compact_value: str, query: str,
                query_compact: str, pinyin_blob: str = "") -> float:
    """单字段匹配分档：相等 100 / 前缀 85 / 子串 70 / 拼音 55。"""
    if not value and not compact_value:
        return 0.0
    if query == value or (query_compact and query_compact == compact_value):
        best = MATCH_EXACT
    elif value.startswith(query) or (
            query_compact and compact_value.startswith(query_compact)):
        best = MATCH_PREFIX
    elif query in value or (query_compact and query_compact in compact_value):
        best = MATCH_SUBSTR
    else:
        best = 0.0
    if best < MATCH_PINYIN and pinyin_blob and query:
        if query in pinyin_blob:
            best = MATCH_PINYIN
    return best


def term_coverage(terms: Iterable[str], matcher: Callable[[str], bool],
                  min_ratio: float = TERM_MIN_COVERAGE,
                  all_bonus: float = 0.0) -> float:
    """词项覆盖率分：低于 min_ratio 视为不相关，全中时加 all_bonus。"""
    terms = list(terms or ())
    if not terms:
        return 0.0
    matched = sum(1 for term in terms if matcher(term))
    ratio = matched / len(terms)
    if ratio < min_ratio:
        return 0.0
    score = MATCH_TERMS * ratio
    if all_bonus and matched == len(terms):
        score += all_bonus
    return score
