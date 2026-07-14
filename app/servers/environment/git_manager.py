"""
Copyright (c) 2026 綦恒智
Email: bmscriptsbox@163.com
SPDX-License-Identifier: AGPL-3.0
"""
import shutil
from pathlib import Path

import pygit2

from app.data import ProjectGlobal
from app.utils import BM_LOG


class GitManager:
    def __init__(self):
        self.github_proxies = ProjectGlobal.PROXIES

    def download_script_from_git(self, git_url: str, script_dir: str, branch: str = 'main') -> bool:
        dir_path = Path(script_dir).resolve()

        try:
            # 场景1：已存在 git 仓库 → git pull
            if dir_path.exists() and (dir_path / '.git').exists():
                try:
                    repo = pygit2.Repository(str(dir_path))
                    for remote in repo.remotes:
                        remote.fetch()
                    branch_ref = f'refs/remotes/origin/{branch}'
                    if branch_ref in repo.listall_references():
                        repo.reset(repo.references[branch_ref].target, pygit2.GIT_RESET_HARD)
                    BM_LOG.info(f"Git 更新成功: {dir_path}")
                    return True
                except Exception as e:
                    BM_LOG.warning(f"Git pull 失败，回退到重新克隆: {e}")

            # 场景2：目录存在但没 git（上次安装异常）→ 清理后克隆
            if dir_path.exists():
                for _ in range(3):
                    try:
                        shutil.rmtree(dir_path)
                        break
                    except Exception:
                        continue

            # 场景3：全新克隆
            dir_path.parent.mkdir(parents=True, exist_ok=True)

            urls = [git_url]
            if 'github.com' in git_url:
                urls = [p + git_url for p in self.github_proxies] + [git_url]

            for url in urls:
                try:
                    pygit2.clone_repository(url, str(dir_path), depth=1, checkout_branch=branch)
                    BM_LOG.info(f"Git 克隆成功: {url[:60]}...")
                    return True
                except Exception as e:
                    BM_LOG.debug(f"克隆失败 ({url[:60]}...): {e}")
                    continue

            BM_LOG.error("所有代理尝试克隆都失败")
            return False

        except Exception as e:
            BM_LOG.error(f"下载脚本失败: {e}")
            if dir_path.exists():
                shutil.rmtree(dir_path, ignore_errors=True)
            return False
