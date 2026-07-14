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
    BM_BINARY_RESOURCE_UR = "https://gitee.com/bmscriptsbox/bm-binary-resource/raw/master/"
    BANNER_DATA_URL = 'https://gitee.com/bmscriptsbox/bm-minor-update/raw/master/banner.json'
    REMOTE_VERSION_URL = 'https://gitee.com/bmscriptsbox/bm-minor-update/raw/master/version.json'
    API_GATEWAY = ''
    SOFT_VERSION = None
    LANGUAGE = None
    RUNNING_SCRIPTS_LOCK = threading.Lock()
    RUNNING_SCRIPTS = set()
    PROXIES = [
    "https://gh-proxy.org/",
    "https://git.yylx.win",
    "https://gh.llkk.cc/",
    "https://gh.xxooo.cf/",
    "https://gh-proxy.ygxz.in/",
    "https://gh-proxy.net/"
  ]


if __name__ == "__main__":
    ProjectGlobal.SCRIPTS = ['2', '3']  # 修改全局配置
    print(ProjectGlobal.SCRIPTS)
