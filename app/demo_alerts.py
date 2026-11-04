"""Demo three-stage alerts WITHOUT opening the webcam.

Run: python -m app.demo_alerts
Start a simulated touch and release it from the small controls window.
Automatic safety cutoff is 9 seconds.
"""
import time

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication, QWidget, QVBoxLayout, QPushButton, QLabel

from alerts.alert_audio import AlertAudio
from alerts.alert_overlay import AlertOverlay
from alerts.alert_logic import AlertTimeline


class Demo(QWidget):
    def __init__(self, app):
        super().__init__()
        self.app = app
        self.overlay = AlertOverlay()
        self.audio = AlertAudio(volume=0.08)
        self.logic = AlertTimeline()
        self.counter = 0
        self.active = False
        self.muted = False
        self.started = 0.0

        self.setWindowTitle("Face Touch Guard | Alert demo")
        self.setMinimumWidth(310)
        layout = QVBoxLayout(self)
        self.label = QLabel("Start a simulated touch to preview the alerts.")
        layout.addWidget(self.label)
        start = QPushButton("Start simulated touch")
        stop = QPushButton("Release simulated touch")
        mute = QPushButton("Mute / unmute audio")
        quit_button = QPushButton("Quit")
        start.clicked.connect(self.start_touch)
        stop.clicked.connect(self.stop_touch)
        mute.clicked.connect(self.toggle_mute)
        quit_button.clicked.connect(self.close)
        for b in (start, stop, mute, quit_button):
            layout.addWidget(b)
        self.timer = QTimer(self)
        self.timer.setInterval(50)
        self.timer.timeout.connect(self.tick)
        self.timer.start()

    def start_touch(self):
        if self.active:
            return
        self.counter += 1
        self.active = True
        self.started = time.monotonic() - 0.35

    def stop_touch(self):
        self.active = False
        self.overlay.set_stage(0)
        self.audio.stop()
        self.label.setText("Released — sounds and overlay stopped")

    def toggle_mute(self):
        self.muted = not self.muted
        self.audio.set_muted(self.muted)
        self.label.setText("Audio muted" if self.muted else "Audio enabled")

    def tick(self):
        now = time.monotonic()
        if self.active and now - self.started >= 9:
            self.stop_touch()
            return
        feedback = self.logic.update(now, self.counter, self.active, self.active)
        old = self.overlay.stage
        self.overlay.set_stage(feedback.stage)
        if feedback.stage == 0 and old != 0:
            self.audio.stop()
        elif feedback.entered_stage:
            self.audio.play_stage(feedback.stage)
        self.label.setText(f"Alert stage: {feedback.stage} | Audio: {'muted' if self.muted else 'on'}")

    def closeEvent(self, event):
        self.timer.stop()
        self.stop_touch()
        self.overlay.close()
        self.audio.close()
        event.accept()


def main():
    app = QApplication([])
    demo = Demo(app)
    demo.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
