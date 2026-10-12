"""
Copyright (c) 2026 綦恒智
Email: bmscriptsbox@163.com
SPDX-License-Identifier: MIT
SPDX-License-Identifier: LicenseRef-Commons-Clause

资源清理（GC）：删除没有任何已安装脚本引用的二进制包与模型，并 prune uv/pnpm 缓存。
判定"引用集"来自数据库 app_scripts 的 binaries / models_schema；
清单文件 BmPackage.json / BmModels.json 与文件系统成对清理（先删实体，成功后再改清单）。
"""
import os
import subprocess
from pathlib import Path

from app.utils import BmTools, BM_LOG
from app.servers.packages import PackagesManager
from app.servers.packages.match_version import VersionMatcher
from app.servers.models.model_manager import ModelManager

# 盒子自带工具，永不清理（与 PackagesManager 安装名对应，小写比较）
CORE_WHITELIST = {'uv', 'python', 'tkinter', 'pwsh', 'node', 'pnpm', 'webview-cli',
                  'webview_cli'}

_CREATE_NO_WINDOW = getattr(subprocess, 'CREATE_NO_WINDOW', 0)


def _path_size(p: Path) -> int:
    try:
        if not p.exists():
            return 0
        if p.is_file():
            return p.stat().st_size
    except OSError:
        return 0
    total = 0
    for root, _dirs, files in os.walk(p):
        for name in files:
            try:
                total += os.path.getsize(os.path.join(root, name))
            except OSError:
                pass
    return total


def _is_under(path: Path, root: Path) -> bool:
    try:
        path = path.resolve()
        root = root.resolve()
    except OSError:
        return False
    if path == root:
        return True
    try:
        path.relative_to(root)
        return True
    except ValueError:
        return False


class ResourceCleaner:
    """扫描并清理无用的共享资源（二进制/模型）与缓存"""

    def __init__(self):
        self.packages = PackagesManager()
        self.models = ModelManager()

    # --- 引用集 ---

    def _collect_refs(self):
        """返回 (bin_refs: {name_lower: [version_req,...]}, model_ids: set)"""
        bin_refs = {}
        model_ids = set()
        try:
            scripts = self._all_scripts()
        except Exception as e:
            BM_LOG.error(f"[GC] 读取脚本列表失败: {e}")
            scripts = []
        for s in scripts:
            for b in (getattr(s, 'binaries', None) or []):
                if not isinstance(b, dict):
                    continue
                name = (b.get('name') or '').strip().lower()
                if name:
                    bin_refs.setdefault(name, []).append((b.get('version') or '').strip())
            for m in (getattr(s, 'models_schema', None) or []):
                if isinstance(m, dict) and m.get('repo_id'):
                    model_ids.add(m['repo_id'])
        return bin_refs, model_ids

    @staticmethod
    def _all_scripts():
        from app.data import ScriptDatabase
        return ScriptDatabase().get_all_scripts()

    # --- 计划构建 ---

    def _version_roots(self, info: dict, downloads: Path):
        """由包版本记录的 paths 反推删除目标（单文件或其顶层目录）"""
        roots = set()
        paths = info.get('paths') or ([info.get('path')] if info.get('path') else [])
        for p in paths:
            if not p:
                continue
            pth = Path(p)
            try:
                rel = pth.relative_to(downloads)
            except ValueError:
                continue
            if len(rel.parts) == 1:
                roots.add(pth)                      # 直接位于 downloads 下的单文件
            else:
                roots.add(downloads / rel.parts[0])  # 顶层包目录
        return roots

    def _plan_binaries(self, bin_refs):
        data = self.packages.iter_installed()
        downloads = self.packages.downloads_path()
        delete_versions = {}   # manifest name -> [versions 待删]
        delete_roots = set()
        keep_roots = set()

        for name, entry in data.items():
            versions = entry.get('versions', {}) or {}
            lname = name.lower()

            if lname in CORE_WHITELIST:
                for v in versions.values():
                    keep_roots |= self._version_roots(v, downloads)
                continue

            if lname not in bin_refs:
                target = list(versions.keys())
            else:
                keep = set()
                for req in bin_refs[lname]:
                    if not req:
                        keep = set(versions.keys())  # 无版本约束 → 全留
                        break
                    res = VersionMatcher().find_best_local_version(data, name, req)
                    if res.found:
                        keep.add(res.version)
                if not keep:
                    keep = set(versions.keys())      # 匹配不到 → 保守全留
                target = [v for v in versions if v not in keep]
                for v in keep:
                    keep_roots |= self._version_roots(versions[v], downloads)

            if target:
                delete_versions[name] = target
                for v in target:
                    delete_roots |= self._version_roots(versions[v], downloads)

        delete_roots -= keep_roots
        return {'versions': delete_versions, 'roots': delete_roots, 'keep_roots': keep_roots}

    def _plan_models(self, model_ids):
        data = self.models.iter_installed()
        repo_ids = [rid for rid in data.keys() if rid not in model_ids]
        return {'repo_ids': repo_ids}

    # --- 扫描（预览）---

    def scan(self) -> dict:
        bin_refs, model_ids = self._collect_refs()

        plan_b = self._plan_binaries(bin_refs)
        bin_bytes = sum(_path_size(r) for r in plan_b['roots'])
        bin_names = sorted(plan_b['versions'].keys())

        plan_m = self._plan_models(model_ids)
        model_bytes = sum(_path_size(self.models.base_path / rid) for rid in plan_m['repo_ids'])

        uv_ok = self.packages.find_installed('uv') is not None
        pnpm_ok = self.packages.find_installed('pnpm') is not None

        # 缓存只 prune（未引用项），无法预先准确估算释放量，故不计入「可释放」
        return {
            'binaries': {'names': bin_names, 'bytes': bin_bytes},
            'models': {'repo_ids': plan_m['repo_ids'], 'bytes': model_bytes},
            'caches': {'uv': uv_ok, 'pnpm': pnpm_ok},
            'total_bytes': bin_bytes + model_bytes,
        }

    # --- 执行清理 ---

    def clean(self) -> dict:
        bin_refs, model_ids = self._collect_refs()
        freed = 0
        failures = []
        removed = {'binaries': [], 'models': [], 'shims': []}

        # 1) 二进制实体
        plan_b = self._plan_binaries(bin_refs)
        downloads = self.packages.downloads_path()
        deleted_roots = []
        for root in sorted(plan_b['roots'], key=lambda p: len(str(p)), reverse=True):
            size = _path_size(root)
            ok = self._delete(root)
            if ok:
                freed += size
                deleted_roots.append(root)
                removed['binaries'].append(str(root))
            else:
                failures.append(str(root))

        # 2) 清单同步（仅移除实体确已消失的版本）
        removals = {}
        for name, versions in plan_b['versions'].items():
            gone = []
            entry_versions = self.packages.iter_installed().get(name, {}).get('versions', {})
            for v in versions:
                roots = self._version_roots(entry_versions.get(v, {}), downloads)
                if roots and all(not r.exists() for r in roots):
                    gone.append(v)
                elif not roots:
                    gone.append(v)  # 无路径信息，跟随 name 删除
            if gone:
                removals[name] = gone
        self.packages.remove_manifest_entries(removals)

        # 3) shim 清理（按 .target 内指向的真实路径判断归属）
        for shim_target in list(self.packages.bin_path().glob('*.target')):
            try:
                pointed = Path(shim_target.read_text(encoding='utf-8').strip())
            except Exception:
                continue
            if any(_is_under(pointed, r) for r in deleted_roots):
                self._remove_shim(shim_target, removed, failures)

        # 4) 模型
        plan_m = self._plan_models(model_ids)
        for repo_id in plan_m['repo_ids']:
            p = self.models.base_path / repo_id
            size = _path_size(p)
            ok = self._delete(p)
            if ok:
                freed += size
                self.models.remove_manifest_entry(repo_id)
                removed['models'].append(repo_id)
                self._prune_empty_owner(p)
            else:
                failures.append(str(p))

        # 5) 缓存 prune（以 prune 前后目录大小之差计真实回收）
        cache_results, cache_freed = self._prune_caches()
        freed += cache_freed

        return {'freed_bytes': freed, 'removed': removed,
                'failures': failures, 'caches': cache_results}

    # --- 辅助 ---

    def _delete(self, path: Path) -> bool:
        try:
            if not path.exists():
                return True
            if path.is_dir():
                return BmTools.remove_dir(path)
            path.unlink()
            return not path.exists()
        except Exception as e:
            BM_LOG.warning(f"[GC] 删除失败 {path}: {e}")
            return False

    def _remove_shim(self, target_file: Path, removed: dict, failures: list):
        try:
            exe = target_file.with_suffix('.exe')
            ok = True
            if exe.exists():
                ok = self._delete(exe)
            if target_file.exists():
                ok = self._delete(target_file) and ok
            if ok:
                removed['shims'].append(str(exe))
            else:
                failures.append(str(exe))
        except Exception as e:
            BM_LOG.warning(f"[GC] 清理 shim 失败 {target_file}: {e}")
            failures.append(str(target_file))

    def _prune_empty_owner(self, deleted_path: Path):
        """模型按 owner/repo 两级存储，owner 目录空则一并移除"""
        try:
            parent = deleted_path.parent
            base = self.models.base_path
            if parent != base and parent.exists() and not any(parent.iterdir()):
                parent.rmdir()
        except Exception:
            pass

    def _prune_caches(self):
        """执行 uv/pnpm 缓存 prune，返回 (results, freed_bytes)。

        缓存目录 prune 后仍保留大部分内容，释放量无法预估，只能以 prune 前后
        目录大小之差作为实际回收量。
        """
        results = []
        freed = 0
        cache_root = BmTools.get_root_path() / 'BmPackages' / 'BmCache'

        uv = self.packages.find_installed('uv')
        if uv:
            cache_dir = cache_root / 'python'
            before = _path_size(cache_dir)
            try:
                r = subprocess.run(
                    [uv[1], '--cache-dir', str(cache_dir), 'cache', 'prune'],
                    capture_output=True, text=True, timeout=300,
                    creationflags=_CREATE_NO_WINDOW,
                )
                freed += max(0, before - _path_size(cache_dir))
                results.append({'name': 'uv', 'ok': r.returncode == 0,
                                'msg': (r.stderr or r.stdout or '').strip()})
            except Exception as e:
                results.append({'name': 'uv', 'ok': False, 'msg': str(e)})

        pnpm = self.packages.find_installed('pnpm')
        if pnpm:
            node_dir = cache_root / 'node'
            store_dir = node_dir / 'pnpm-store'
            before = _path_size(node_dir)
            env = os.environ.copy()
            env['npm_config_store_dir'] = str(store_dir)
            try:
                r = subprocess.run(
                    [pnpm[1], 'store', 'prune'],
                    capture_output=True, text=True, timeout=600, env=env,
                    creationflags=_CREATE_NO_WINDOW,
                )
                freed += max(0, before - _path_size(node_dir))
                results.append({'name': 'pnpm', 'ok': r.returncode == 0,
                                'msg': (r.stderr or r.stdout or '').strip()})
            except Exception as e:
                results.append({'name': 'pnpm', 'ok': False, 'msg': str(e)})

        return results, freed
