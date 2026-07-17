"""
Copyright (c) 2026 綦恒智
Email: bmscriptsbox@163.com
SPDX-License-Identifier: AGPL-3.0
"""

import threading


class ProjectGlobal:
    _lock = threading.Lock()

    @classmethod
    def safe_get(cls, name):
        with cls._lock:
            return getattr(cls, name)

    @classmethod
    def safe_set(cls, name, value):
        with cls._lock:
            setattr(cls, name, value)
    SCRIPTS = None
    MENU = None
    CONFIG = None
    LOGIN_CODE = None
    Task = None
    BM_BINARY_RESOURCE_UR = "https://raw.githubusercontent.com/bm-qihengzhi/BmBinaryResource/refs/heads/main/"
    # BANNER_DATA_URL = 'https://raw.githubusercontent.com/bm-qihengzhi/BmMinorUpdate/refs/heads/main/banner.json'
    BANNER_DATA_URL = 'https://static.bm-box.cn/bm-update/banner.json'
    # REMOTE_VERSION_URL = 'https://raw.githubusercontent.com/bm-qihengzhi/BmMinorUpdate/refs/heads/main/version.json'
    REMOTE_VERSION_URL = 'https://static.bm-box.cn/bm-update/version.json'
    API_GATEWAY = 'https://www.bm-box.cn'
    SOFT_VERSION = None
    LANGUAGE = None
    RUNNING_SCRIPTS_LOCK = threading.Lock()
    RUNNING_SCRIPTS = set()
    PROXIES = [
    "https://v4.gh-proxy.org/",
    "https://gh-proxy.org/",
    "https://github.1zyq1.com/",
    "https://v6.gh-proxy.org/",
    "https://cdn.gh-proxy.org/"
  ]

