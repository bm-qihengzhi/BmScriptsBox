"""
Copyright (c) 2026 綦恒智
Email: bmscriptsbox@163.com
SPDX-License-Identifier: AGPL-3.0
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


class ArchiveExtractor:
    """
    通用解压工具类(可传7zr.exe路径进来。如果没有传会在同目录下寻找)
    """

    TAR_EXTENSIONS = ('.tar', '.tar.gz', '.tgz', '.tar.bz2', '.tbz2', '.tar.xz', '.txz')
    STANDARD_EXTENSIONS = {'.zip': 'ZIP', '.7z': '7Z', '.gz': 'GZIP', '.bz2': 'BZIP2'}

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
                print('文件后缀为.exe')
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
                shutil.rmtree(target_path, ignore_errors=True)
            raise RuntimeError(f"解压失败: {str(e)}")

    # --- 具体的解压执行逻辑 ---

    def _run_external_7z_extraction(self, source: Path, destination: Path):
        """调用外部 7z 工具进行解压"""
        subprocess.run(
            [self.tool_path, "x", str(source), f"-o{destination}", "-y"],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
            timeout=300, check=True,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
        )

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

    @staticmethod
    def _run_zip_extraction(source: Path, destination: Path):
        with zipfile.ZipFile(source, 'r') as ref:
            ref.extractall(destination)

    @staticmethod
    def _run_tar_extraction(source: Path, destination: Path):
        with tarfile.open(source, 'r:*') as ref:
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


if __name__ == '__main__':
    print(Path(__file__).parent / '7zr.exe')  # 保持原样，同目录引用 PyInstaller 也兼容

    # tool = r'D:\PythonCode\BmScriptsBox-Code\app\utils\packages\7zr.exe'
    # archive = r"D:\PythonCode\BmScriptsBox-Code\app\utils\packages\7zr.exe"
    #
    # extractor = ArchiveExtractor()
    # result = extractor.extract(source_file=archive, remove_source=False)
    # print(result)