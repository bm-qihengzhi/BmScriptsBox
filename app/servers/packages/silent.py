"""
Copyright (c) 2026 綦恒智
Email: bmscriptsbox@163.com
SPDX-License-Identifier: AGPL-3.0
"""
import os
import subprocess
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional, Any

from PySide2.QtCore import QObject, Signal


class InstallationStatus(Enum):
    """安装状态枚举"""
    PENDING = "pending"
    DOWNLOADING = "downloading"
    INSTALLING = "installing"
    SUCCESS = "success"
    FAILED = "failed"
    CANCELLED = "cancelled"


class SilentInstaller(QObject):
    """
    静默安装器 - 支持各种软件的静默安装
    """
    # 信号定义
    progress_signal = Signal(str)  # 进度更新信号
    status_signal = Signal(str)    # 状态更新信号
    log_signal = Signal(str)       # 日志信号

    def __init__(self):
        super().__init__()
        self._cancelled = False

    def cancel_installation(self):
        """取消当前安装"""
        self._cancelled = True
        self.status_signal.emit("cancelled")

    def install_software(self, installer_path: str, install_dir: str, binary_name: str,
                        silent_params: Optional[Dict[str, Any]] = None,
                        installer_type: Optional[str] = None,) -> tuple:
        """
        静默安装软件

        Args:
            installer_path: 安装包路径
            install_dir: 安装目标目录
            binary_name: 期望存在的可执行文件名
            silent_params: 静默安装参数字典
            installer_type: 安装包类型 (exe, msi, zip等)，如果为None则自动检测

        Returns:
            tuple: (是否成功, 可执行文件完整路径)
        """
        self._cancelled = False
        try:
            # 检测安装包类型
            if installer_type is None:
                installer_type = self._detect_installer_type(installer_path)
            
            self.log_signal.emit(f"检测到安装包类型: {installer_type}")
            
            # 根据类型选择安装方法
            if installer_type == 'msi':
                return self._install_msi(installer_path, install_dir, binary_name, silent_params)
            elif installer_type == 'exe':
                return self._install_exe(installer_path, install_dir, binary_name, silent_params)
            else:
                self.log_signal.emit(f"不支持的安装包类型: {installer_type}")
                return False, ""

        except Exception as e:
            self.log_signal.emit(f"安装过程中发生错误: {str(e)}")
            return False, ""

    def _detect_installer_type(self, installer_path: str) -> str:
        """检测安装包类型"""
        path = Path(installer_path)
        ext = path.suffix.lower()
        
        if ext == '.msi':
            return 'msi'
        elif ext == '.exe':
            return 'exe'
        elif ext == '.zip':
            return 'zip'
        elif ext == '.7z':
            return '7z'
        elif ext == '.rar':
            return 'rar'
        elif ext == '.tar':
            return 'tar'
        elif ext in ['.gz', '.tar.gz']:
            return 'tar.gz'
        elif ext in ['.bz2', '.tar.bz2']:
            return 'tar.bz2'
        else:
            # 尝试从文件名中检测
            name_lower = path.name.lower()
            if 'installer' in name_lower or 'setup' in name_lower:
                return 'exe'
            else:
                return 'exe'  # 默认为exe

    def _install_msi(self, installer_path: str, install_dir: str, binary_name: str,
                    silent_params: Optional[Dict[str, Any]] = None) -> tuple:
        """安装MSI包"""
        self.status_signal.emit("installing")
        self.log_signal.emit(f"开始静默安装MSI包: {installer_path}")
        
        # 默认MSI静默安装参数
        default_params = [
            'msiexec',
            '/i',  # 安装
            f'"{installer_path}"',
            '/quiet',  # 静默安装
            '/norestart',  # 不重启
            f'TARGETDIR="{install_dir}"',
            'ALLUSERS=1'
        ]
        
        # 合并用户参数
        if silent_params:
            for key, value in silent_params.items():
                if isinstance(value, bool):
                    param_value = '1' if value else '0'
                    default_params.append(f'{key}={param_value}')
                else:
                    default_params.append(f'{key}={value}')
        
        # 执行安装
        success = self._execute_install_command(default_params, "MSI")
        if success:
            return self.verify_installation(install_dir, binary_name)
        else:
            return False, ""

    def _install_exe(self, installer_path: str, install_dir: str, binary_name: str,
                    silent_params: Optional[Dict[str, Any]] = None) -> tuple:
        """安装EXE包"""
        self.status_signal.emit("installing")
        self.log_signal.emit(f"开始静默安装EXE包: {installer_path}")
        
        # 常见的EXE静默安装参数
        installer_name = Path(installer_path).name.lower()
        
        # 根据安装包名称选择合适的参数
        if 'python' in installer_name:
            # Python安装器参数
            install_cmd = [
                installer_path,
                '/quiet',
                'InstallAllUsers=0',
                'PrependPath=0',
                'Include_launcher=0',
                f'TargetDir={install_dir}',
                '/norestart'
            ]
        elif 'node' in installer_name and 'x64' in installer_name:
            # Node.js安装器参数
            install_cmd = [
                installer_path,
                '/S',  # 静默安装
                f'/D={install_dir}'  # 安装目录
            ]
        elif 'git' in installer_name:
            # Git安装器参数
            install_cmd = [
                installer_path,
                '/VERYSILENT',
                '/NORESTART',
                f'/DIR={install_dir}'
            ]
        elif 'jdk' in installer_name or 'java' in installer_name:
            # JDK安装器参数
            install_cmd = [
                installer_path,
                '/s',  # 静默安装
                f'/D={install_dir}'
            ]
        else:
            # 通用EXE静默安装参数
            install_cmd = [
                installer_path,
                '/S',  # 静默安装（NSIS）
                '/VERYSILENT',  # 静默安装（Inno Setup）
                '/SILENT',      # 静默安装（Inno Setup）
                f'/DIR={install_dir}',
                f'/D={install_dir}'
            ]
        
        # 如果提供了自定义参数，优先使用
        if silent_params:
            if 'command' in silent_params:
                # 直接使用用户提供的命令
                install_cmd = [installer_path] + silent_params['command']
            else:
                # 合并参数
                install_cmd = [installer_path]
                for key, value in silent_params.items():
                    if key != 'command':
                        if isinstance(value, bool):
                            param_value = '1' if value else '0'
                            install_cmd.append(f'/{key}={param_value}')
                        else:
                            install_cmd.append(f'/{key}={value}')
        
        # 执行安装
        success = self._execute_install_command(install_cmd, "EXE")
        if success:
            return self.verify_installation(install_dir, binary_name)
        else:
            return False, ""



    def _execute_install_command(self, command: List[str], installer_type: str) -> bool:
        """执行安装命令，返回是否成功"""
        """执行安装命令"""
        try:
            self.log_signal.emit(f"执行安装命令: {' '.join(command)}")
            
            # 执行安装命令
            result = subprocess.run(
                command,
                capture_output=True,
                text=True,
                timeout=3600,  # 1小时超时
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
            )
            
            if result.returncode == 0:
                self.log_signal.emit(f"{installer_type}安装成功")
                self.status_signal.emit("success")
                return True
            else:
                self.log_signal.emit(f"{installer_type}安装失败，错误码: {result.returncode}")
                self.log_signal.emit(f"错误信息: {result.stderr}")
                self.status_signal.emit("failed")
                return False
                
        except subprocess.TimeoutExpired:
            self.log_signal.emit(f"{installer_type}安装超时")
            self.status_signal.emit("failed")
            return False
        except Exception as e:
            self.log_signal.emit(f"{installer_type}安装过程中发生异常: {str(e)}")
            self.status_signal.emit("failed")
            return False

    def install_multiple_software(self, software_list: List[Dict[str, Any]]) -> Dict[str, bool]:
        """
        批量安装软件

        Args:
            software_list: 软件安装信息列表，每个元素包含:
                          {
                            'installer_path': str,
                            'install_dir': str,
                            'silent_params': dict (可选),
                            'installer_type': str (可选)
                          }

        Returns:
            Dict[str, bool]: 安装结果字典，键为安装包路径，值为是否成功
        """
        results = {}
        
        for i, software_info in enumerate(software_list):
            self.progress_signal.emit(f"正在安装第 {i+1}/{len(software_list)} 个软件")
            
            installer_path = software_info.get('installer_path')
            install_dir = software_info.get('install_dir')
            silent_params = software_info.get('silent_params')
            installer_type = software_info.get('installer_type')
            
            success = self.install_software(
                installer_path=installer_path,
                install_dir=install_dir,
                silent_params=silent_params,
                installer_type=installer_type
            )
            
            results[installer_path] = success
            
            if not success:
                self.log_signal.emit(f"软件安装失败: {installer_path}")
                # 可以选择继续安装其他软件或停止
                # 这里我们继续安装其他软件
        
        return results

    def verify_installation(self, install_dir: str, binary_name: str = None) -> tuple:
        """
        验证安装是否成功

        Args:
            install_dir: 安装目录
            binary_name: 期望存在的可执行文件名

        Returns:
            tuple: (是否成功, 可执行文件完整路径)
        """
        install_path = Path(install_dir)

        if not install_path.exists():
            self.log_signal.emit(f"安装目录不存在: {install_dir}")
            return False, ""

        if binary_name:
            full_path = install_path / binary_name
            if not full_path.exists():
                self.log_signal.emit(f"缺少文件: {full_path}")
                return False, ""
            else:
                self.log_signal.emit(f"文件存在: {full_path}")
                return True, str(full_path)
        else:
            self.log_signal.emit("缺少参数")
            return False, ''



class SoftwareInstallerConfig:
    """软件安装配置类"""
    
    # 常见软件的静默安装参数配置
    COMMON_INSTALLER_PARAMS = {
        'python': {
            'exe': {
                '/quiet': '',
                'InstallAllUsers=0': '',
                'PrependPath=0': '',
                'Include_launcher=0': '',
                '/norestart': ''
            }
        },
        'nodejs': {
            'exe': {
                '/S': '',
                '/NORESTART': ''
            }
        },
        'git': {
            'exe': {
                '/VERYSILENT': '',
                '/NORESTART': '',
                '/NOCANCEL': ''
            }
        },
        'jdk': {
            'exe': {
                '/s': '',
                '/L': 'disable_eula'  # 静默同意许可
            }
        }
    }
    
    @classmethod
    def get_default_params(cls, software_name: str, installer_type: str = 'exe') -> Dict[str, str]:
        """获取指定软件的默认安装参数"""
        software_name = software_name.lower()
        installer_type = installer_type.lower()
        
        if software_name in cls.COMMON_INSTALLER_PARAMS:
            if installer_type in cls.COMMON_INSTALLER_PARAMS[software_name]:
                return cls.COMMON_INSTALLER_PARAMS[software_name][installer_type]
        
        return {}


# 使用示例
if __name__ == "__main__":
    # 创建安装器实例
    installer = SilentInstaller()
    
    # 连接信号
    installer.progress_signal.connect(lambda msg: print(f"进度: {msg}"))
    installer.status_signal.connect(lambda msg: print(f"状态: {msg}"))
    installer.log_signal.connect(lambda msg: print(f"日志: {msg}"))
    
    # 示例1: 安装单个软件
    success, path = installer.install_software(
        r"C:\Users\89913\Downloads\python-3.9.5.exe", r'D:\python395',
        binary_name='python.exe',
    )
    
    print(f"安装结果: {success}")
    print(f"安装结果: {path}")
    
