"""
Copyright (c) 2026 綦恒智
Email: bmscriptsbox@163.com
SPDX-License-Identifier: MIT
SPDX-License-Identifier: LicenseRef-Commons-Clause

用缓存 pixmap + 绘制透明度实现淡出，替代 QGraphicsOpacityEffect。
QGraphicsOpacityEffect 每帧都要把整个子树离屏合成，成本远高于直接绘制一张静态图。
"""
from PySide6.QtCore import Property, QEasingCurve, QPropertyAnimation, Qt
from PySide6.QtGui import QPainter, QPixmap
from PySide6.QtWidgets import QWidget


class FadeOverlay(QWidget):
    """覆盖在目标控件上方的淡出层"""

    def __init__(self, pixmap: QPixmap, parent=None):
        super().__init__(parent)
        self._pixmap = pixmap
        self._opacity = 1.0
        self._anim = None
        self.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        self.setAttribute(Qt.WA_NoSystemBackground, True)
        self.setFocusPolicy(Qt.NoFocus)

    def _get_opacity(self) -> float:
        return self._opacity

    def _set_opacity(self, value: float) -> None:
        self._opacity = value
        self.update()

    opacity = Property(float, _get_opacity, _set_opacity)

    def paintEvent(self, event) -> None:
        if self._pixmap.isNull():
            return
        painter = QPainter(self)
        painter.setOpacity(self._opacity)
        painter.drawPixmap(self.rect(), self._pixmap)

    def fade_out(self, duration: int = 180,
                 easing=QEasingCurve.OutCubic) -> None:
        """淡出并在结束后自动销毁"""
        anim = QPropertyAnimation(self, b"opacity", self)
        anim.setDuration(duration)
        anim.setStartValue(1.0)
        anim.setEndValue(0.0)
        anim.setEasingCurve(easing)
        anim.finished.connect(self._on_finished)
        self._anim = anim
        anim.start()

    def cancel(self) -> None:
        """立即停止动画并销毁"""
        if self._anim is not None:
            try:
                self._anim.stop()
            except RuntimeError:
                pass
            self._anim = None
        self.hide()
        self.deleteLater()

    def _on_finished(self) -> None:
        self._anim = None
        self.hide()
        self.deleteLater()
