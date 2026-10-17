"""
Copyright (c) 2026 綦恒智
Email: bmscriptsbox@163.com
SPDX-License-Identifier: MIT
SPDX-License-Identifier: LicenseRef-Commons-Clause

直连二进制的完整性（按 tag TOFU）与用户信任（确认记忆）持久化。

- BmBinaryHashes.json : { "<name>": { "<tag>": "<sha256>" } }
  首次见到某 tag 时记录其哈希并放行（Trust On First Use）；
  同一 tag 再次出现却哈希不同 → 视为篡改，硬失败。
- BmBinaryTrust.json  : { "<script_id>|<url>": true }
  用户在确认弹窗勾选"记住此来源"后，后续同一脚本同一 URL 不再询问。
"""
import hashlib
import json
import os
from pathlib import Path
from typing import Optional

from app.utils import BmTools, BM_LOG


def sha256_file(path) -> str:
    """流式计算文件 sha256（十六进制小写）"""
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()


class BinaryIntegrityStore:
    """直连二进制完整性 + 信任的本地存储"""

    def __init__(self, root: Optional[Path] = None):
        base = (Path(root) if root else BmTools.get_root_path()) / 'BmData'
        base.mkdir(parents=True, exist_ok=True)
        self._hash_file = base / 'BmBinaryHashes.json'
        self._trust_file = base / 'BmBinaryTrust.json'

    # --- 通用读写 ---

    @staticmethod
    def _load(path: Path) -> dict:
        try:
            if path.exists():
                with open(path, 'r', encoding='utf-8') as f:
                    return json.load(f) or {}
        except Exception as e:
            BM_LOG.warning(f"[完整性] 读取 {path.name} 失败: {e}")
        return {}

    @staticmethod
    def _save(path: Path, data: dict):
        try:
            tmp = path.with_suffix('.json.tmp')
            with open(tmp, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            os.replace(tmp, path)
        except Exception as e:
            BM_LOG.warning(f"[完整性] 写入 {path.name} 失败: {e}")

    # --- 哈希 TOFU ---

    def check_and_record_hash(self, name: str, tag: str, actual_sha: str,
                              strict: bool = True) -> bool:
        """
        返回校验是否通过。
        - 已记录该 tag 且哈希一致 → True
        - 已记录该 tag 但哈希不同：
            strict=True  → False（视为篡改，硬失败）
            strict=False → 覆盖记录新哈希并告警，返回 True（滚动 tag 正常更新）
        - 未记录该 tag → 记录后 True（首次信任）
        """
        data = self._load(self._hash_file)
        key = (name or '').strip().lower()
        tag_key = (tag or 'latest').strip() or 'latest'
        actual = (actual_sha or '').strip().lower()
        entry = data.setdefault(key, {})
        known = entry.get(tag_key)
        if known:
            if known != actual:
                if strict:
                    BM_LOG.error(
                        f"[完整性] {name} tag={tag_key} 哈希不匹配: 记录={known} 实际={actual}")
                    return False
                BM_LOG.warning(
                    f"[完整性] {name} tag={tag_key} 内容变化（滚动 tag，已更新记录）: "
                    f"旧={known} 新={actual}")
                entry[tag_key] = actual
                self._save(self._hash_file, data)
                return True
            return True
        entry[tag_key] = actual
        self._save(self._hash_file, data)
        BM_LOG.info(f"[完整性] 首次记录 {name} tag={tag_key} sha256={actual}")
        return True

    # --- 用户信任 ---

    @staticmethod
    def _trust_key(script_id: str, url: str) -> str:
        return f"{(script_id or '').strip()}|{(url or '').strip()}"

    def is_trusted(self, script_id: str, url: str) -> bool:
        return bool(self._load(self._trust_file).get(self._trust_key(script_id, url)))

    def trust(self, script_id: str, url: str):
        data = self._load(self._trust_file)
        data[self._trust_key(script_id, url)] = True
        self._save(self._trust_file, data)

    def untrust(self, script_id: str, url: str):
        data = self._load(self._trust_file)
        if data.pop(self._trust_key(script_id, url), None) is not None:
            self._save(self._trust_file, data)

    def list_trusted(self) -> list:
        return sorted(self._load(self._trust_file).keys())
