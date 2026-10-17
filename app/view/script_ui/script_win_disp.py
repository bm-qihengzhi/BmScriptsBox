"""
Copyright (c) 2026 綦恒智
Email: bmscriptsbox@163.com
SPDX-License-Identifier: MIT
SPDX-License-Identifier: LicenseRef-Commons-Clause
"""
from PySide2.QtCore import Qt, Signal, QTimer
from PySide2.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QFrame, \
    QStackedLayout

from xsideui import XPushButton, XFlowLayout, XLineEdit, XCarousel, XLabel, XImage, IconName, XIcon, XColor, \
    XScrollArea, tr

from .script_win_card import ScriptCard
from .script_pr import ScriptPresenter



class ScriptsWidget(QWidget):
    """脚本展示视图 - 负责 UI 渲染和用户交互"""

    login_signal = Signal(bool)
    ScriptHub = Signal()

    def __init__(self):
        super().__init__()
        self.presenter = ScriptPresenter()
        self.db = None
        self._all_scripts = []
        self._last_sig = None
        self._cards = {}   # id -> ScriptCard（复用实例，避免整表重建）
        self._order = []   # 上次渲染的卡片顺序

        self.info_widget = None
        self._init_ui()
        self._init_signals()
        self._init_presenter_signals()

        self.search_timer = QTimer()
        self.search_timer.setSingleShot(True)
        self.search_timer.timeout.connect(self._do_filter)

    def _init_ui(self):
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(11, 11, 11, 11)
        self.main_layout.setSpacing(11)

        self.banner = XCarousel(interval=3000, min_height=120)
        self.banner.setMaximumHeight(120)
        self.main_layout.addWidget(self.banner, 0)

        self.scripts_search_layout = QHBoxLayout()
        self.scripts_search_layout.setContentsMargins(0, 0, 0, 0)
        self.scripts_search_layout.setSpacing(5)
        self.search_bar = XLineEdit(placeholder=tr('Search scripts...'), prefix_icon=IconName.SEARCH)

        self.scripts_search_layout.addWidget(self.search_bar)
        self.btn_install = XPushButton(tr('Install Script'), icon=IconName.INSTALL)

        self.scripts_search_layout.addWidget(self.btn_install)
        self.main_layout.addLayout(self.scripts_search_layout, 0)

        self.scroll_area = XScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.set_scrollbar_visible(True, False)
        self.scroll_content = QFrame()
        self.stack_layout = QStackedLayout(self.scroll_content)

        self.list_container = QWidget()
        self.flow_layout = XFlowLayout(self.list_container)
        self.flow_layout.setContentsMargins(0, 0, 0, 0)
        self.flow_layout.setSpacing(11)
        self.stack_layout.addWidget(self.list_container)

        self.empty_container = self._create_empty_widget()
        self.stack_layout.addWidget(self.empty_container)

        self.scroll_area.setWidget(self.scroll_content)
        self.main_layout.addWidget(self.scroll_area, 1)

        QTimer.singleShot(0, self.presenter.lazy_loading)

    def _init_signals(self):
        self.search_bar.textChanged.connect(self._on_search_text_changed)
        self.btn_install.clicked.connect(lambda :self.ScriptHub.emit())
        self.banner.image_clicked.connect(self.presenter.on_banner_clicked)


    def _init_presenter_signals(self):
        """逻辑层信号"""
        self.presenter.scripts_loaded.connect(self._on_scripts_loaded)
        self.presenter.banner_loaded.connect(self._on_banner_loaded)
        self.presenter.show_window.connect(self._on_show_window)

    def _on_show_window(self):
        """脚本未启动成功时恢复主窗口"""
        window = self.window()
        if window is not None:
            window.show()
            window.raise_()
            window.activateWindow()

    def _on_search_text_changed(self):
        self.search_timer.start(300)

    def _do_filter(self):
        filter_text = self.search_bar.text()
        filtered = self.presenter.filter_scripts(filter_text, self._all_scripts)
        self._render_scripts(filtered)

    def _create_empty_widget(self):
        empty_widget = QWidget()
        layout = QVBoxLayout(empty_widget)
        layout.setSpacing(20)
        layout.setAlignment(Qt.AlignCenter)
        layout.addWidget(XImage(source=XIcon.get(name=IconName.EMOTION_UNHAPPY, color=XColor.TERTIARY, size=32).pixmap(), min_size=32))
        layout.addWidget(XLabel(tr("The script is empty.")).set_color(XColor.TERTIARY), alignment=Qt.AlignCenter)
        return empty_widget


    def _on_scripts_loaded(self, scripts_data):
        self._all_scripts = scripts_data
        # 刷新后重新套用当前搜索词，避免“框里有词、列表却是全量”的不一致
        self._render_scripts(self.presenter.filter_scripts(self.search_bar.text(), scripts_data))

    def _on_banner_loaded(self, banner_list):
        for banner in banner_list:
            self.banner.add_image_page(banner)

    def _render_scripts(self, scripts_data):
        # 数据未变（同一批 id/pin/徽章/名称/图标/版本）则跳过，避免无谓刷新
        sig = tuple((s.id, s.pin, s.badge, s.name, s.icon, s.version) for s in scripts_data)
        if sig == self._last_sig:
            return
        self._last_sig = sig

        new_ids = [s.id for s in scripts_data]
        new_set = set(new_ids)

        # 1) 移除已消失的卡片（其余卡片实例保留，图标不重载）
        for sid in [k for k in self._cards if k not in new_set]:
            stale = self._cards.pop(sid)
            stale.hide()
            stale.deleteLater()

        # 2) 复用已有卡片就地更新；新脚本才新建并连接信号（信号只连一次）
        for script in scripts_data:
            card = self._cards.get(script.id)
            if card is None:
                card = ScriptCard(script)
                card.updated.connect(self._on_card_updated)
                card.uninstalled.connect(self._on_card_uninstall)
                card.started.connect(self._on_card_started)
                card.clicked.connect(card._start_script)
                self._cards[script.id] = card
            else:
                card.update_data(script)

        # 3) 仅顺序变化时重排（非删除式：摘出所有项再按序放回）
        if new_ids != self._order:
            self._reorder(new_ids)
            self._order = list(new_ids)

        if not scripts_data:
            self.stack_layout.setCurrentWidget(self.empty_container)
            return

        scroll_bar = self.scroll_area.verticalScrollBar()
        scroll_pos = scroll_bar.value()
        self.stack_layout.setCurrentWidget(self.list_container)
        self.list_container.updateGeometry()
        # 布局完成后恢复滚动位置（重排会重置滚动条）
        QTimer.singleShot(0, lambda p=scroll_pos: scroll_bar.setValue(p))

    def _reorder(self, ordered_ids):
        """按 ordered_ids 重排卡片，复用同一批控件实例（不删除、不重建、不重载图）"""
        while self.flow_layout.count():
            self.flow_layout.takeAt(0)
        for sid in ordered_ids:
            card = self._cards.get(sid)
            if card is not None:
                self.flow_layout.addWidget(card)




    def _on_card_started(self, script_id: str):
        # 运行时立即隐藏主窗口（参数表单弹出期间也保持隐藏）
        self.window().hide()
        self.presenter.execute_script(script_id)

    def _on_card_uninstall(self, script_id:str):
        self.presenter.uninstall_script(script_id)

    def _on_card_updated(self, msg: dict):
        self.presenter.refresh_scripts()


