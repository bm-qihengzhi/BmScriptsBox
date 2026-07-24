"""
Copyright (c) 2026 綦恒智
Email: bmscriptsbox@163.com
SPDX-License-Identifier: AGPL-3.0
"""
import fnmatch
from pathlib import Path

import requests

from app.servers.packages.download import XDownLoad
from app.utils import BM_LOG


class ModelScopeDownloader:
    """ModelScope 模型下载器 — 基于 HTTP API（零额外依赖）"""

    def __init__(self):
        self.api_base = "https://modelscope.cn"
        self.session = requests.Session()
        self.session.trust_env = False

    def download(self, model, dest_dir: Path,
                 progress_cb, cancel_check,
                 progress_emitter=None) -> bool:
        # 1. 获取文件列表
        BM_LOG.info(f"[MS] 列出 {model.repo_id} 文件列表 ...")
        files = self._list_files(model.repo_id)

        if files:
            target_files = self._filter_files(files, model.files)
        else:
            # 列表为空但用户指定了精确文件名 → 直接尝试下载
            BM_LOG.warning(f"[MS] 文件列表为空，尝试按文件名直接下载")
            exact = [f for f in model.files if not set(f) & {'*', '?', '[', ']'}]
            target_files = [{'Path': f} for f in exact] if exact else []

        BM_LOG.info(f"[MS] 需要下载 {len(target_files)} 个文件")

        # 2. 逐个下载
        total = len(target_files)
        downloaded = 0
        for f in target_files:
            if cancel_check():
                BM_LOG.info("[MS] 下载已取消")
                return False

            file_path = f['Path']  # 如 "model.safetensors" 或 "subdir/config.json"
            file_url = f"{self.api_base}/models/{model.repo_id}/resolve/master/{file_path}"

            # 创建子目录（文件可能在子目录中）
            save_dir = dest_dir / Path(file_path).parent
            save_dir.mkdir(parents=True, exist_ok=True)

            BM_LOG.info(f"[MS] 下载 ({downloaded + 1}/{total}): {file_path}")
            try:
                xd = XDownLoad()
                if progress_emitter:
                    xd.download_progress.connect(progress_emitter)
                xd.download(file_url, str(save_dir))
            except Exception as e:
                BM_LOG.warning(f"[MS] 文件 {file_path} 下载失败: {e}")
                raise

            downloaded += 1
            progress_cb(downloaded, total, file_path)

        return True

    def _list_files(self, repo_id: str) -> list:
        """调用 ModelScope API 获取文件列表"""
        url = f"{self.api_base}/api/v1/models/{repo_id}/repo/files?Recursive=true"
        try:
            resp = self.session.get(url, timeout=15)
            resp.raise_for_status()
            data = resp.json()
            BM_LOG.debug(f"[MS] API 响应: {str(data)[:500]}")
            if data.get('Success'):
                files = data.get('Data', {}).get('Files', [])
                if isinstance(files, list):
                    return files
            return []
        except Exception as e:
            BM_LOG.error(f"[MS] 获取文件列表失败: {e}")
            return []

    def _filter_files(self, files: list, patterns: list) -> list:
        if patterns == ["*"]:
            return [f for f in files if f.get('Type') == 'blob']
        result = []
        for f in files:
            if f.get('Type') != 'blob':
                continue
            fpath = f.get('Path', '')
            for p in patterns:
                if fnmatch.fnmatch(fpath, p):
                    result.append(f)
                    break
        return result
