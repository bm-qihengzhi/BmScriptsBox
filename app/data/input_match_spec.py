"""
Copyright (c) 2026 綦恒智
Email: bmscriptsbox@163.com
SPDX-License-Identifier: MIT
SPDX-License-Identifier: LicenseRef-Commons-Clause

脚本输入匹配的公共字段、类型与操作符定义。
"""

MATCH_KINDS = frozenset({"url", "path", "text", "magnet"})
MAX_REGEX_PATTERN = 512
MAX_REGEX_INPUT = 32768

TEXT_FORMATS = frozenset({
    "json", "xml", "csv", "yaml", "base64", "hex", "hash", "btih",
    "email", "ip", "domain", "uuid",
})

URL_MATCH_FIELDS = frozenset({
    "scheme", "domain", "host", "path", "query_contains", "ext",
})
PATH_MATCH_FIELDS = frozenset({
    "path", "name", "ext", "exists", "is_file", "is_folder",
})
TEXT_MATCH_FIELDS = frozenset({
    "format", "prefix", "suffix", "contains", "equals",
    "min_length", "max_length", "regex",
})
SIMPLE_MATCH_FIELDS = frozenset({
    "kind", "weight", "ignore_case", "all", "none",
}) | URL_MATCH_FIELDS | PATH_MATCH_FIELDS | TEXT_MATCH_FIELDS

PREDICATE_FIELDS = frozenset({
    "kind", "raw", "length", "formats",
    "url.scheme", "url.host", "url.path", "url.query", "url.ext",
    "path.full", "path.name", "path.ext", "path.exists",
    "path.is_file", "path.is_folder",
    "text",
})

PREDICATE_OPS = frozenset({
    "eq", "ne", "in", "not_in",
    "prefix", "suffix", "contains", "not_contains",
    "glob", "host_suffix", "gte", "lte", "regex",
})


