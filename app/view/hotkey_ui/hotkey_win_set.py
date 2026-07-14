"""
Copyright (c) 2026 綦恒智
Email: bmscriptsbox@163.com
SPDX-License-Identifier: AGPL-3.0
"""
from typing import Optional

from PySide2.QtCore import Qt, Signal
from PySide2.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QFrame

from app.utils import BM_LOG
from app.utils.tools import BmTools
from app.servers.monitor import get_hotkey_manager
from xsideui import XPushButton, XLabel, XButtonVariant, XDialog, tr, XColor


class HotkeySettingWidget(XDialog):
    handle_signal = Signal(tuple)
    _combo_detected = Signal(str)

    def __init__(self, script_id: str, hotkey_key: str, script_name: str,
                 conflict_check_fn=None, parent: Optional[QWidget] = None):
        super().__init__(parent=parent)
        self.setModal(True)
        self.stop_requested = None
        self.script_id = script_id
        self.hotkey_key = hotkey_key or tr("Press keys in sequence to set a shortcut")
        self.script_name = script_name
        self._conflict_check_fn = conflict_check_fn
        self.resize(360, 260)
        self._keyboard_hook = None
        self.add_ui()
        self._combo_detected.connect(self._on_combo_received)
        self.start_monitor()


    def add_ui(self):
        self.addWidget(self._create_ui())
        self.hide_title_bar()
        self.set_logo(BmTools.get_logo_path())


    def _on_key_event(self, event):
        """键盘回调（背景线程），只解析按键，不碰 Qt/DB"""
        import keyboard as kb
        try:
            modifiers = []
            for mod in ['ctrl', 'alt', 'shift', 'windows']:
                if kb.is_pressed(mod) and mod != event.name:
                    modifiers.append(mod)

            if not modifiers and event.name in ['ctrl', 'alt', 'shift', 'windows']:
                return

            key_name = event.name
            if event.event_type == kb.KEY_DOWN and hasattr(event, 'is_keypad') and event.is_keypad:
                if key_name.isdigit():
                    key_name = f'numpad_{key_name}'

            if modifiers:
                combo = '+'.join(modifiers + [key_name])
            else:
                combo = key_name

            if len(combo) > 1 or key_name.startswith('f') and key_name[1:].isdigit():
                self._combo_detected.emit(combo)  # 安全跨线程发射

        except Exception as e:
            BM_LOG.error(f"处理按键事件出错: {e}")

    def _on_combo_received(self, combo):
        """主线程接收组合键"""
        self.on_key_pressed(combo)

    def on_key_pressed(self, key_name):
        """处理按键事件（始终在主线程执行）"""
        self.hotkey_label.setText(f'{key_name}')
        if self._conflict_check_fn:
            conflict_name = self._conflict_check_fn(key_name)
            if conflict_name:
                self._conflict_label.setText(
                    tr('快捷键已被 "{}"脚本占用').format(conflict_name))
                self._conflict_label.show()
            else:
                self._conflict_label.hide()

    def reset_hotkey(self):
        """重置快捷键"""
        self.hotkey_label.setText(tr("Press keys in sequence to set a shortcut"))
        self._conflict_label.hide()

    def save(self):
        self.handle_signal.emit((self.script_id, self.hotkey_label.text()))
        self.close()

    def start_monitor(self):
        """启动键盘监听（暂停全局热键）"""
        import keyboard as kb
        self._kb = kb
        self.stop_requested = False
        get_hotkey_manager().stop()
        self._keyboard_hook = self._kb.on_press(self._on_key_event)

    def stop_monitor(self):
        """停止键盘监听（恢复全局热键）"""
        self.stop_requested = True
        if self._keyboard_hook:
            self._kb.unhook(self._keyboard_hook)
            self._keyboard_hook = None
        get_hotkey_manager().start()

    def closeEvent(self, event):
        self.stop_monitor()
        super().closeEvent(event)

    def _create_ui(self):
        self.content = QFrame()
        self.layout = QVBoxLayout(self.content)
        self.layout.setContentsMargins(20,20,20,20)
        self.layout.addWidget(XLabel(tr('Configure Script Hotkeys'), style=XLabel.Style.H4).set_font_size(18))
        self.layout.addWidget(
            XLabel(tr('Press keys to set shortcut')).set_font_size(
                13).set_color(XColor.TERTIARY))
        self.hotkey_label = XLabel(self.hotkey_key).set_font_size(16)

        self.save_btn = XPushButton(tr('Save'))
        self.save_btn.clicked.connect(self.save)
        self.cancel_btn = XPushButton(tr('Cancel'), color=XColor.TERTIARY, variant=XButtonVariant.OUTLINED)
        self.cancel_btn.clicked.connect(self.window().close)
        self.reset_btn = XPushButton(tr('Reset'), color="success", variant=XButtonVariant.FILLED)
        self.reset_btn.clicked.connect(self.reset_hotkey)
        btn_layout = QHBoxLayout()

        btn_layout.addWidget(self.save_btn)
        btn_layout.addWidget(self.cancel_btn)


        self.layout.addStretch()
        self.layout.addWidget(self.hotkey_label, alignment=Qt.AlignCenter)
        self._conflict_label = XLabel('').set_font_size(12).set_color(XColor.DANGER)
        self._conflict_label.setAlignment(Qt.AlignCenter)
        self._conflict_label.hide()
        self.layout.addWidget(self._conflict_label)
        self.layout.addStretch()
        self.layout.addLayout(btn_layout)
        return self.content

