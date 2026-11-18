"""
Copyright (c) 2026 綦恒智
Email: bmscriptsbox@163.com
SPDX-License-Identifier: MIT
SPDX-License-Identifier: LicenseRef-Commons-Clause

搜索输入的语义解析与匹配上下文。
"""
import os
import re
from dataclasses import dataclass, field
from urllib.parse import unquote, urlsplit

from .input_formats import detect_format


_WIN_DRIVE_RE = re.compile(r"^[A-Za-z]:[\\/]")
_UNC_RE = re.compile(r"^\\\\")
_DOMAIN_RE = re.compile(
    r"^(?=.{1,253}$)(?:[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?\.)+"
    r"[A-Za-z]{2,63}$")
_KNOWN_FILE_EXTENSIONS = frozenset({
    ".aac", ".ape", ".avi", ".bat", ".bz2", ".cab", ".chm", ".cmd", ".com",
    ".csv", ".doc", ".docx", ".epub", ".exe", ".flac", ".flv", ".gif", ".gz",
    ".heic", ".ico", ".iso", ".jar", ".jpeg", ".jpg", ".m4a", ".m4v", ".md",
    ".mid", ".midi", ".mkv", ".mobi", ".mov", ".mp3", ".mp4", ".mpeg", ".mpg",
    ".msi", ".odp", ".ods", ".odt", ".ogg", ".opus", ".pdf", ".png", ".ppt",
    ".pptx", ".ps1", ".rar", ".rtf", ".scr", ".svg", ".tar", ".tgz", ".tif",
    ".tiff", ".torrent", ".txt", ".vbs", ".wav", ".webm", ".webp", ".wma",
    ".wmv", ".xls", ".xlsx", ".xz", ".zip", ".3gp", ".7z",
})
_NON_DOMAIN_TLDS = {
    "7z", "ape", "bat", "bmp", "bz2", "cab", "chm", "cmd", "csv", "css",
    "dll", "doc", "docx", "epub", "exe", "flac", "gif", "gz", "heic",
    "html", "ico", "ini", "iso", "jar", "jpeg", "jpg", "js", "json",
    "log", "m4a", "m4v", "md", "mid", "midi", "mkv", "mobi", "mov",
    "mp3", "mp4", "mpeg", "mpg", "msi", "odt", "ogg", "opus", "pdf",
    "png", "ppt", "pptx", "ps1", "py", "rar", "rtf", "scr", "svg",
    "tar", "tgz", "tif", "tiff", "torrent", "txt", "vbs", "wav",
    "webm", "webp", "wma", "wmv", "xls", "xlsx", "xml", "xz", "zip",
}


@dataclass
class UrlContext:
    scheme: str
    host: str
    domain: str
    path: str
    query: str
    ext: str


@dataclass
class PathContext:
    full: str
    name: str
    ext: str
    exists: bool
    is_file: bool
    is_folder: bool


@dataclass
class InputContext:
    kind: str
    raw: str
    trimmed: str
    length: int
    formats: set = field(default_factory=set)
    url: UrlContext | None = None
    path: PathContext | None = None
    _checked_formats: set = field(default_factory=set)

    def ensure_formats(self, names):
        if self.kind != "text":
            return self.formats
        for name in names:
            if name in self._checked_formats:
                continue
            self._checked_formats.add(name)
            if detect_format(name, self.trimmed):
                self.formats.add(name)
        return self.formats


def _parse_url(text):
    candidate = text
    parsed = urlsplit(candidate)
    if parsed.scheme.lower() not in ("http", "https"):
        if any(ch.isspace() for ch in text):
            return None
        first = text.split("/", 1)[0].split("?", 1)[0].lower()
        first_ext = os.path.splitext(first)[1].lower().lstrip(".")
        if not text.lower().startswith("www.") and (
                not _DOMAIN_RE.fullmatch(first)
                or first_ext in _NON_DOMAIN_TLDS):
            return None
        candidate = "https://" + text
        parsed = urlsplit(candidate)
    if parsed.scheme.lower() not in ("http", "https") or not parsed.netloc:
        return None
    host = (parsed.hostname or "").lower().rstrip(".")
    if not host:
        return None
    path = unquote(parsed.path or "/")
    if not path.startswith("/"):
        path = "/" + path
    ext = os.path.splitext(path)[1].lower()
    return UrlContext(
        scheme=parsed.scheme.lower(),
        host=host,
        domain=host,
        path=path,
        query=parsed.query or "",
        ext=ext,
    )


def _looks_like_path(text):
    if os.path.exists(text):
        return True
    if _WIN_DRIVE_RE.match(text) or _UNC_RE.match(text):
        return True
    if text.startswith(("./", "../", ".\\", "..\\", "/", "\\")):
        return True
    if " " not in text and "\\" in text:
        return True
    if " " not in text and "@" not in text:
        ext = os.path.splitext(text)[1].lower()
        if ext in _KNOWN_FILE_EXTENSIONS:
            return True
    return False


def _parse_path(text):
    full = os.path.normpath(text)
    name = os.path.basename(full.rstrip("\\/")) or full
    ext = os.path.splitext(name)[1].lower()
    exists = os.path.exists(text)
    is_file = exists and os.path.isfile(text)
    is_folder = exists and os.path.isdir(text)
    return PathContext(
        full=full,
        name=name,
        ext=ext,
        exists=exists,
        is_file=is_file,
        is_folder=is_folder,
    )


def build_context(raw):
    raw = str(raw or "")
    trimmed = raw.strip()
    if trimmed.lower().startswith("magnet:"):
        return InputContext(
            kind="magnet",
            raw=raw,
            trimmed=trimmed,
            length=len(trimmed),
        )

    url = _parse_url(trimmed)
    if url is not None:
        return InputContext(
            kind="url",
            raw=raw,
            trimmed=trimmed,
            length=len(trimmed),
            url=url,
        )

    if _looks_like_path(trimmed):
        return InputContext(
            kind="path",
            raw=raw,
            trimmed=trimmed,
            length=len(trimmed),
            path=_parse_path(trimmed),
        )

    return InputContext(
        kind="text",
        raw=raw,
        trimmed=trimmed,
        length=len(trimmed),
    )
