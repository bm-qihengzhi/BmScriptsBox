"""
Copyright (c) 2026 綦恒智
Email: bmscriptsbox@163.com
SPDX-License-Identifier: MIT
SPDX-License-Identifier: LicenseRef-Commons-Clause
"""
import random
import time
from typing import Dict, Any

import requests
from app.data import ProjectGlobal
from app.utils.proxy import get_sorted_proxies
from app.utils.region import is_china


class RemoteManifestProvider:
    """
    负责从 Gitee/GitHub 拉取静态配置
    具备自动过期机制的缓存功能、确保数据实时性和性能的平衡
    """

    USER_AGENTS = [
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:122.0) Gecko/20100101 Firefox/122.0",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36 Edg/121.0.0.0",
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36"
    ]

    def __init__(self, cache_ttl: int = 600):
        self._cache: Dict[str, Dict[str, Any]] = {}
        self.cache_ttl = cache_ttl
        self._session = requests.Session()
        self._session.trust_env = False
        self._is_china = is_china()

    def _get_random_headers(self) -> Dict[str, str]:
        """生成随机的请求头"""
        return {
            "User-Agent": random.choice(self.USER_AGENTS),
            "Accept": "application/json",
            "Cache-Control": "no-cache",  # 告诉服务器/CDN 我们想要最新的数据
        }

    def clear_cache(self):
        """手动清空所有缓存"""
        self._cache.clear()

    def _fetch_json(self, url: str) -> Dict:
        """发起一次 JSON 请求，失败抛出异常"""
        response = self._session.get(url, headers=self._get_random_headers(), timeout=(5, 20))
        response.raise_for_status()
        return response.json()

    def get_package_manifest(self, file_name: str) -> Dict:
        """
        获取包配置数据（带过期检查）
        """
        if not file_name:
            raise ValueError("文件名不能为空")

        cache_key = file_name.lower()
        now = time.time()

        # 1. 检查缓存是否有效
        if cache_key in self._cache:
            entry = self._cache[cache_key]
            if now - entry['timestamp'] < self.cache_ttl:
                return entry['content']

        # 2. 缓存失效或不存在，发起网络请求
        base_url = ProjectGlobal.BM_BINARY_RESOURCE_UR.rstrip('/')
        url = f"{base_url}/{cache_key}.json"
        is_github = "github" in url.lower()

        last_exception = None
        data = None

        # 中国区 + GitHub 域名时优先走加速代理，否则直连优先
        if is_github and self._is_china:
            candidates = get_sorted_proxies(url)
            candidates.append(url)
        else:
            candidates = [url]

        for try_url in candidates:
            try:
                data = self._fetch_json(try_url)
                break
            except Exception as e:
                last_exception = e
                continue

        # 兜底：非中国区直连失败时，再尝试加速代理（兼容本地挂梯子场景）
        if data is None and is_github and not self._is_china:
            try:
                for proxy_url in get_sorted_proxies(url):
                    try:
                        data = self._fetch_json(proxy_url)
                        break
                    except Exception as e:
                        last_exception = e
                        continue
            except Exception as e:
                last_exception = e

        if data is not None:
            # 3. 更新缓存及时间戳
            self._cache[cache_key] = {
                'content': data,
                'timestamp': now,
            }
            return data

        if cache_key in self._cache:
            return self._cache[cache_key]['content']
        raise RuntimeError(f"无法获取远程清单: {last_exception}")

    def get_banner_manifest(self) -> Dict:
        """
        获取banner配置
        """
        cache_key = 'banner'
        now = time.time()

        # 检查缓存是否有效
        if cache_key in self._cache:
            entry = self._cache[cache_key]
            if now - entry['timestamp'] < self.cache_ttl:
                return entry['content']

        try:
            data = self._fetch_json(ProjectGlobal.BANNER_DATA_URL)
            # 更新缓存及时间戳
            self._cache[cache_key] = {
                'content': data,
                'timestamp': now,
            }
            return data

        except Exception as e:
            if cache_key in self._cache:
                return self._cache[cache_key]['content']
            raise RuntimeError(f"无法获取远程清单: {e}")



