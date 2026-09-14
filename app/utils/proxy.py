"""
Copyright (c) 2026 綦恒智
Email: bmscriptsbox@163.com
SPDX-License-Identifier: MIT
SPDX-License-Identifier: LicenseRef-Commons-Clause
"""
import concurrent.futures
import time
from typing import Dict, List

import requests

from app.data import ProjectGlobal

CACHE_TTL = 120  # 2 分钟
_sorted_prefixes: List[str] = None
_cache_time: float = 0


def get_sorted_proxies(target_url: str) -> List[str]:
    """
    对 GitHub 代理 URL 并行测速，按速度降序返回，2 分钟缓存

    缓存的是代理前缀的排序顺序，不依赖 target_url，
    因此不同 URL 可复用同一份测速结果。

    Args:
        target_url: 需要下载的原始 GitHub URL

    Returns:
        按速度降序排列的代理 URL 列表
    """
    global _sorted_prefixes, _cache_time

    now = time.time()
    if _sorted_prefixes and now - _cache_time < CACHE_TTL:
        return [_build_proxy_url(p, target_url) for p in _sorted_prefixes]

    prefixes = ProjectGlobal.PROXIES
    if len(prefixes) <= 1:
        _sorted_prefixes = list(prefixes)
        _cache_time = now
        return [_build_proxy_url(p, target_url) for p in prefixes]

    # 构建 (代理前缀 → 完整测速 URL) 映射
    proxy_map: Dict[str, str] = {p: _build_proxy_url(p, target_url) for p in prefixes}
    sorted_urls = _probe_urls(list(proxy_map.values()))

    # 从测速结果反推代理前缀的排序
    url_to_prefix: Dict[str, str] = {v: k for k, v in proxy_map.items()}
    _sorted_prefixes = []
    seen = set()
    for url in sorted_urls:
        prefix = url_to_prefix.get(url)
        if prefix and prefix not in seen:
            _sorted_prefixes.append(prefix)
            seen.add(prefix)
    # 未测到的放末尾
    for p in prefixes:
        if p not in seen:
            _sorted_prefixes.append(p)

    _cache_time = now
    return [_build_proxy_url(p, target_url) for p in _sorted_prefixes]


def _build_proxy_url(prefix: str, target_url: str) -> str:
    return f"{prefix.rstrip('/')}/{target_url}"


def _probe_urls(urls: List[str]) -> List[str]:
    """并行测速多个 URL，按速度降序排列"""
    PROBE_BYTES = 256 * 1024
    FAST_ENOUGH = 100 * 1024
    PROBE_TIMEOUT = 6

    probe_headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
        'Accept-Encoding': 'identity',
    }

    def _probe_one(url):
        try:
            start = time.time()
            downloaded = 0
            with requests.get(url, headers=probe_headers, stream=True, timeout=(3, 5)) as r:
                r.raise_for_status()
                for chunk in r.iter_content(128 * 1024):
                    if chunk:
                        downloaded += len(chunk)
                    if downloaded >= PROBE_BYTES:
                        break
            elapsed = time.time() - start
            if elapsed <= 0 or downloaded <= 0:
                return None
            return (downloaded / elapsed, url)
        except Exception:
            return None

    pool = concurrent.futures.ThreadPoolExecutor(max_workers=len(urls))
    futures = {pool.submit(_probe_one, u): u for u in urls}
    results = []
    try:
        for f in concurrent.futures.as_completed(futures, timeout=PROBE_TIMEOUT):
            r = f.result()
            if r:
                results.append(r)
                speed_bps, url = r
                if speed_bps >= FAST_ENOUGH:
                    for ff in futures:
                        ff.cancel()
                    break
    except concurrent.futures.TimeoutError:
        pass
    pool.shutdown(wait=False)

    if not results:
        return urls

    results.sort(key=lambda x: x[0], reverse=True)
    sorted_urls = [url for _, url in results]
    probed_set = set(sorted_urls)
    sorted_urls.extend(u for u in urls if u not in probed_set)
    return sorted_urls
