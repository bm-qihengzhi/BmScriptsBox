"""
Copyright (c) 2026 綦恒智
Email: bmscriptsbox@163.com
SPDX-License-Identifier: AGPL-3.0
"""
import win32gui
from pathlib import Path
from .desktop_utils import DesktopMouseChecker


class FileExplorerManager:
    """管理资源管理器窗口路径匹配"""

    def __init__(self, shell):
        self._shell = shell

    def get_active_tab_path(self) -> list:
        if DesktopMouseChecker.is_mouse_on_desktop():
            return [str(Path.home() / "Desktop")]

        paths = self._get_explorer_paths()
        title = self._get_active_explorer_title()
        active_path = self._match_path_and_title(paths, title)

        if not active_path:
            raise ValueError("无法识别当前窗口路径")
        return [active_path]

    def _get_explorer_paths(self):
        paths = []
        for window in self._shell.Windows():
            try:
                paths.append(window.Document.Folder.Self.Path)
            except:
                continue
        return paths

    def _get_active_explorer_title(self):
        titles = []

        def callback(hwnd, t_list):
            if win32gui.GetClassName(hwnd) in ["CabinetWClass", "WorkerW", "Progman"]:
                title = win32gui.GetWindowText(hwnd)
                if title and win32gui.IsWindowVisible(hwnd):
                    t_list.append(title)
            return True

        win32gui.EnumWindows(callback, titles)
        return titles[0] if titles else ""

    def _match_path_and_title(self, paths: list, title: str) -> str:
        """
        比对路径和标题，确定当前活动选项卡的路径

        参数:
            paths (list): 路径列表，用于匹配标题
            title (str): 标题字符串，用于匹配路径

        返回:
            str: 匹配到的路径字符串

        异常:
            ValueError: 当路径列表为空、标题为空或未找到匹配路径时抛出
        """
        if not paths:
            raise ValueError("路径列表为空")
        if not title:
            raise ValueError("标题为空")

        # 定义英文文件夹名到中文的映射
        folder_name_mapping = {
            "Downloads": "下载",
            "Documents": "文档",
            "Pictures": "图片",
            "Music": "音乐",
            "Videos": "视频",
        }

        # 清理标题，提取核心部分
        clean_title = title.split(' - ')[0].strip()
        if ' 和 ' in clean_title:
            clean_title = clean_title.split(' 和 ')[0].strip()
        # 遍历路径列表，查找与标题匹配的路径
        for path in paths:
            # 提取路径中最后一个 \ 后面的文件夹名称
            folder_name = Path(path).name

            # 多种匹配策略
            # 1. 直接匹配
            if folder_name in title or folder_name in clean_title:
                return path

            # 2. 通过映射匹配
            if folder_name in folder_name_mapping:
                chinese_name = folder_name_mapping[folder_name]
                if chinese_name in title or chinese_name in clean_title:
                    return path

            # 3. 反向映射匹配（中文路径名）
            for english_name, chinese_name in folder_name_mapping.items():
                if chinese_name == folder_name and english_name in title:
                    return path

        raise ValueError("未找到匹配的路径")
