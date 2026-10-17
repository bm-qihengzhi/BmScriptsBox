"""
Copyright (c) 2026 綦恒智
Email: bmscriptsbox@163.com
SPDX-License-Identifier: MIT
SPDX-License-Identifier: LicenseRef-Commons-Clause
"""
import json
import os
import re
import shutil
import sys
from pathlib import Path
from typing import List, Dict, Any

from PySide2.QtCore import QObject, Signal

from app.servers.packages.download import XDownLoad
from app.servers.packages.integrity import BinaryIntegrityStore, sha256_file
from app.servers.packages.match_version import VersionMatcher
from app.servers.packages.remote import RemoteManifestProvider
from app.servers.packages.silent import SilentInstaller
from app.servers.packages.unzip import ArchiveExtractor
from app.utils import BmTools, BM_LOG


class PackagesManager(QObject):
    """
    软件包基础设施管理器
    负责开源工具（uv, python, node等）的下载、安装、版本管理及环境补丁
    """
    packages_progress = Signal(dict)

    def __init__(self, consent_callback=None):
        super().__init__()
        self.base_path = self._get_base_path()
        self.base_path.mkdir(parents=True, exist_ok=True)
        self.json_file = BmTools.get_root_path() / "BmData" / "BmPackage.json"

        # 内部状态
        self.downloader = None
        # 直连二进制下载确认回调：callable(payload:dict) -> bool；缺省表示无确认界面（直连将失败）
        self._consent_callback = consent_callback

    # --- 基础路径配置 ---

    def _get_base_path(self) -> Path:
        """统一管理软件包存储根目录"""
        return BmTools.get_root_path() / 'BmPackages'

    # --- 核心公开接口 ---

    def install_cli(self, package_name: str, version_requirement: str = '',
                    env_set_override=None) -> str:
        """
        安装单个软件包（核心逻辑）
        env_set_override: 显式覆盖资源清单里的 env_set（None=用清单值），用于两模式统一。
        """
        try:
            # 1. 本地查重
            local_data = self._read_manifest()
            matcher = VersionMatcher()
            local_res = matcher.find_best_local_version(local_data, package_name, version_requirement)

            if local_res.found:
                if local_res.path and Path(local_res.path).exists():
                    return str(local_res.path)
                BM_LOG.warning(f"软件包 {package_name} 记录存在但文件已丢失，重新下载")

            # 2. 远程发现
            self._emit_status(f"正在从云端获取 {package_name} 清单...")
            remote_provider = RemoteManifestProvider()
            remote_data = remote_provider.get_package_manifest(package_name)

            cloud_res = matcher.fetch_best_cloud_version(remote_data, package_name, version_requirement)
            if not cloud_res.found:
                raise RuntimeError(f"未找到匹配的版本要求: {package_name} {version_requirement}")

            payload = cloud_res.payload
            self._emit_status("已获取最优下载连接")

            # 3. 下载流程
            download_dir = self.base_path / 'downloads'
            download_dir.mkdir(exist_ok=True)

            self.downloader = XDownLoad()
            self.downloader.download_progress.connect(self.packages_progress.emit)
            zip_path = self.downloader.download(payload.get('url'), download_dir,
                                                 cn_url=payload.get('url_cn'))

            # 4. 解压归档
            self._emit_status("正在解压归档文件...")
            extractor = ArchiveExtractor()
            extracted_path = Path(extractor.extract(zip_path))

            # 5. 定位执行文件
            bin_paths = self._resolve_bin_paths(extracted_path, payload.get('bin'))

            # 6. 处理静默安装 (EXE/MSI)
            if payload.get('silent_install'):
                bin_paths = self._handle_silent_install(package_name, cloud_res.version, bin_paths, payload)

            # 7. 环境变量与持久化
            effective_env_set = env_set_override if env_set_override is not None else payload.get('env_set')
            if effective_env_set:
                self._create_shim_exes(bin_paths, package_name)
                self._emit_status("环境变量 Shim 重定向已创建")

            self._update_manifest(package_name, bin_paths, cloud_res.version)

            # 8. 清理临时文件
            if Path(extracted_path).is_dir():
                self._safe_unlink(zip_path)

            self._emit_status(f"{package_name} 安装成功")
            return str(bin_paths[0])

        except Exception as e:
            BM_LOG.error(f"安装 {package_name} 失败: {e}")
            raise RuntimeError(f"软件包 [{package_name}] 部署异常: {e}")

    def batch_install_cli(self, packages: List, script_id: str = '') -> List[str]:
        """
        批量安装接口。逐条分发：
        - 官方清单模式（无 url）→ install_cli
        - 作者直连模式（有 url）→ install_binary
        任一失败向上抛出（由安装流程统一回滚）。
        """
        if not packages:
            return []
        results = []
        for pkg in packages:
            spec = pkg if isinstance(pkg, dict) else pkg.model_dump()
            if (spec.get('url') or '').strip():
                results.append(self.install_binary(spec, script_id))
            else:
                results.append(self.install_cli(spec.get('name'), spec.get('version', ''),
                                                env_set_override=spec.get('env_set')))
        return results

    # --- 直连二进制（作者自备 GitHub 链接）---

    def install_binary(self, spec: Dict[str, Any], script_id: str = '') -> str:
        """
        安装一个外部二进制声明。
        - 无 url → 走官方清单模式（install_cli）。
        - 有 url → 直连模式：解析 tag → 用户确认 → 下载 → sha256(显式/TOFU) → 解压或安装 → shim。
        """
        url = (spec.get('url') or '').strip()
        if not url:
            return self.install_cli(spec.get('name'), spec.get('version', ''))

        name = (spec.get('name') or '').strip()
        declared_sha = (spec.get('sha256') or '').strip().lower()
        bin_names = [b for b in (spec.get('bin') or []) if str(b).strip()]
        do_extract = bool(spec.get('extract', True))
        install_opts = spec.get('install') or None
        is_installer = self._looks_like_installer(url, install_opts)
        # 直连模式默认不进 PATH（env_set 未声明时按 False）；仍会注入参数文件供脚本取路径
        env_set = spec.get('env_set')
        if env_set is None:
            env_set = False

        try:
            # 1. 解析真实标签（/releases/latest/download/.. 会 302 到具体 tag）
            self._emit_status(f"正在校验外部二进制来源: {name}")
            tag = self._resolve_tag(url)

            # 2. 用户确认（可被信任表跳过）
            self._confirm_direct(name, url, tag, declared_sha, is_installer, script_id)

            # 3. 下载
            download_dir = self.base_path / 'downloads'
            download_dir.mkdir(parents=True, exist_ok=True)
            self.downloader = XDownLoad()
            self.downloader.download_progress.connect(self.packages_progress.emit)
            downloaded = Path(self.downloader.download(url, download_dir))

            # 4. 完整性校验：显式 sha256 优先，否则按 tag TOFU
            store = BinaryIntegrityStore()
            if declared_sha:
                if not XDownLoad.verify_sha256(downloaded, declared_sha):
                    actual = sha256_file(downloaded)
                    self._safe_unlink(downloaded)
                    raise RuntimeError(
                        f"二进制 {name} sha256 校验失败（声明={declared_sha}，实际={actual}）")
            else:
                actual = sha256_file(downloaded)
                strict = self._is_version_tag(tag)
                if not store.check_and_record_hash(name, tag, actual, strict=strict):
                    self._safe_unlink(downloaded)
                    raise RuntimeError(
                        f"二进制 {name} 完整性校验失败：tag={tag} 内容与首次记录不一致（疑似篡改）")

            # 5. 解压 / 静默安装 / 单文件
            bin_paths = self._materialize_binary(downloaded, name, tag, bin_names,
                                                 do_extract, is_installer, install_opts)

            # 6. 存在性校验
            missing = [str(p) for p in bin_paths if not Path(p).exists()]
            if missing:
                raise RuntimeError(f"二进制 {name} 未找到声明的可执行文件: {missing}")

            # 7. shim + 清单
            if env_set:
                self._create_shim_exes(bin_paths, name)
                self._emit_status("环境变量 Shim 重定向已创建")
            self._update_manifest(name, bin_paths, tag)
            self._emit_status(f"{name} 部署成功（{tag}）")
            return str(bin_paths[0])

        except Exception as e:
            BM_LOG.error(f"安装直连二进制 {name} 失败: {e}")
            if isinstance(e, RuntimeError):
                raise
            raise RuntimeError(f"外部二进制 [{name}] 部署异常: {e}")

    def _materialize_binary(self, downloaded: Path, name: str, tag: str, bin_names: List[str],
                            do_extract: bool, is_installer: bool, install_opts) -> List[Path]:
        """把下载产物变成可暴露的可执行文件列表（解压 / 静默安装 / 直接使用）"""
        if is_installer and not do_extract:
            if not bin_names:
                raise RuntimeError(f"二进制 {name} 为安装程序，必须声明 bin（可执行文件名）")
            self._emit_status(f"检测到安装程序，正在执行静默部署: {name}")
            install_dir = self.base_path / 'cli' / name / tag
            installer = SilentInstaller()
            ok, _ = installer.install_software(
                installer_path=str(downloaded),
                install_dir=str(install_dir),
                binary_name=bin_names,
                silent_params=install_opts)
            if not ok:
                raise RuntimeError(f"二进制 {name} 静默安装失败")
            self._safe_unlink(downloaded)
            return [Path(install_dir) / bn for bn in bin_names]

        if do_extract:
            self._emit_status("正在解压外部二进制归档...")
            extracted = Path(ArchiveExtractor().extract(downloaded))
            if extracted.is_dir() and not bin_names:
                bin_names = [f"{name}.exe"]
            paths = self._resolve_bin_paths(extracted, bin_names)
            # 归档已解压，删除压缩包节省空间；若产物即下载文件本身（exe/msi 直通）则保留
            try:
                if extracted.resolve() != downloaded.resolve():
                    self._safe_unlink(downloaded)
            except OSError:
                pass
            return paths

        # 单文件：直接暴露下载产物自身
        return self._resolve_bin_paths(downloaded, bin_names)

    @staticmethod
    def _looks_like_installer(url: str, install_opts) -> bool:
        if install_opts:
            return True
        clean = url.split('?')[0].split('#')[0].lower()
        return clean.endswith('.exe') or clean.endswith('.msi')

    @staticmethod
    def _is_version_tag(tag: str) -> bool:
        """版本型 tag（v1 / 2 / v6.1.0）→ 严格校验；latest/nightly 等滚动 tag → 放宽"""
        return bool(re.match(r'^v?\d', (tag or '').strip()))

    def _resolve_tag(self, url: str) -> str:
        """跟随重定向解析 release tag（/releases/download/<tag>/）；失败回退 'latest'"""
        try:
            import requests
            resp = requests.get(
                url, allow_redirects=True, stream=True, timeout=(5, 15),
                headers={'User-Agent': 'Mozilla/5.0'})
            candidates = [resp.url] + [h.url for h in getattr(resp, 'history', [])]
            resp.close()
            for u in candidates:
                m = re.search(r'/releases/download/([^/]+)/', u or '')
                if m:
                    return m.group(1)
        except Exception as e:
            BM_LOG.debug(f"[直连] 解析 tag 失败，回退 latest: {e}")
        return 'latest'

    def _confirm_direct(self, name: str, url: str, tag: str, declared_sha: str,
                        is_installer: bool, script_id: str):
        """直连下载前的用户确认；命中信任表则跳过；被拒则抛错终止安装"""
        store = BinaryIntegrityStore()
        if store.is_trusted(script_id, url):
            return
        if not self._consent_callback:
            raise RuntimeError(
                f"外部二进制 {name} 需要用户确认，但当前无确认界面，已终止安装")
        payload = {
            'name': name,
            'url': url,
            'tag': tag,
            'sha256': declared_sha or '',
            'is_installer': is_installer,
            'script_id': script_id,
        }
        if not self._consent_callback(payload):
            raise RuntimeError(f"用户拒绝下载外部二进制 {name}，安装已终止")


    # --- 环境特定接口 (UV / Python / Node) ---

    def get_uv(self) -> str:
        """获取 uv 路径并确保配置了国内镜像源"""
        uv_path = self.install_cli('uv')
        # 确保脚本根目录下有针对 uv 的配置（路径与 BmScripts 保持一致，避免大小写分裂）
        root_toml = BmTools.get_base_scripts_path() / 'pyproject.toml'
        if not root_toml.exists():
            self._create_uv_config(root_toml)
            self._emit_status("UV 国内加速镜像配置完成")
        return uv_path

    def get_python(self, version_requirement: str) -> str:
        """获取 Python 路径并自动修复 Tkinter 缺失问题"""
        matcher = VersionMatcher()
        local_data = self._read_manifest()

        # 尝试本地匹配
        res = matcher.find_best_local_version(local_data, 'python', version_requirement)
        if res.found:
            return str(res.path)

        # 远程下载 Python
        py_path = self.install_cli('python', version_requirement)
        py_ver = matcher.find_best_local_version(self._read_manifest(), 'python', version_requirement).version

        # 关联下载 Tkinter 并覆盖补丁
        self._emit_status("正在为 Python 环境应用 Tkinter 补丁...")
        tk_path = self.install_cli('tkinter', f">={py_ver}")
        self.copy_contents(tk_path, str(Path(py_path).parent))

        self._emit_status("Python GUI 环境配置完成")
        return py_path

    # --- 内部辅助方法 ---

    def _read_manifest(self) -> Dict:
        """安全读取本地包索引 JSON"""
        if not self.json_file.exists(): return {}
        try:
            with open(self.json_file, 'r', encoding='utf-8') as f:
                return json.load(f) or {}
        except Exception:
            return {}

    def _update_manifest(self, name: str, paths: List[Path], version: str):
        """原子化更新本地包索引"""
        data = self._read_manifest()
        if name not in data: data[name] = {"versions": {}}

        data[name]["versions"][version] = {
            "path": str(paths[0]),
            "paths": [str(p) for p in paths]
        }

        self._write_manifest_atomic(data)

    def downloads_path(self) -> Path:
        return self.base_path / 'downloads'

    def bin_path(self) -> Path:
        return self.base_path / 'bin'

    def iter_installed(self) -> Dict:
        """返回本地清单副本 {name: {versions: {...}}}"""
        return self._read_manifest()

    def find_installed(self, package_name: str, version_requirement: str = ''):
        """只读查询本地清单匹配到的 (version, path)；不触发任何下载"""
        res = VersionMatcher().find_best_local_version(
            self._read_manifest(), package_name, version_requirement)
        if res.found:
            return res.version, res.path
        return None

    def installed_paths(self, package_name: str, version_requirement: str = '') -> List[str]:
        """返回匹配版本的全部可执行文件绝对路径；未安装返回 []（供启动时注入参数文件）。
        直连模式的版本键是 GitHub tag（如 latest / jq-1.8.2），非 PEP440，故语义化匹配失败时回退。"""
        if not package_name:
            return []
        data = self._read_manifest()
        entry = data.get(package_name)
        if not entry:
            return []
        versions = entry.get('versions', {}) or {}

        # 1) 官方模式：语义化版本约束匹配
        res = VersionMatcher().find_best_local_version(data, package_name, version_requirement)
        if res.found and res.version in versions:
            return self._version_paths(versions[res.version])

        # 2) 直连模式：tag 不是合法版本号
        req = (version_requirement or '').strip()
        if req and req in versions:          # 声明里写了精确 tag
            return self._version_paths(versions[req])
        if versions:                          # 否则取最近安装的那条（与按名 last-wins 一致）
            return self._version_paths(versions[list(versions.keys())[-1]])
        return []

    @staticmethod
    def _version_paths(info) -> List[str]:
        """从某版本的清单记录里取全部可执行文件路径"""
        if not isinstance(info, dict):
            return []
        paths = info.get('paths') or ([info.get('path')] if info.get('path') else [])
        return [str(p) for p in paths if p]

    def _write_manifest_atomic(self, data: Dict):
        self.json_file.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.json_file.with_suffix('.json.tmp')
        with open(tmp, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=4, ensure_ascii=False)
        os.replace(tmp, self.json_file)

    def remove_manifest_entries(self, removals: Dict[str, list]):
        """按 {name: [要删除的版本...]} 清理清单；某 name 版本删空则删 name。"""
        if not removals:
            return
        data = self._read_manifest()
        changed = False
        for name, versions in removals.items():
            entry = data.get(name)
            if not entry:
                continue
            vers = entry.get('versions', {})
            for v in versions:
                if v in vers:
                    del vers[v]
                    changed = True
            if not vers:
                del data[name]
                changed = True
        if changed:
            self._write_manifest_atomic(data)

    def _resolve_bin_paths(self, extract_dir: Path, bin_names: List[str]) -> List[Path]:
        """智能定位执行文件列表，支持多二进制"""
        if not bin_names:
            return [extract_dir]

        # 单文件下载（.exe/.msi 等非压缩包）：直接匹配文件名
        if extract_dir.is_file():
            for bin_name in bin_names:
                if extract_dir.name == bin_name:
                    return [extract_dir]
            return [extract_dir]

        results = []
        for bin_name in bin_names:
            # 1. 直接匹配
            direct = extract_dir / bin_name
            if direct.exists():
                results.append(direct)
                continue

            # 2. 递归查找
            found = False
            for found_path in extract_dir.rglob(bin_name):
                if found_path.is_file():
                    results.append(found_path)
                    found = True
                    break

            if not found:
                results.append(extract_dir / bin_name)  # 回退

        return results

    def _handle_silent_install(self, name: str, ver: str, installer_paths: List[Path], payload: Dict) -> List[Path]:
        """处理二进制静默安装流程，支持多二进制输出"""
        self._emit_status(f"检测到安装程序，正在执行静默部署...")
        install_dir = self.base_path / "cli" / name / ver

        installer = SilentInstaller()
        success, _ = installer.install_software(
            installer_path=str(installer_paths[0]),
            install_dir=str(install_dir),
            binary_name=payload.get('bin')
        )
        if not success:
            raise RuntimeError(f"静默安装失败: {name}")
        return [Path(install_dir) / bn for bn in payload.get('bin')]

    def _create_shim_exes(self, source_paths: List[Path], package_name: str):
        """创建 Windows Shim (原生 exe 重定向)，支持多二进制"""
        bin_dir = self.base_path / 'bin'
        bin_dir.mkdir(exist_ok=True)

        launcher = Path(__file__).parent / 'shim-launcher.exe'
        for source_path in source_paths:
            resolved = source_path.resolve()
            shim_name = package_name if len(source_paths) == 1 else resolved.stem
            shim_path = bin_dir / f"{shim_name}.exe"
            shutil.copy(launcher, shim_path)

            target_path = bin_dir / f"{shim_name}.target"
            target_path.write_text(str(resolved), encoding='utf-8')

    def _create_uv_config(self, toml_path: Path):
        """生成 UV 配置文件并注入加速源"""
        cache_path = (self.base_path / 'BmCache' / 'python').as_posix()
        content = (
            f'[tool.uv]\n'
            f'link-mode = "hardlink"\n'
            f'cache-dir = "{cache_path}"\n\n'
            f'[[tool.uv.index]]\n'
            f'url = "https://pypi.tuna.tsinghua.edu.cn/simple"\n'
            f'default = true\n'
        )
        toml_path.write_text(content, encoding='utf-8')

    def copy_contents(self, src: str, dst: str):
        """通用目录覆盖拷贝"""
        src_p, dst_p = Path(src), Path(dst)
        dst_p.mkdir(parents=True, exist_ok=True)

        for item in src_p.iterdir():
            target = dst_p / item.name
            if item.is_dir():
                shutil.copytree(item, target, dirs_exist_ok=True)
            else:
                shutil.copy2(item, target)

    def _safe_unlink(self, path: Any):
        """安全删除文件，不抛出异常"""
        try:
            p = Path(path)
            if p.exists(): p.unlink()
        except OSError as e:
            BM_LOG.warning(f"删除文件失败: {e}")

    def _emit_status(self, msg: str):
        """统一进度信号发射"""
        self.packages_progress.emit({'status': True, 'msg': msg})




