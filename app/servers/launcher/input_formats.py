"""
Copyright (c) 2026 綦恒智
Email: bmscriptsbox@163.com
SPDX-License-Identifier: MIT
SPDX-License-Identifier: LicenseRef-Commons-Clause

文本格式检测器。只在脚本声明了对应 format 时按需执行。
"""
import base64
import binascii
import csv
import ipaddress
import json
import re
import uuid
from xml.etree import ElementTree

from app.data.input_match_spec import TEXT_FORMATS


_EMAIL_RE = re.compile(
    r"^[A-Za-z0-9.!#$%&'*+/=?^_`{|}~-]+@"
    r"[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?"
    r"(?:\.[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?)+$")
_DOMAIN_RE = re.compile(
    r"^(?=.{1,253}$)(?:[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?\.)+"
    r"[A-Za-z]{2,63}$")
_BASE64_RE = re.compile(r"^[A-Za-z0-9+/]+={0,2}$")
_HEX_RE = re.compile(r"^[0-9a-fA-F]+$")
_BTIH_HEX_RE = re.compile(r"^[0-9a-fA-F]{40}$")
_BTIH_BASE32_RE = re.compile(r"^[A-Z2-7]{32}$")


def _is_json(text):
    if not text or text[0] not in "[{":
        return False
    try:
        value = json.loads(text)
    except (TypeError, ValueError):
        return False
    return isinstance(value, (dict, list))


def _is_xml(text):
    if not text or not text.startswith("<"):
        return False
    try:
        ElementTree.fromstring(text)
    except (ElementTree.ParseError, ValueError):
        return False
    return True


def _is_csv(text):
    lines = [line for line in text.splitlines() if line.strip()]
    if len(lines) < 2:
        return False
    try:
        rows = list(csv.reader(lines[:50]))
    except csv.Error:
        return False
    return len(rows) >= 2 and all(len(row) >= 2 for row in rows[:3])


def _is_yaml(text):
    if not text or not (text.startswith("-") or
                        re.search(r"^[\w.-]+\s*:", text, re.MULTILINE)):
        return False
    try:
        import yaml
        value = yaml.safe_load(text)
    except Exception:
        return False
    return isinstance(value, (dict, list))


def _is_base64(text):
    value = text.strip()
    if len(value) < 16 or len(value) % 4 or not _BASE64_RE.fullmatch(value):
        return False
    try:
        base64.b64decode(value, validate=True)
    except (binascii.Error, ValueError):
        return False
    return True


def _is_hex(text):
    value = text.strip()
    return len(value) >= 8 and len(value) % 2 == 0 and bool(
        _HEX_RE.fullmatch(value))


def _is_hash(text):
    value = text.strip()
    return len(value) in (32, 40, 64, 96, 128) and bool(
        _HEX_RE.fullmatch(value))


def _is_btih(text):
    value = text.strip()
    return bool(_BTIH_HEX_RE.fullmatch(value)
                or _BTIH_BASE32_RE.fullmatch(value))


def _is_email(text):
    return bool(_EMAIL_RE.fullmatch(text.strip()))


def _is_ip(text):
    try:
        ipaddress.ip_address(text.strip())
    except ValueError:
        return False
    return True


def _is_domain(text):
    return bool(_DOMAIN_RE.fullmatch(text.strip()))


def _is_uuid(text):
    try:
        uuid.UUID(text.strip())
    except (ValueError, AttributeError):
        return False
    return True


_DETECTORS = {
    "json": _is_json,
    "xml": _is_xml,
    "csv": _is_csv,
    "yaml": _is_yaml,
    "base64": _is_base64,
    "hex": _is_hex,
    "hash": _is_hash,
    "btih": _is_btih,
    "email": _is_email,
    "ip": _is_ip,
    "domain": _is_domain,
    "uuid": _is_uuid,
}


def detect_format(name, text):
    detector = _DETECTORS.get(name)
    if detector is None or name not in TEXT_FORMATS:
        return False
    try:
        return bool(detector(text))
    except Exception:
        return False


def detect_formats(text, names):
    return {
        name for name in names
        if name in TEXT_FORMATS and detect_format(name, text)
    }
