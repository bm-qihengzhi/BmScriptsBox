"""
Copyright (c) 2026 綦恒智
Email: bmscriptsbox@163.com
SPDX-License-Identifier: AGPL-3.0
"""
from PySide2.QtCore import QObject, Signal

# 跨线程通信信号
class MouseSignals(QObject):
    click_outside = Signal()