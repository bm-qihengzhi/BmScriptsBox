"""
Copyright (c) 2026 綦恒智
Email: bmscriptsbox@163.com
SPDX-License-Identifier: MIT
SPDX-License-Identifier: LicenseRef-Commons-Clause
"""
import webbrowser

from PySide2.QtCore import Qt, Signal, QUrl, QSize
from PySide2.QtGui import QDesktopServices
from PySide2.QtWidgets import QVBoxLayout, QFrame, QLabel, QSizePolicy

from app.data import ScriptDatabase, ProjectGlobal
from app.utils import BM_LOG, BmNotify
from app.utils.tools import BmTools
from xsideui import XCard, XLabel, XImage, XMenu, \
    IconName, XIcon, XColor, tr


class ScriptCard(XCard):
    """
    脚本卡片
    """

    # 文本徽章颜色映射（badge 文本 → 背景色）
    BADGE_COLORS = {
        '本地': '#909399',
    }

    MIN_CARD_W = 140

    uninstalled = Signal(str)
    started = Signal(str)
    updated = Signal(dict)

    def __init__(self, script_info):
        super().__init__()
        self.set_clickable(True)
        self.script_info = script_info
        self._icon_source = None
        self._pin_label = None
        self._badge_label = None
        self._setup_ui()
        self._setup_badges()

    def update_data(self, script_info):
        """就地更新卡片数据（复用卡片实例，避免整表重建导致图标重载）"""
        old = self.script_info
        if (old.id, old.name, old.icon, old.badge, old.pin, old.version) == \
                (script_info.id, script_info.name, script_info.icon,
                 script_info.badge, script_info.pin, script_info.version):
            return
        name_changed = old.name != script_info.name
        self.script_info = script_info

        icon = script_info.icon or BmTools.get_language_icon_path(script_info.language)
        if icon != self._icon_source:
            self._icon_source = icon
            self.img.set_source(icon)

        if name_changed:
            self.title_label.setText(script_info.name)

        self._refresh_badges()

    def sizeHint(self):
        # 根据父容器实际可用宽度自适应列数，卡片在该列数下铺满，避免临界宽度下挤成少列
        parent = self.parentWidget()
        if parent and parent.layout():
            margins = parent.layout().contentsMargins()
            spacing = parent.layout().spacing()
            avail = parent.width() - margins.left() - margins.right()
            cols = max(1, (avail + spacing) // (self.MIN_CARD_W + spacing))
            card_w = (avail - (cols - 1) * spacing) // cols
        else:
            card_w = self.MIN_CARD_W
        scale = self.logicalDpiY() / 96.0  # 高 DPI 缩放系数
        card_h = max(60, int(80 * scale))  # 80 是基准高度，按比例放大
        return QSize(card_w, card_h)

    def minimumSizeHint(self):
        # 最小宽度与建议宽度一致，长文本不得撑开流式布局
        return self.sizeHint()

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
        self.content_layout.addStretch()  # 前后各一个 stretch → icon/标题垂直居中

        self.setContextMenuPolicy(Qt.CustomContextMenu)
        self.customContextMenuRequested.connect(self._add_menu)

    def _add_icon(self):
        """添加脚本图标"""
        icon = self.script_info.icon
        if not icon:
            icon = BmTools.get_language_icon_path(self.script_info.language)
        self._icon_source = icon
        self.img = XImage(source=icon, fit=XImage.FitMode.COVER, lazy=True, min_size=28)

        self.img.setContextMenuPolicy(Qt.NoContextMenu)  # 禁用右键菜单
        self.img.setAttribute(Qt.WA_TransparentForMouseEvents, True)  # 禁用鼠标事件
        self.img.setFixedSize(28, 28)
        self.content_layout.addWidget(self.img, alignment=Qt.AlignCenter)

    def _add_central(self):
        """添加中央布局"""
        # 不能给 addWidget 传 alignment：那会让标签按 sizeHint 摆放（构造时被省略成 ...，sizeHint 塌缩）
        # 改为标签填满卡片宽（Ignored），文本在标签内部居中
        self.title_label = XLabel(self.script_info.name, elide_mode=True, alignment=Qt.AlignCenter)
        self.title_label.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
        self.content_layout.addWidget(self.title_label)
        self.title_label.setContextMenuPolicy(Qt.NoContextMenu)  # 禁用右键菜单
        self.title_label.setAttribute(Qt.WA_TransparentForMouseEvents, True)  # 禁用鼠标事件


    def _setup_badges(self):
        """创建徽章子控件（随卡片裁剪，无浮动问题）"""
        # 清除旧徽章，支持就地重建
        if self._pin_label:
            self._pin_label.deleteLater()
            self._pin_label = None
        if self._badge_label:
            self._badge_label.deleteLater()
            self._badge_label = None

        # 置顶图标
        if self.script_info.pin:
            pixmap = XIcon.get(name=IconName.PIN_FILL, color=XColor.TERTIARY, size=14).pixmap()
            self._pin_label = QLabel(self)
            self._pin_label.setPixmap(pixmap)
            self._pin_label.setFixedSize(14, 14)
            self._pin_label.setAttribute(Qt.WA_TransparentForMouseEvents, True)
            self._pin_label.show()  # 手动定位子控件：在已可见卡片上动态创建须显式 show

        # 文本徽章
        badge_text = self.script_info.badge
        if badge_text:
            badge_color = ScriptCard.BADGE_COLORS.get(badge_text, '#909399')
            self._badge_label = QLabel(badge_text, self)
            self._badge_label.setStyleSheet(
                f"QLabel {{"
                f"  background-color: {badge_color};"
                f"  color: #F1F1F1;"
                f"  padding: 1px 6px;"
                f"  border-radius: 4px;"
                f"  font-size: 11px;"
                f"}}"
            )
            self._badge_label.adjustSize()
            self._badge_label.setAttribute(Qt.WA_TransparentForMouseEvents, True)
            self._badge_label.show()  # 同上：动态创建须显式 show

        self._position_badges()

    def _refresh_badges(self):
        """数据更新后刷新角标/徽章"""
        self._setup_badges()

    def _position_badges(self):
        if self._pin_label:
            self._pin_label.move(10, 10)
        if self._badge_label:
            self._badge_label.move(self.width() - self._badge_label.width() - 6, 6)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._position_badges()

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
            new_pin = not self.script_info.pin
            self.db = ScriptDatabase()
            self.db.update_status(self.script_info.id, 'pin', new_pin)
            # 不再就地改 self.script_info：否则复用分支的 update_data 会误判为“无变化”而跳过角标刷新
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

