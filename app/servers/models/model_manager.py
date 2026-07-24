"""
Copyright (c) 2026 綦恒智
Email: bmscriptsbox@163.com
SPDX-License-Identifier: AGPL-3.0
"""
import json
import fnmatch
import shutil
import time
from pathlib import Path
from typing import List, Optional

from PySide2.QtCore import QObject, Signal

from app.utils import BmTools, BM_LOG
from .hf_downloader import HuggingFaceDownloader
from .ms_downloader import ModelScopeDownloader


class ModelManager(QObject):
    """模型管理器 — 统筹模型下载、本地追踪、路径查询"""
    model_progress = Signal(dict)
    model_error = Signal(str, str)  # repo_id, error_msg

    def __init__(self):
        super().__init__()
        self.base_path = BmTools.get_root_path() / 'BmPackages' / 'BmModels'
        self.base_path.mkdir(parents=True, exist_ok=True)
        self.json_path = BmTools.get_root_path() / 'BmData' / 'BmModels.json'
        self._cancelled = False

    # --- 公开接口 ---

    def batch_download(self, models: list) -> bool:
        if not models:
            return True

        # 检查磁盘剩余空间（BmModels 所在分区）
        free_gb = shutil.disk_usage(self.base_path).free / (1024 ** 3)
        if free_gb < 10:
            BM_LOG.error(f"[MS] 磁盘空间不足：剩余 {free_gb:.1f}GB，需要至少 10GB")
            return False

        all_ok = True
        for m in models:
            if self._cancelled:
                break
            try:
                self._download_single(m)
            except Exception as e:
                BM_LOG.error(f"模型 {m.repo_id} 下载失败: {e}")
                self.model_error.emit(m.repo_id, str(e))
                all_ok = False
        return all_ok

    def cancel(self):
        self._cancelled = True

    def get_model_path(self, repo_id: str) -> Optional[str]:
        manifest = self._read_manifest()
        info = manifest.get(repo_id)
        if info:
            p = Path(info['path'])
            if p.exists():
                return str(p)
        return None

    # --- 内部方法 ---

    def _download_single(self, model):
        repo_id = model.repo_id
        dest_dir = self.base_path / repo_id

        if self._is_downloaded(model):
            self._emit_progress(f"模型 {repo_id} 已存在，跳过")
            return

        self._emit_progress(f"开始下载模型 {repo_id} ...")
        dest_dir.mkdir(parents=True, exist_ok=True)

        if model.source == "huggingface":
            dl = HuggingFaceDownloader()
        elif model.source == "modelscope":
            dl = ModelScopeDownloader()
        else:
            raise ValueError(f"不支持的模型来源: {model.source}")

        dl.download(
            model=model,
            dest_dir=dest_dir,
            progress_cb=lambda done, total, fname: self._emit_progress(
                f"模型 {repo_id} {done}/{total} ({fname})"
            ),
            cancel_check=lambda: self._cancelled,
            progress_emitter=self.model_progress.emit,
        )

        self._update_manifest(repo_id, str(dest_dir), model.source)
        self._emit_progress(f"模型 {repo_id} 下载完成")

    def _is_downloaded(self, model) -> bool:
        repo_id = model.repo_id
        dest_dir = self.base_path / repo_id
        manifest = self._read_manifest()
        info = manifest.get(repo_id)
        if not info:
            return False
        if not dest_dir.exists():
            return False

        existing_files = [f.name for f in dest_dir.iterdir() if f.is_file()]
        if not existing_files:
            return False

        # 如果声明了具体文件模式，逐一验证实际文件是否存在
        if model.files and model.files != ["*"]:
            for pattern in model.files:
                if not fnmatch.filter(existing_files, pattern):
                    BM_LOG.warning(f"模型 {repo_id} 文件不完整（缺少 {pattern}），重新下载")
                    return False

        return True

    def _read_manifest(self) -> dict:
        if not self.json_path.exists():
            return {}
        try:
            with open(self.json_path, 'r', encoding='utf-8') as f:
                return json.load(f) or {}
        except Exception:
            return {}

    def _update_manifest(self, repo_id: str, path: str, source: str):
        data = self._read_manifest()
        data[repo_id] = {
            "source": source,
            "repo_id": repo_id,
            "path": path,
            "downloaded_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        }
        self.json_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.json_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

    def _emit_progress(self, msg: str):
        self.model_progress.emit({'status': True, 'msg': msg})
