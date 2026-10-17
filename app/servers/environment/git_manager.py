"""
Copyright (c) 2026 綦恒智
Email: bmscriptsbox@163.com
SPDX-License-Identifier: MIT
SPDX-License-Identifier: LicenseRef-Commons-Clause
"""
import json
import shutil
import time
from pathlib import Path
from urllib.parse import quote, urlparse

import pygit2

from app.servers.packages.download import XDownLoad
from app.servers.packages.unzip import ArchiveExtractor
from app.utils import BM_LOG, BmTools
from app.utils.proxy import get_sorted_proxies
from app.utils.region import is_china


class GitManager:
    """脚本仓库下载管理器 - GitHub 仓库走归档 zip（mudl 多线程下载 + 7zr 解压），其余回退 git 克隆"""

    # 更新脚本时需保留的环境目录 / 记录文件（在同步时一律不删除）
    PRESERVE = {'.venv', 'node_modules', '.git', '.bm-sync-manifest.json', '.bm-source.json'}

    def download_script_from_git(self, git_url: str, script_dir: str, branch: str = 'main') -> bool:
        dir_path = Path(script_dir).resolve()

        # 失败时不再删除既有安装目录（更新场景下那是旧版本），交由上层回滚决定
        try:
            if 'github.com' in git_url:
                try:
                    if self._download_archive(git_url, dir_path, branch):
                        return True
                except Exception as e:
                    BM_LOG.warning(f"GitHub 归档下载失败，回退 git 克隆: {e}")
            return self._clone_with_pygit2(git_url, dir_path, branch)
        except Exception as e:
            BM_LOG.error(f"下载脚本失败: {e}")
            return False

    # --- GitHub 归档 zip 下载 ---

    def _download_archive(self, git_url: str, dir_path: Path, branch: str) -> bool:
        owner_repo = self._parse_github_url(git_url)
        if not owner_repo:
            raise ValueError(f"无法解析 GitHub 仓库地址: {git_url}")
        owner, repo = owner_repo

        codeload_url = f"https://codeload.github.com/{owner}/{repo}/zip/refs/heads/{quote(branch, safe='/')}"
        zip_name = f"{repo}-{branch.replace('/', '-')}.zip"

        tmp_base = dir_path.parent / f".{dir_path.name}.tmp-{int(time.time() * 1000)}"
        tmp_zip_dir = tmp_base / "zip"
        tmp_extract_dir = tmp_base / "extract"
        try:
            tmp_zip_dir.mkdir(parents=True, exist_ok=True)

            BM_LOG.info(f"下载 GitHub 归档: {codeload_url[:90]}...")
            xd = XDownLoad()
            zip_path = xd.download(codeload_url, str(tmp_zip_dir), output_filename=zip_name)

            ArchiveExtractor().extract(zip_path, str(tmp_extract_dir))

            src = self._find_single_subdir(tmp_extract_dir) or tmp_extract_dir

            # 合并覆盖：将新内容同步进原目录，保留 .venv / node_modules / .git
            # 下载/解压成功后才开始合并，失败时原目录不受影响
            dir_path.mkdir(parents=True, exist_ok=True)
            self._sync_dir(src, dir_path)

            marker = {
                'source': git_url,
                'branch': branch,
                'downloaded_at': time.strftime("%Y-%m-%dT%H:%M:%S"),
            }
            (dir_path / '.bm-source.json').write_text(
                json.dumps(marker, ensure_ascii=False), encoding='utf-8')

            BM_LOG.info(f"Git 归档下载成功: {dir_path}")
            return True
        finally:
            if tmp_base.exists():
                BmTools.remove_dir(tmp_base)

    @staticmethod
    def _parse_github_url(url: str):
        """从 GitHub 地址中解析 owner / repo"""
        parsed = urlparse(url)
        parts = [p for p in parsed.path.split('/') if p]
        if len(parts) < 2:
            return None
        repo = parts[1]
        if repo.endswith('.git'):
            repo = repo[:-4]
        return parts[0], repo

    @staticmethod
    def _find_single_subdir(folder: Path):
        """归档 zip 内含唯一顶层目录时返回该目录，否则返回 None"""
        entries = [p for p in Path(folder).iterdir()]
        if len(entries) == 1 and entries[0].is_dir():
            return entries[0]
        return None

    @classmethod
    def _sync_dir(cls, src: Path, dest: Path):
        """
        递归合并 src 到 dest：
        - 新文件覆盖旧文件，新子目录递归合并；
        - 仅清理“上次同步记录中、本次已从仓库移除”的内容，保留 .venv/node_modules/.git
          以及用户自建的数据文件（未被同步清单记录者不动）。
        """
        src_names = {p.name for p in src.iterdir()}
        for item in src.iterdir():
            if item.name == '.git':
                continue
            target = dest / item.name
            if item.is_dir():
                if target.exists():
                    cls._sync_dir(item, target)
                else:
                    shutil.copytree(item, target)
            else:
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(item, target)

        # 只删除“上次同步清单里有、本次仓库已没有”的条目（保留环境目录与用户文件）
        old_names = cls._read_sync_manifest(dest)
        for name in old_names:
            if name in src_names or name in cls.PRESERVE:
                continue
            victim = dest / name
            if victim.is_dir():
                BmTools.remove_dir(victim)
            else:
                victim.unlink(missing_ok=True)

        cls._write_sync_manifest(dest, src_names)

    _SYNC_MANIFEST_NAME = '.bm-sync-manifest.json'

    @classmethod
    def _sync_manifest_path(cls, dest: Path) -> Path:
        return dest / cls._SYNC_MANIFEST_NAME

    @classmethod
    def _read_sync_manifest(cls, dest: Path) -> set:
        """读取该目录上次同步的子项名集合；无清单（旧安装）返回空集 → 不删除任何旧内容"""
        try:
            path = cls._sync_manifest_path(dest)
            if path.exists():
                data = json.loads(path.read_text(encoding='utf-8'))
                if isinstance(data, list):
                    return set(data)
        except Exception as e:
            BM_LOG.debug(f"读取同步清单失败 {dest}: {e}")
        return set()

    @classmethod
    def _write_sync_manifest(cls, dest: Path, names: set):
        try:
            cls._sync_manifest_path(dest).write_text(
                json.dumps(sorted(names), ensure_ascii=False), encoding='utf-8')
        except Exception as e:
            BM_LOG.debug(f"写入同步清单失败 {dest}: {e}")

    # --- git 克隆兜底 ---

    def _clone_with_pygit2(self, git_url: str, dir_path: Path, branch: str) -> bool:
        dir_path.parent.mkdir(parents=True, exist_ok=True)

        # 克隆到临时目录，成功后再合并进目标目录（保留 .venv/node_modules 与用户文件，
        # 且失败时不破坏既有安装）
        tmp_dir = dir_path.parent / f".{dir_path.name}.clone-{int(time.time() * 1000)}"

        is_github = 'github.com' in git_url

        # 中国区：加速代理优先；非中国区：直连优先（挂梯子时通常可直连）
        if is_github and is_china():
            urls = get_sorted_proxies(git_url) + [git_url]
        else:
            urls = [git_url]

        def _try_clone(candidates) -> bool:
            for url in candidates:
                try:
                    pygit2.clone_repository(url, str(tmp_dir), depth=1, checkout_branch=branch)
                    BM_LOG.info(f"Git 克隆成功: {url[:60]}...")
                    return True
                except Exception as e:
                    BM_LOG.debug(f"克隆失败 ({url[:60]}...): {e}")
                    if tmp_dir.exists():
                        BmTools.remove_dir(tmp_dir)
                    continue
            return False

        try:
            cloned = _try_clone(urls)
            # 兜底：非中国区直连失败时再尝试加速代理
            if not cloned and is_github and not is_china():
                cloned = _try_clone(get_sorted_proxies(git_url))
            if not cloned:
                BM_LOG.error("所有代理尝试克隆都失败")
                return False

            dir_path.mkdir(parents=True, exist_ok=True)
            self._sync_dir(tmp_dir, dir_path)
            marker = {
                'source': git_url,
                'branch': branch,
                'downloaded_at': time.strftime("%Y-%m-%dT%H:%M:%S"),
            }
            (dir_path / '.bm-source.json').write_text(
                json.dumps(marker, ensure_ascii=False), encoding='utf-8')
            return True
        finally:
            if tmp_dir.exists():
                BmTools.remove_dir(tmp_dir)