"""
Copyright (c) 2026 綦恒智
Email: bmscriptsbox@163.com
SPDX-License-Identifier: AGPL-3.0
"""
import sys
import json
from xsideui import XDialog, XLabel, tr, XColor, XTextEdit, XPushButton, XButtonVariant
from PySide2 import QtWidgets
from PySide2.QtWidgets import QFrame, QVBoxLayout, QHBoxLayout

from app.data import ProjectGlobal
from app.utils import BmTools, BmNotify


class ProxyWidget(XDialog):
    def __init__(self, parent=None):
        super(ProxyWidget, self).__init__(parent=parent)
        self.setModal(True)
        self._init_ui()
        self.disp_proxy()
        self._init_signal()

    def _init_ui(self):
        self.hide_title_bar()
        context_widget = QFrame()
        self.addWidget(context_widget)
        context_layout = QVBoxLayout(context_widget)
        context_layout.setContentsMargins(20, 20, 20, 20)
        context_layout.setSpacing(11)

        context_layout.addWidget(XLabel(tr('Edit Proxy Server'), style=XLabel.Style.H4).set_font_size(18))
        context_layout.addWidget(
            XLabel(tr('For script environments, dependencies, and binaries'), style=XLabel.Style.H4).set_font_size(
                13).set_color(XColor.TERTIARY))

        self.proxy_edit = XTextEdit(placeholder=tr('Supports multiple proxy sources (one per line)'))
        context_layout.addWidget(self.proxy_edit)
        context_layout.addWidget(
            XLabel(tr('Source: Internet. Slow speed? Customize below. [Tutorials]')).set_font_size(10))

        btn_layout = QHBoxLayout()
        self.btn_save = XPushButton(text=tr('Save'))
        self.btn_cancel = XPushButton(text=tr('Cancel'), variant=XButtonVariant.OUTLINED, color=XColor.TERTIARY)
        btn_layout.addWidget(self.btn_save)
        btn_layout.addWidget(self.btn_cancel)

        context_layout.addLayout(btn_layout)

    def _init_signal(self):
        self.btn_cancel.clicked.connect(self.close)
        self.btn_save.clicked.connect(self.save_proxy)

    def disp_proxy(self):
        self.proxy_edit.setFocus()
        for proxy in ProjectGlobal.PROXIES:
            self.proxy_edit.append(proxy)

    def save_proxy(self):
        raw_text = self.proxy_edit.toPlainText()
        lines = raw_text.splitlines()
        proxy_list = [line.strip() for line in lines if line.strip()]
        self._handle_save_logic(proxy_list)
        self.close()

    def _handle_save_logic(self, proxy_list):
        # 修改内存中的代理数据
        ProjectGlobal.PROXIES = proxy_list
        # 修改json中的代理数据
        json_path = BmTools.get_resources_path() / 'configs.json'
        if not json_path.exists():
            raise FileNotFoundError('No configs.json found')
        try:
            with open(str(json_path), 'r', encoding='utf-8') as json_file:
                json_data = json.load(json_file)
                json_data['PROXIES'] = proxy_list

                # 将修改后的数据写回文件
                with open(str(json_path), 'w', encoding='utf-8') as json_file:
                    json.dump(json_data, json_file, indent=2, ensure_ascii=False)

        except Exception as e:
            print(e)
            BmNotify().show_error_notify('save proxies failed')


if __name__ == '__main__':
    app = QtWidgets.QApplication(sys.argv)
    proxy = ProxyWidget()
    proxy.show()
    sys.exit(app.exec_())
