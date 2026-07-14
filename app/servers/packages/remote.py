"""
Copyright (c) 2026 綦恒智
Email: bmscriptsbox@163.com
SPDX-License-Identifier: AGPL-3.0
"""
import random
import time
from typing import Dict, Any

import requests
from app.data import ProjectGlobal


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

        try:
            response = self._session.get(
                url,
                headers=self._get_random_headers(),
                timeout=(5, 20))
            response.raise_for_status()
            data = response.json()

            # 3. 更新缓存及时间戳
            self._cache[cache_key] = {
                'content': data,
                'timestamp': now,

            }
            return data

        except Exception as e:
            if cache_key in self._cache:
                return self._cache[cache_key]['content']
            raise RuntimeError(f"无法获取远程清单: {e}")


    def get_banner_manifest(self) -> Dict:
        """
        获取banner配置
        """
        cache_key = 'banner'
        now = time.time()

        # 1. 检查缓存是否有效
        if cache_key in self._cache:
            entry = self._cache[cache_key]
            if now - entry['timestamp'] < self.cache_ttl:
                return entry['content']

        url = ProjectGlobal.BANNER_DATA_URL
        try:
            response = self._session.get(
                url,
                headers=self._get_random_headers(),
                timeout=(5, 20))
            response.raise_for_status()
            data = response.json()

            # 3. 更新缓存及时间戳
            self._cache[cache_key] = {
                'content': data,
                'timestamp': now,

            }
            return data

        except Exception as e:
            if cache_key in self._cache:
                return self._cache[cache_key]['content']
            raise RuntimeError(f"无法获取远程清单: {e}")





if __name__ == '__main__':
    remote = RemoteManifestProvider()
    print(remote.get_banner_manifest())
    print(remote._cache)
