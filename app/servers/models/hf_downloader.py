"""
Copyright (c) 2026 綦恒智
Email: bmscriptsbox@163.com
SPDX-License-Identifier: AGPL-3.0
"""
import os
import fnmatch
from pathlib import Path

from app.utils import BM_LOG


class HuggingFaceDownloader:
    """HuggingFace 模型下载器 — 基于 huggingface_hub SDK"""

    def download(self, model, dest_dir: Path,
                 progress_cb, cancel_check, progress_emitter=None) -> bool:
        # 设置 HF 镜像源（国内用户加速），必须在 import huggingface_hub 之前
        os.environ.setdefault("HF_ENDPOINT", "https://hf-mirror.com")

        from huggingface_hub import list_repo_files, hf_hub_url
        from app.servers.packages.download import XDownLoad

        # 1. 获取文件列表
        BM_LOG.info(f"[HF] 列出 {model.repo_id} 文件列表 ...")
        all_files = list_repo_files(model.repo_id)

        # 2. 按 files 模式过滤
        target_files = self._filter_files(all_files, model.files)
        BM_LOG.info(f"[HF] 需要下载 {len(target_files)} 个文件")

        # 3. 用 XDownLoad 逐个下载（带实时进度信号）
        total = len(target_files)
        for i, fname in enumerate(target_files, 1):
            if cancel_check():
                BM_LOG.info("[HF] 下载已取消")
                return False

            file_url = hf_hub_url(repo_id=model.repo_id, filename=fname)
            save_dir = dest_dir / Path(fname).parent
            save_dir.mkdir(parents=True, exist_ok=True)

            BM_LOG.info(f"[HF] 下载 ({i}/{total}): {fname}")
            try:
                xd = XDownLoad()
                if progress_emitter:
                    xd.download_progress.connect(progress_emitter)
                xd.download(file_url, str(save_dir))
            except Exception as e:
                BM_LOG.warning(f"[HF] 文件 {fname} 下载失败: {e}")
                raise

            progress_cb(i, total, fname)

        return True

    def _filter_files(self, files: list, patterns: list) -> list:
        if patterns == ["*"]:
            return files
        result = []
        for f in files:
            for p in patterns:
                if fnmatch.fnmatch(f, p):
                    result.append(f)
                    break
        return result
