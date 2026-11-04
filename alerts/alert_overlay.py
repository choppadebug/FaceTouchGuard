"""A full-desktop, transparent and mouse-click-through Qt alert overlay."""
from PySide6.QtCore import Qt, QRectF
from PySide6.QtGui import QColor, QFont, QPainter, QPen
from PySide6.QtWidgets import QApplication, QWidget


class _ScreenOverlay(QWidget):
    def __init__(self, screen):
        flags = (
            Qt.WindowType.Tool
            | Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.WindowTransparentForInput
            | Qt.WindowType.WindowDoesNotAcceptFocus
        )
        super().__init__(None, flags)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating, True)
        self._screen = screen
        self._stage = 0
        self.setGeometry(screen.geometry())
        self.hide()

    def set_stage(self, stage):
        if stage == self._stage:
            return
        self._stage = stage
        if stage == 0:
            self.hide()
        else:
            self.setGeometry(self._screen.geometry())
            self.show()
            self.update()

    def paintEvent(self, event):
        if not self._stage:
            return
        stage = self._stage
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        r = self.rect().adjusted(1, 1, -2, -2)

        # Never flash: a steadily intensified border/tint is easier to tolerate.
        tint_alpha = (0, 28, 55, 83)[stage]
        p.fillRect(r, QColor(105, 9, 18, tint_alpha))
        border_color = QColor("#f59e0b") if stage == 1 else QColor("#ef4444")
        border_px = (0, 9, 17, 26)[stage]
        p.setPen(QPen(border_color, border_px))
        p.setBrush(Qt.BrushStyle.NoBrush)
        inset = border_px // 2 + 2
        p.drawRect(r.adjusted(inset, inset, -inset, -inset))

        labels = {
            1: ("HANDS OFF!", "Possible face touch detected"),
            2: ("STILL TOUCHING?", "Move your hand away"),
            3: ("REMOVE YOUR HAND!", "Alert continues until you release"),
        }
        headline, subline = labels[stage]
        w = self.width()
        h = self.height()
        box_width = min(560, max(260, w - 70))
        box_height = 118 if h > 250 else 90
        panel = QRectF((w - box_width) / 2, max(20, h * 0.15), box_width, box_height)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(16, 22, 34, 230))
        p.drawRoundedRect(panel, 18, 18)
        p.setFont(QFont("Segoe UI", 21 if w > 750 else 15, QFont.Weight.Bold))
        p.setPen(QColor("#ffffff"))
        p.drawText(panel.adjusted(12, 13, -12, -44), Qt.AlignmentFlag.AlignCenter, headline)
        p.setFont(QFont("Segoe UI", 11))
        p.setPen(QColor("#fca5a5"))
        p.drawText(panel.adjusted(10, 65, -10, -8), Qt.AlignmentFlag.AlignCenter, subline)
        p.end()


class AlertOverlay:
    def __init__(self):
        self.windows = [_ScreenOverlay(s) for s in QApplication.screens()]
        self.stage = 0

    def set_stage(self, stage):
        stage = int(stage)
        if stage == self.stage:
            return
        self.stage = stage
        for window in self.windows:
            window.set_stage(stage)

    def close(self):
        self.set_stage(0)
        for window in self.windows:
            window.close()
