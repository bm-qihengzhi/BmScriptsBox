"""
Copyright (c) 2026 綦恒智
Email: bmscriptsbox@163.com
SPDX-License-Identifier: AGPL-3.0
"""
import json
import shutil
import sys
from pathlib import Path
from typing import Optional, List, Dict, Any

from PySide2.QtCore import QObject, Signal

from app.servers.packages.download import XDownLoad
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

    def __init__(self):
        super().__init__()
        self.base_path = self._get_base_path()
        self.base_path.mkdir(parents=True, exist_ok=True)
        self.json_file = self.base_path / "BmPackage.json"

        # 内部状态
        self.downloader = None

    # --- 基础路径配置 ---

    def _get_base_path(self) -> Path:
        """统一管理软件包存储根目录"""
        return BmTools.get_root_path() / 'BmPackages'

    # --- 核心公开接口 ---

    def install_cli(self, package_name: str, version_requirement: str = '') -> str:
        """
        安装单个软件包（核心逻辑）
        """
        try:
            # 1. 本地查重
            local_data = self._read_manifest()
            matcher = VersionMatcher()
            local_res = matcher.find_best_local_version(local_data, package_name, version_requirement)

            if local_res.found:
                return str(local_res.path)

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
            bin_path = self._resolve_bin_path(extracted_path, payload.get('bin'))

            # 6. 处理静默安装 (EXE/MSI)
            if payload.get('silent_install'):
                bin_path = self._handle_silent_install(package_name, cloud_res.version, bin_path, payload)

            # 7. 环境变量与持久化
            if payload.get('env_set'):
                self._create_shim_exe(bin_path)
                self._emit_status("环境变量 Shim 重定向已创建")

            self._update_manifest(package_name, str(bin_path), cloud_res.version)

            # 8. 清理临时文件
            if Path(extracted_path).is_dir():
                self._safe_unlink(zip_path)

            self._emit_status(f"{package_name} 安装成功")
            return str(bin_path)

        except Exception as e:
            BM_LOG.error(f"安装 {package_name} 失败: {e}")
            raise RuntimeError(f"软件包 [{package_name}] 部署异常: {e}")

    def batch_install_cli(self, packages: List[Dict[str, str]]) -> List[str]:
        """批量安装接口"""
        if not packages: return []
        results = []
        for pkg in packages:
            path = self.install_cli(pkg.get('name'), pkg.get('version', ''))
            results.append(path)
        return results

    # --- 环境特定接口 (UV / Python / Node) ---

    def get_uv(self) -> str:
        """获取 uv 路径并确保配置了国内镜像源"""
        uv_path = self.install_cli('uv')
        # 确保项目根目录下有针对 uv 的配置
        root_toml = BmTools.get_root_path() / 'bmscripts' /'pyproject.toml'
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

    def _update_manifest(self, name: str, path: str, version: str):
        """原子化更新本地包索引"""
        data = self._read_manifest()
        if name not in data: data[name] = {"versions": {}}

        data[name]["versions"][version] = {"path": path}

        with open(self.json_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=4, ensure_ascii=False)

    def _resolve_bin_path(self, extract_dir: Path, bin_name: Optional[str]) -> Path:
        """智能定位执行文件"""
        if not bin_name: return extract_dir

        # 1. 直接匹配
        direct = extract_dir / bin_name
        if direct.exists(): return direct

        # 2. 递归查找
        for found in extract_dir.rglob(bin_name):
            if found.is_file(): return found

        return extract_dir  # 回退

    def _handle_silent_install(self, name: str, ver: str, installer_path: Path, payload: Dict) -> Path:
        """处理二进制静默安装流程"""
        self._emit_status(f"检测到安装程序，正在执行静默部署...")
        install_dir = self.base_path / "cli" / name / ver

        installer = SilentInstaller()
        success, final_path = installer.install_software(
            installer_path=str(installer_path),
            install_dir=str(install_dir),
            binary_name=payload.get('bin')
        )
        if not success:
            raise RuntimeError(f"静默安装失败: {name}")
        return Path(final_path)

    def _create_shim_exe(self, source_path: Path):
        """创建 Windows Shim (原生 exe 重定向)"""
        bin_dir = self.base_path / 'bin'
        bin_dir.mkdir(exist_ok=True)

        launcher = Path(__file__).parent / 'shim-launcher.exe'
        shim_path = bin_dir / f"{source_path.stem}.exe"
        shutil.copy(launcher, shim_path)

        target_path = bin_dir / f"{source_path.stem}.target"
        target_path.write_text(str(source_path.resolve()), encoding='utf-8')

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



if __name__ == '__main__':
    # # 添加sys.path
    # sys.path.insert(0, str(Path(__file__).parents[3]))
    # # 示例使用
    # packages_manager = PackagesManager()
    # packages_manager.packages_progress.connect(lambda x: print(x))
    # print(packages_manager.install_cli('pnpm'))
    root_toml = BmTools.get_root_path() / 'pyproject.toml'
    print(root_toml)

