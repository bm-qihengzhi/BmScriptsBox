"""
Copyright (c) 2026 綦恒智
Email: bmscriptsbox@163.com
SPDX-License-Identifier: MIT
SPDX-License-Identifier: LicenseRef-Commons-Clause

脚本输入匹配索引、规则执行、评分与排序。
"""
import fnmatch
import re
from dataclasses import dataclass
from functools import lru_cache
from typing import Any

from app.data.input_match_spec import MAX_REGEX_INPUT
from app.data.toml_schemas import InputMatch
from app.utils import BM_LOG

from .input_context import InputContext, build_context


@dataclass
class InputMatchResult:
    script: Any
    input_schema: dict
    rule: InputMatch
    rule_index: int
    order: int
    kind: str
    value: str
    score: int
    confidence: str
    reasons: tuple


@dataclass
class _CompiledRule:
    script: Any
    input_schema: dict
    rule: InputMatch
    rule_index: int
    order: int
    high: bool


@lru_cache(maxsize=256)
def _compile_regex(pattern, ignore_case=False):
    return re.compile(pattern, re.IGNORECASE if ignore_case else 0)


def _text_value(value):
    return "" if value is None else str(value)


def _eq(left, right, ignore_case=False):
    if left is None:
        return False
    if isinstance(left, bool) or isinstance(right, bool):
        return left == right
    left = _text_value(left)
    right = _text_value(right)
    if ignore_case:
        return left.casefold() == right.casefold()
    return left == right


def _contains(left, right, ignore_case=False):
    if left is None or right is None:
        return False
    left = _text_value(left)
    right = _text_value(right)
    if ignore_case:
        return right.casefold() in left.casefold()
    return right in left


def _prefix(left, right, ignore_case=False):
    if left is None or right is None:
        return False
    left = _text_value(left)
    right = _text_value(right)
    if ignore_case:
        return left.casefold().startswith(right.casefold())
    return left.startswith(right)


def _suffix(left, right, ignore_case=False):
    if left is None or right is None:
        return False
    left = _text_value(left)
    right = _text_value(right)
    if ignore_case:
        return left.casefold().endswith(right.casefold())
    return left.endswith(right)


def _glob(left, right, ignore_case=False):
    if left is None or right is None:
        return False
    left = _text_value(left)
    right = _text_value(right)
    if ignore_case:
        return fnmatch.fnmatchcase(left.casefold(), right.casefold())
    return fnmatch.fnmatchcase(left, right)


def _host_suffix(host, suffix, ignore_case=False):
    if not host or not suffix:
        return False
    host = _text_value(host).lower()
    suffix = _text_value(suffix).lower().lstrip("*.")
    return host == suffix or host.endswith("." + suffix)


def _domain_match(host, pattern):
    if not host or not pattern:
        return False
    return _host_suffix(host, pattern)


def _ext_match(ext, expected):
    expected = _text_value(expected).lower()
    if expected and not expected.startswith("."):
        expected = "." + expected
    return ext == expected


def _as_list(value):
    if isinstance(value, (list, tuple, set)):
        return list(value)
    return [value]


def _predicate_high(pred):
    if pred.field == "kind" and pred.op == "eq" and pred.value == "magnet":
        return True
    if pred.field in ("url.host", "url.path", "url.ext"):
        return True
    if pred.field in ("path.full", "path.name", "path.ext",
                     "path.exists", "path.is_file", "path.is_folder"):
        return True
    if pred.field == "formats":
        return True
    if pred.field == "text" and pred.op in (
            "prefix", "suffix", "equals", "contains", "regex"):
        return True
    return False


def _rule_high(rule):
    if rule.kind == "magnet":
        return True
    if rule.all or rule.none:
        return any(_predicate_high(pred) for pred in rule.all)
    if rule.kind == "url":
        return any((
            rule.domain, rule.host, rule.path, rule.ext,
        ))
    if rule.kind == "path":
        return bool(rule.path or rule.name or rule.ext
                    or rule.exists is not None
                    or rule.is_file is not None
                    or rule.is_folder is not None)
    if rule.kind == "text":
        return bool(
            rule.format or rule.prefix or rule.suffix or rule.contains
            or rule.equals or rule.regex)
    return False


class InputMatchIndex:
    def __init__(self):
        self._rules = {kind: [] for kind in ("url", "path", "text", "magnet")}
        self._required_formats = set()

    @property
    def required_formats(self):
        return set(self._required_formats)

    def rebuild(self, scripts):
        self._rules = {kind: [] for kind in ("url", "path", "text", "magnet")}
        self._required_formats = set()
        for order, script in enumerate(scripts or []):
            triggers = getattr(script, "triggers_schema", None) or {}
            search = triggers.get("search") if isinstance(triggers, dict) else None
            if not isinstance(search, dict) or not search.get("enabled", True):
                continue
            raw_rules = search.get("match") or []
            if not raw_rules:
                continue

            inputs = getattr(script, "inputs_schema", None) or []
            input_schema = inputs[0] if inputs else None
            if input_schema is None:
                BM_LOG.warning(
                    "脚本 %s 声明了 triggers.search 但没有 inputs"
                    % getattr(script, "id", "?"))
                continue

            for rule_index, raw in enumerate(raw_rules):
                try:
                    rule = InputMatch.model_validate(raw)
                except Exception as exc:
                    BM_LOG.warning(
                        "脚本 %s 输入匹配规则 %s 无效: %s"
                        % (getattr(script, "id", "?"), rule_index, exc))
                    continue
                compiled = _CompiledRule(
                    script=script,
                    input_schema=input_schema,
                    rule=rule,
                    rule_index=rule_index,
                    order=order,
                    high=_rule_high(rule),
                )
                self._rules[rule.kind].append(compiled)
                self._required_formats.update(rule.format)
                for pred in rule.all + rule.none:
                    if pred.field == "formats":
                        self._required_formats.update(
                            str(v) for v in _as_list(pred.value) if v)

    def match(self, query, include_low=True, limit=8):
        context = build_context(query)
        if not context.trimmed:
            return []
        if context.kind == "text" and self._required_formats:
            context.ensure_formats(self._required_formats)

        best_by_script = {}
        for compiled in self._rules.get(context.kind, []):
            matched, score, reasons = self._evaluate(compiled, context)
            if not matched:
                continue
            confidence = "high" if compiled.high else "low"
            if not include_low and confidence != "high":
                continue
            result = InputMatchResult(
                script=compiled.script,
                input_schema=compiled.input_schema,
                rule=compiled.rule,
                rule_index=compiled.rule_index,
                order=compiled.order,
                kind=context.kind,
                value=context.trimmed,
                score=score,
                confidence=confidence,
                reasons=tuple(reasons),
            )
            script_id = str(getattr(compiled.script, "id", compiled.order))
            current = best_by_script.get(script_id)
            if current is None or result.score > current.score:
                best_by_script[script_id] = result

        results = list(best_by_script.values())
        results.sort(key=self._sort_key)
        return results[:limit]

    @staticmethod
    def _sort_key(result):
        script = result.script
        last_run = getattr(script, "last_run_at", None)
        last_ts = last_run.timestamp() if last_run else 0
        return (
            -result.score,
            -int(result.rule.weight or 0),
            0 if getattr(script, "pin", False) else 1,
            -last_ts,
            -int(getattr(script, "run_count", 0) or 0),
            str(getattr(script, "name", "")).lower(),
            result.order,
        )

    def _evaluate(self, compiled, context):
        rule = compiled.rule
        if rule.all or rule.none:
            return self._evaluate_advanced(compiled, context)
        return self._evaluate_simple(compiled, context)

    def _evaluate_simple(self, compiled, context):
        rule = compiled.rule
        score = 10
        reasons = ["kind=%s" % context.kind]
        ignore = rule.ignore_case

        if rule.kind == "url":
            url = context.url
            if url is None:
                return False, 0, []
            if rule.scheme and url.scheme not in [
                    value.lower() for value in rule.scheme]:
                return False, 0, []
            if rule.scheme:
                score += 5
                reasons.append("scheme=%s" % url.scheme)
            if rule.domain and not any(
                    _domain_match(url.host, value) for value in rule.domain):
                return False, 0, []
            if rule.domain:
                score += 50
                reasons.append("domain=%s" % ",".join(rule.domain))
            if rule.host and not any(
                    _eq(url.host, value) for value in rule.host):
                return False, 0, []
            if rule.host:
                score += 55
                reasons.append("host=%s" % ",".join(rule.host))
            if rule.path and not _glob(url.path, rule.path, ignore):
                return False, 0, []
            if rule.path:
                score += 40
                reasons.append("path=%s" % rule.path)
            if rule.query_contains and not _contains(
                    url.query, rule.query_contains, ignore):
                return False, 0, []
            if rule.query_contains:
                score += 10
                reasons.append("query_contains=%s" % rule.query_contains)
            if rule.ext and not any(
                    _ext_match(url.ext, value) for value in rule.ext):
                return False, 0, []
            if rule.ext:
                score += 30
                reasons.append("ext=%s" % ",".join(rule.ext))

        elif rule.kind == "path":
            path = context.path
            if path is None:
                return False, 0, []
            if rule.path and not _glob(path.full, rule.path, ignore):
                return False, 0, []
            if rule.path:
                score += 40
                reasons.append("path=%s" % rule.path)
            if rule.name and not _glob(path.name, rule.name, ignore):
                return False, 0, []
            if rule.name:
                score += 35
                reasons.append("name=%s" % rule.name)
            if rule.ext and not any(
                    _ext_match(path.ext, value) for value in rule.ext):
                return False, 0, []
            if rule.ext:
                score += 30
                reasons.append("ext=%s" % ",".join(rule.ext))
            if rule.exists is not None and path.exists != rule.exists:
                return False, 0, []
            if rule.exists is not None:
                score += 10
                reasons.append("exists=%s" % rule.exists)
            if rule.is_file is not None and path.is_file != rule.is_file:
                return False, 0, []
            if rule.is_file is not None:
                score += 10
                reasons.append("is_file=%s" % rule.is_file)
            if rule.is_folder is not None and path.is_folder != rule.is_folder:
                return False, 0, []
            if rule.is_folder is not None:
                score += 10
                reasons.append("is_folder=%s" % rule.is_folder)

        elif rule.kind == "text":
            if rule.format and not any(
                    value in context.formats for value in rule.format):
                return False, 0, []
            if rule.format:
                score += 45
                reasons.append("format=%s" % ",".join(rule.format))
            if rule.prefix and not _prefix(
                    context.trimmed, rule.prefix, ignore):
                return False, 0, []
            if rule.prefix:
                score += 30
                reasons.append("prefix=%s" % rule.prefix)
            if rule.suffix and not _suffix(
                    context.trimmed, rule.suffix, ignore):
                return False, 0, []
            if rule.suffix:
                score += 20
                reasons.append("suffix=%s" % rule.suffix)
            if rule.contains and not _contains(
                    context.trimmed, rule.contains, ignore):
                return False, 0, []
            if rule.contains:
                score += 20
                reasons.append("contains=%s" % rule.contains)
            if rule.equals and not _eq(
                    context.trimmed, rule.equals, ignore):
                return False, 0, []
            if rule.equals:
                score += 40
                reasons.append("equals")
            if rule.min_length is not None and context.length < rule.min_length:
                return False, 0, []
            if rule.min_length is not None:
                score += 5
                reasons.append("min_length=%s" % rule.min_length)
            if rule.max_length is not None and context.length > rule.max_length:
                return False, 0, []
            if rule.max_length is not None:
                score += 5
                reasons.append("max_length=%s" % rule.max_length)
            if rule.regex:
                if len(context.trimmed) > MAX_REGEX_INPUT:
                    return False, 0, []
                if not _compile_regex(rule.regex, ignore).search(
                        context.trimmed):
                    return False, 0, []
            if rule.regex:
                score += 35
                reasons.append("regex")
        elif rule.kind != "magnet":
            return False, 0, []

        return True, score, reasons

    def _evaluate_advanced(self, compiled, context):
        rule = compiled.rule
        reasons = []
        for pred in rule.all:
            if not self._predicate(pred, context, rule.ignore_case):
                return False, 0, []
            reasons.append("%s %s %s" % (pred.field, pred.op, pred.value))
        for pred in rule.none:
            if self._predicate(pred, context, rule.ignore_case):
                return False, 0, []

        score = 10 + 8 * len(rule.all)
        if any(_predicate_high(pred) for pred in rule.all):
            score += 20
        return True, score, reasons or ["kind=%s" % context.kind]

    def _predicate(self, pred, context, ignore_case):
        actual = self._field_value(pred.field, context)
        if actual is None:
            return False
        if pred.op == "eq":
            return _eq(actual, pred.value, ignore_case)
        if pred.op == "ne":
            return not _eq(actual, pred.value, ignore_case)
        if pred.op == "in":
            return any(_eq(actual, value, ignore_case)
                       for value in _as_list(pred.value))
        if pred.op == "not_in":
            return all(not _eq(actual, value, ignore_case)
                       for value in _as_list(pred.value))
        if pred.op == "prefix":
            return _prefix(actual, pred.value, ignore_case)
        if pred.op == "suffix":
            return _suffix(actual, pred.value, ignore_case)
        if pred.op == "contains":
            if isinstance(actual, (list, tuple, set)):
                return any(_eq(item, pred.value, ignore_case) for item in actual)
            return _contains(actual, pred.value, ignore_case)
        if pred.op == "not_contains":
            if isinstance(actual, (list, tuple, set)):
                return all(not _eq(item, pred.value, ignore_case)
                           for item in actual)
            return not _contains(actual, pred.value, ignore_case)
        if pred.op == "glob":
            return _glob(actual, pred.value, ignore_case)
        if pred.op == "host_suffix":
            return _host_suffix(actual, pred.value, ignore_case)
        if pred.op == "gte":
            compared = self._compare_number(actual, pred.value)
            return compared is not None and compared >= 0
        if pred.op == "lte":
            compared = self._compare_number(actual, pred.value)
            return compared is not None and compared <= 0
        if pred.op == "regex":
            text = _text_value(actual)
            if len(text) > MAX_REGEX_INPUT:
                return False
            return bool(_compile_regex(
                str(pred.value), ignore_case).search(text))
        return False

    @staticmethod
    def _compare_number(actual, expected):
        try:
            left = float(actual)
            right = float(expected)
        except (TypeError, ValueError):
            return None
        return (left > right) - (left < right)

    @staticmethod
    def _field_value(field, context):
        if field == "kind":
            return context.kind
        if field == "raw":
            return context.raw or context.trimmed
        if field == "length":
            return context.length
        if field == "formats":
            return context.formats
        if field == "text":
            return context.trimmed if context.kind == "text" else None
        url = context.url
        if field.startswith("url."):
            if url is None:
                return None
            return {
                "url.scheme": url.scheme,
                "url.host": url.host,
                "url.path": url.path,
                "url.query": url.query,
                "url.ext": url.ext,
            }.get(field)
        path = context.path
        if field.startswith("path."):
            if path is None:
                return None
            return {
                "path.full": path.full,
                "path.name": path.name,
                "path.ext": path.ext,
                "path.exists": path.exists,
                "path.is_file": path.is_file,
                "path.is_folder": path.is_folder,
            }.get(field)
        return None
