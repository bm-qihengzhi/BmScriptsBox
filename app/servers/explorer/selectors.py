"""
Copyright (c) 2026 綦恒智
Email: bmscriptsbox@163.com
SPDX-License-Identifier: AGPL-3.0
"""
import os
import subprocess
from pathlib import Path
from .manager import FileExplorerManager


class SelectedActiveWindow:
    def __init__(self, shell):
        self._shell = shell

    def get_active_folder_window(self):
        active_mgr = FileExplorerManager(self._shell)
        active_paths = active_mgr.get_active_tab_path()
        active_path = active_paths[0]

        if active_path == str(Path.home() / "Desktop"):
            return "DESKTOP"

        for window in self._shell.Windows():
            try:
                if window.Document.Folder.Self.Path == active_path:
                    return window
            except:
                continue
        raise ValueError(f"未找到路径窗口: {active_path}")

    def get_selected_items(self) -> list:
        window = self.get_active_folder_window()
        if window == "DESKTOP":
            return self._get_desktop_files()

        items = window.Document.SelectedItems()
        if items.Count >= 500:
            raise ValueError("选中项过多")
        return [item.Path for item in items]

    def _get_desktop_files(self):
        # AHK 逻辑
        script_path = str(Path(__file__).parent / "get_desktop.exe")
        res = subprocess.run([script_path], capture_output=True, text=True, encoding='gbk',
                              creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)
        return res.stdout.strip().split('\n') if res.stdout else []


class SelectedFilesInExplorer:
    def __init__(self, shell): self._shell = shell

    def get_selected_files(self):
        paths = SelectedActiveWindow(self._shell).get_selected_items()
        return [p for p in paths if Path(p).is_file()]


class SelectedFolderInExplorer:
    def __init__(self, shell): self._shell = shell

    def get_selected_folder(self):
        paths = SelectedActiveWindow(self._shell).get_selected_items()
        return [p for p in paths if Path(p).is_dir()]


class SelectedFilesAndFolderInExplorer:
    def __init__(self, shell): self._shell = shell

    def get_selected_folder_and_files(self):
        return SelectedActiveWindow(self._shell).get_selected_items()