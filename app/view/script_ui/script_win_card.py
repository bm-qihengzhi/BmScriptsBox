"""
Copyright (c) 2026 綦恒智
Email: bmscriptsbox@163.com
SPDX-License-Identifier: AGPL-3.0
"""
import webbrowser

from PySide2.QtCore import Qt, Signal, QUrl, QSize
from PySide2.QtGui import QDesktopServices
from PySide2.QtWidgets import QVBoxLayout, QFrame

from app.data import ScriptDatabase, ProjectGlobal
from app.utils import BM_LOG, BmNotify
from app.utils.tools import BmTools
from app.view.script_ui.script_card_pr import ScriptCardPresenter
from xsideui import XCard, XLabel, XImage, XMenu, \
    IconName, XIcon, XColor, tr


class ScriptCard(XCard):
    """
    脚本卡片
    """
    uninstalled = Signal(str)
    started = Signal(str)
    updated = Signal(dict)

    def __init__(self, script_info):
        super().__init__()
        self.presenter = ScriptCardPresenter()
        self.sizeHint()
        self.set_clickable(True)
        self.script_info = script_info
        self._setup_ui()

    def sizeHint(self):
        # 根据父容器宽度计算卡片宽度
        parent = self.parentWidget()
        if parent and parent.layout():
            avail = parent.width() - parent.layout().contentsMargins().left() \
                    - parent.layout().contentsMargins().right() \
                    - parent.layout().spacing() * 2
            card_w = max(140, avail // 3)
        else:
            card_w = 140
        scale = self.logicalDpiY() / 96.0  # 高 DPI 缩放系数
        card_h = max(60, int(80 * scale))  # 80 是基准高度，按比例放大
        return QSize(card_w, card_h)

    def _setup_ui(self):
        """初始化 UI 组件"""
        context_widget = QFrame()
        self.content_layout = QVBoxLayout(context_widget)
        self.content_layout.setContentsMargins(0, 0, 0, 0)
        self.content_layout.setSpacing(11)
        self.content_layout.addStretch()
        self._layout.addWidget(context_widget)
        self._add_icon()
        self._add_central()

        self.setContextMenuPolicy(Qt.CustomContextMenu)
        self.customContextMenuRequested.connect(self._add_menu)

    def _add_icon(self):
        """添加脚本图标"""
        icon = self.script_info.icon
        if not icon:
            icon = BmTools.get_language_icon_path(self.script_info.language)
        self.img = XImage(source=icon, fit=XImage.FitMode.COVER, lazy=True, min_size=28)

        self.img.setContextMenuPolicy(Qt.NoContextMenu)  # 禁用右键菜单
        self.img.setAttribute(Qt.WA_TransparentForMouseEvents, True)  # 禁用鼠标事件
        self.img.setFixedSize(28, 28)
        self.content_layout.addWidget(self.img, alignment=Qt.AlignCenter)

    def _add_central(self):
        """添加中央布局"""
        self.title_label = XLabel(self.script_info.name)
        self.content_layout.addWidget(self.title_label, alignment=Qt.AlignCenter)
        self.title_label.setContextMenuPolicy(Qt.NoContextMenu)  # 禁用右键菜单
        self.title_label.setAttribute(Qt.WA_TransparentForMouseEvents, True)  # 禁用鼠标事件


    def _add_menu(self, pos):
        """
        添加右键菜单
        :return:
        """
        menu = XMenu(self)
        menu.add_action(icon=XIcon(IconName.PLAY, color=XColor.SUCCESS).icon(), text=tr('Run'),
                        triggered=self._start_script)
        menu.add_action(icon=XIcon(IconName.DELETE, color=XColor.DANGER).icon(), text=tr('Uninstall'),
                        triggered=self.uninstall_script)
        if self.script_info.pin:
            menu.add_action(text=tr('Unpin'),triggered=self._pinned_top)
        else:
            menu.add_action(icon=XIcon(IconName.PIN_FILL).icon(), text=tr('Pin'), triggered=self._pinned_top)
        menu.add_action(text=tr('Details'), icon=XIcon(IconName.INFO).icon(), triggered=self._show_info)
        if self.script_info.badge != '本地':
            menu.add_action(text=tr('Star'), icon=XIcon(IconName.STAR).icon(), triggered=self._show_info)
            menu.add_action(text=tr('Report'), icon=XIcon(IconName.REPORT).icon(), triggered=self._show_info)
        menu.add_action(text=tr('Open Location'), icon=XIcon(IconName.FOLDER).icon(), triggered=self._show_folder)
        menu.exec_(self.mapToGlobal(pos))

    def _show_folder(self):
        """显示脚本目录"""
        path = BmTools.get_base_scripts_path() / self.script_info.id
        if path.exists():
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(path.absolute())))

    def _show_info(self):
        """
        显示脚本详情,访问url
        :return:
        """
        script_id = self.script_info.id
        webbrowser.open_new_tab(ProjectGlobal.API_GATEWAY + '/detail/' + script_id)

    def _pinned_top(self):
        """
        设置脚本置顶 / 取消置顶
        :return:
        """
        try:
            is_top = self.script_info.pin
            self.db = ScriptDatabase()
            result = self.db.update_status(self.script_info.id, 'pin',not is_top)
            if result:
                self.script_info = result
            self.updated.emit({'state': True})
        except Exception as e:
            BM_LOG.error(f"设置脚本置顶失败: {e}")



    def uninstall_script(self) -> None:
        """卸载脚本(转发信号)"""
        BmNotify().show_info_notify(tr('Uninstalling...'), in_window=True)
        self.uninstalled.emit(self.script_info.id)


    def _start_script(self):
        """点击卡片启动脚本(转发信号)"""
        self.started.emit(self.script_info.id)

