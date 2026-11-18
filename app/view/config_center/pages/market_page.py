"""
Copyright (c) 2026 綦恒智
Email: bmscriptsbox@163.com
SPDX-License-Identifier: MIT
SPDX-License-Identifier: LicenseRef-Commons-Clause
"""
from app.cloud.view.market_ui.market_win import MarketWidget


class MarketPage(MarketWidget):
    """配置中心「脚本市场」页。"""

    def __init__(self, market_catalog=None, parent=None):
        super().__init__(parent=parent, market_catalog=market_catalog)

    def showEvent(self, event):
        super().showEvent(event)
        self.refresh()

    def shutdown(self):
        presenter = getattr(self, "presenter", None)
        stop = getattr(presenter, "shutdown", None)
        if callable(stop):
            stop()
