"""
Copyright (c) 2026 綦恒智
Email: bmscriptsbox@163.com
SPDX-License-Identifier: MIT
SPDX-License-Identifier: LicenseRef-Commons-Clause
"""
import time

import requests

_IS_CHINA = None
_CACHE_TIME = 0


def is_china() -> bool:
    """检测当前网络是否在中国区，10 分钟缓存"""
    global _IS_CHINA, _CACHE_TIME
    now = time.time()
    if _IS_CHINA is not None and now - _CACHE_TIME < 600:
        return _IS_CHINA
    try:
        r = requests.get("http://ip-api.com/json/?fields=countryCode", timeout=2)
        _IS_CHINA = r.json().get("countryCode") == "CN"
    except Exception:
        _IS_CHINA = True
    _CACHE_TIME = now
    return _IS_CHINA


