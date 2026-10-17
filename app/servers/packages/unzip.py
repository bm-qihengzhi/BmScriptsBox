"""
Copyright (c) 2026 綦恒智
Email: bmscriptsbox@163.com
SPDX-License-Identifier: MIT
SPDX-License-Identifier: LicenseRef-Commons-Clause
"""
import bz2
import gzip
import os
import shutil
import subprocess
import tarfile
import zipfile
from pathlib import Path
from typing import Union, Optional, List

from app.utils import BmTools


class ArchiveExtractor:
    """
    通用解压工具类(可传7zr.exe路径进来。如果没有传会在同目录下寻找)
    """

    TAR_EXTENSIONS = ('.tar', '.tar.gz', '.tgz', '.tar.bz2', '.tbz2', '.tar.xz', '.txz')
    STANDARD_EXTENSIONS = {'.zip': 'ZIP', '.7z': '7Z', '.gz': 'GZIP', '.bz2': 'BZIP2'}

    # 解压安全上限：条目数与总解压体积（防路径穿越/解压炸弹）
    MAX_ENTRIES = 200000
    MAX_TOTAL_SIZE = 8 * 1024 ** 3  # 8GB

    # 7z 归档头块可能出现的格式类型（用于跳过头部条目）
    _7Z_CONTAINER_TYPES = {
        '7z', 'zip', 'tar', 'gzip', 'bzip2', 'rar', 'cab', 'xar', 'wim', 'iso', 'compound',
    }

    def __init__(self, tool_executable_path: Optional[Union[str, Path]] = None):
        """
        :param tool_executable_path: 外部解压工具(如 7zr.exe)的路径
        """
        self._tool_path = tool_executable_path

    @property
    def tool_path(self) -> str:
        """获取并校验外部解压工具路径"""
        path = self._tool_path or Path(__file__).parent / '7zr.exe'
        if not path:
            raise RuntimeError("未配置7zr解压工具路径！")

        path_obj = Path(path)
        if not path_obj.exists():
            raise FileNotFoundError(f"找不到7zr工具程序: {path}")

        return str(path_obj.resolve())

    @classmethod
    def get_supported_extensions(cls) -> List[str]:
        return list(cls.TAR_EXTENSIONS) + list(cls.STANDARD_EXTENSIONS.keys())

    @classmethod
    def _strip_extensions(cls, file_path: Path) -> str:
        """移除复杂的文件名后缀 (如: data.tar.gz -> data)"""
        filename = file_path.name
        # 按长度排序确保优先匹配长后缀
        all_exts = sorted(cls.get_supported_extensions(), key=len, reverse=True)
        for ext in all_exts:
            if filename.lower().endswith(ext):
                return filename[:-len(ext)]
        return file_path.stem

    def extract(self, source_file: Union[str, Path],
                target_dir: Optional[Union[str, Path]] = None,
                remove_source: bool = False) -> str:
        """
        执行解压任务
        :param source_file: 待解压的文件路径
        :param target_dir: 解压后的保存目录
        :param remove_source: 解压成功后是否删除压缩包
        """
        source_path = Path(source_file)
        if not source_path.exists():
            raise FileNotFoundError(f"文件不存在: {source_path}")

        # 如果未指定目录，则在同级目录下创建与文件名相同的文件夹
        if target_dir is None:
            target_path = source_path.parent / self._strip_extensions(source_path)
        else:
            target_path = Path(target_dir)

        target_path.mkdir(parents=True, exist_ok=True)
        file_ext_lower = str(source_path).lower()

        try:
            # 根据后缀分发到不同的解压逻辑
            if file_ext_lower.endswith(self.TAR_EXTENSIONS):
                self._run_tar_extraction(source_path, target_path)
            elif file_ext_lower.endswith('.zip'):
                self._run_zip_extraction(source_path, target_path)
            elif file_ext_lower.endswith('.7z'):
                self._run_external_7z_extraction(source_path, target_path)
            elif file_ext_lower.endswith('.gz'):
                self._run_single_gzip_extraction(source_path, target_path)
            elif file_ext_lower.endswith('.bz2'):
                self._run_single_bzip2_extraction(source_path, target_path)
            elif file_ext_lower.endswith('.exe'):
                target_path.rmdir()
                return source_file
            elif file_ext_lower.endswith('.msi'):
                target_path.rmdir()
                return source_file

            else:
                raise ValueError(f"不支持的压缩格式: {source_path.suffix}")

            if remove_source:
                source_path.unlink(missing_ok=True)

            return str(target_path.resolve())

        except Exception as e:
            # 失败清理：如果产生了文件夹但解压中断，则清理掉
            if target_path.exists() and any(target_path.iterdir()):
                BmTools.remove_dir(target_path)
            raise RuntimeError(f"解压失败: {str(e)}")

    # --- 具体的解压执行逻辑 ---

    def _run_external_7z_extraction(self, source: Path, destination: Path):
        """调用外部 7z 工具进行解压（解压前先校验内部条目路径，防路径穿越）"""
        self._validate_7z_entries(source, destination)
        subprocess.run(
            [self.tool_path, "x", str(source), f"-o{destination}", "-y"],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
            timeout=300, check=True,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
        )

    def _validate_7z_entries(self, source: Path, destination: Path):
        """列出 7z 内部条目并校验路径合法性；列目录失败时放行（不阻断安装）"""
        try:
            result = subprocess.run(
                [self.tool_path, "l", "-slt", str(source)],
                stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
                encoding='utf-8', errors='replace', timeout=120,
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)
        except Exception as e:
            from app.utils import BM_LOG
            BM_LOG.warning(f"7z 条目列表获取失败，跳过路径校验: {e}")
            return

        base = Path(destination).resolve()
        for block in result.stdout.split('\n\n')[1:]:  # 跳过归档头块
            name = None
            ftype = None
            for line in block.splitlines():
                if line.startswith('Path = '):
                    name = line[len('Path = '):]
                elif line.startswith('Type = '):
                    ftype = line[len('Type = '):].strip()
            if not name or ftype in self._7Z_CONTAINER_TYPES:
                continue
            if not self._is_safe_member(base, name):
                raise RuntimeError(f"压缩包内存在非法路径，已中止: {name}")

    def extract_and_overwrite(self, source: Union[str, Path], working_dir: Union[str, Path]):
        """强制覆盖解压 (常用于增量更新)"""
        source_path = Path(source)
        work_path = Path(working_dir)
        work_path.mkdir(parents=True, exist_ok=True)

        subprocess.run(
            [self.tool_path, "x", str(source_path), "-y", "-aoa"],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
            timeout=300, cwd=str(work_path), check=True,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
        )
        source_path.unlink(missing_ok=True)

    # --- 安全校验 ---

    @staticmethod
    def _is_safe_member(base: Path, name: str) -> bool:
        """校验压缩包成员路径不会逃逸出目标目录（拒绝绝对路径 / 盘符 / .. 穿越）"""
        if not name:
            return True
        norm = name.replace('\\', '/')
        if norm.startswith('/') or (len(norm) > 1 and norm[1] == ':'):
            return False
        try:
            (base / norm).resolve().relative_to(base)
            return True
        except (ValueError, OSError):
            return False

    @classmethod
    def _run_zip_extraction(cls, source: Path, destination: Path):
        base = Path(destination).resolve()
        with zipfile.ZipFile(source, 'r') as ref:
            infos = ref.infolist()
            if len(infos) > cls.MAX_ENTRIES:
                raise RuntimeError(f"压缩包条目过多（{len(infos)}），已中止")
            total = sum(i.file_size for i in infos)
            if total > cls.MAX_TOTAL_SIZE:
                raise RuntimeError(f"压缩包解压体积过大（{total} 字节），已中止")
            for info in infos:
                if not cls._is_safe_member(base, info.filename):
                    raise RuntimeError(f"压缩包内存在非法路径，已中止: {info.filename}")
            ref.extractall(destination)

    @classmethod
    def _run_tar_extraction(cls, source: Path, destination: Path):
        base = Path(destination).resolve()
        with tarfile.open(source, 'r:*') as ref:
            members = ref.getmembers()
            if len(members) > cls.MAX_ENTRIES:
                raise RuntimeError(f"压缩包条目过多（{len(members)}），已中止")
            total = sum(m.size for m in members if m.isfile())
            if total > cls.MAX_TOTAL_SIZE:
                raise RuntimeError(f"压缩包解压体积过大（{total} 字节），已中止")
            for m in members:
                if not cls._is_safe_member(base, m.name):
                    raise RuntimeError(f"压缩包内存在非法路径，已中止: {m.name}")
                if (m.issym() or m.islnk()) and not cls._is_safe_member(base, m.linkname):
                    raise RuntimeError(
                        f"压缩包内含越界链接，已中止: {m.name} -> {m.linkname}")
            try:
                ref.extractall(destination, filter='data')  # Python >= 3.12
            except TypeError:
                ref.extractall(destination)

    @staticmethod
    def _run_single_gzip_extraction(source: Path, destination: Path):
        # gzip 压缩单个文件的情况
        output_file = destination / source.stem
        with gzip.open(source, 'rb') as f_in, open(output_file, 'wb') as f_out:
            shutil.copyfileobj(f_in, f_out)

    @staticmethod
    def _run_single_bzip2_extraction(source: Path, destination: Path):
        output_file = destination / source.stem
        with bz2.open(source, 'rb') as f_in, open(output_file, 'wb') as f_out:
            shutil.copyfileobj(f_in, f_out)


