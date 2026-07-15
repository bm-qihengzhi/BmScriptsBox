"""
Copyright (c) 2026 綦恒智
Email: bmscriptsbox@163.com
SPDX-License-Identifier: AGPL-3.0
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


    def _on_install_success(self, msg: dict):
        self.presenter.refresh_scripts()

    def _on_scripts_loaded(self, scripts_data):
        self._all_scripts = scripts_data
        self._render_scripts(scripts_data)

    def _on_banner_loaded(self, banner_list):
        for banner in banner_list:
            self.banner.add_image_page(banner)

    def _render_scripts(self, scripts_data):
        if not scripts_data:
            self.stack_layout.setCurrentWidget(self.empty_container)
            return
        self.stack_layout.setCurrentWidget(self.list_container)
        self.flow_layout.clear()
        for script in scripts_data:
            script_card = ScriptCard(script)
            script_card.updated.connect(self._on_card_updated)
            script_card.uninstalled.connect(self._on_card_uninstall)
            script_card.started.connect(self._on_card_started)
            script_card.clicked.connect(script_card._start_script)
            self.flow_layout.addWidget(script_card)




    def _on_card_started(self,script_id:str):
        self.window().hide()
        self.presenter.execute_script(script_id)

    def _on_card_uninstall(self, script_id:str):
        self.presenter.uninstall_script(script_id)

    def _on_card_updated(self, msg: dict):
        self.presenter.refresh_scripts()


