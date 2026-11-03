"""Face Touch Guard with three-stage audio + click-through desktop overlay.

Run: python main_alerts.py
"""
import time
from pathlib import Path

import cv2
import mediapipe as mp
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QAction, QFont, QIcon, QImage, QPainter, QPixmap, QShortcut, QKeySequence
from PySide6.QtWidgets import (
    QApplication, QHBoxLayout, QLabel, QMainWindow, QMenu,
    QPushButton, QSystemTrayIcon, QVBoxLayout, QWidget,
)

from alert_audio import AlertAudio
from alert_logic import AlertTimeline
from alert_overlay import AlertOverlay
from touch_detector_v2 import FaceTouchDetector


# Always match this to the webcam/backend in current main.py.
CAMERA_INDEX = 1
CAMERA_BACKEND = cv2.CAP_MSMF
MODEL_DIR = Path(__file__).resolve().parent / "models"
HAND_CONNECTIONS = [
    (0, 1), (1, 2), (2, 3), (3, 4),
    (0, 5), (5, 6), (6, 7), (7, 8),
    (5, 9), (9, 10), (10, 11), (11, 12),
    (9, 13), (13, 14), (14, 15), (15, 16),
    (13, 17), (17, 18), (18, 19), (19, 20),
    (0, 17),
]


def draw_hand(frame, landmarks):
    h, w = frame.shape[:2]
    pts = [(int(lm.x * w), int(lm.y * h)) for lm in landmarks]
    for a, b in HAND_CONNECTIONS:
        cv2.line(frame, pts[a], pts[b], (30, 220, 120), 2)
    for pt in pts:
        cv2.circle(frame, pt, 3, (0, 90, 255), -1)


def make_tray_icon():
    pix = QPixmap(64, 64)
    pix.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pix)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setBrush(Qt.GlobalColor.darkRed)
    painter.setPen(Qt.PenStyle.NoPen)
    painter.drawRoundedRect(5, 5, 54, 54, 14, 14)
    painter.setFont(QFont("Segoe UI", 31, QFont.Weight.Bold))
    painter.setPen(Qt.GlobalColor.white)
    painter.drawText(pix.rect(), Qt.AlignmentFlag.AlignCenter, "!")
    painter.end()
    return QIcon(pix)


class Preview(QMainWindow):
    def __init__(self, guard):
        super().__init__()
        self.guard = guard
        self.setWindowTitle("Face Touch Guard | Annoyance Mode")
        self.setMinimumWidth(520)
        self.setWindowIcon(make_tray_icon())
        container = QWidget()
        layout = QVBoxLayout(container)
        self.video = QLabel("Starting camera...")
        self.video.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.video.setMinimumSize(480, 340)
        self.video.setStyleSheet("background:#111827;color:white;border-radius:8px;")
        layout.addWidget(self.video)
        self.status = QLabel("Ready")
        layout.addWidget(self.status)
        buttons = QHBoxLayout()
        self.pause_button = QPushButton("Pause (P)")
        self.mute_button = QPushButton("Mute (M)")
        hide_button = QPushButton("Hide preview")
        hide_button.setEnabled(guard.has_tray)
        hide_button.setToolTip("Requires a Windows system tray icon")
        quit_button = QPushButton("Quit (Q)")
        self.pause_button.clicked.connect(guard.toggle_pause)
        self.mute_button.clicked.connect(guard.toggle_mute)
        hide_button.clicked.connect(self.hide)
        quit_button.clicked.connect(guard.shutdown)
        for button in (self.pause_button, self.mute_button, hide_button, quit_button):
            buttons.addWidget(button)
        layout.addLayout(buttons)
        self.setCentralWidget(container)
        for key, handler in (("P", guard.toggle_pause), ("M", guard.toggle_mute), ("Q", guard.shutdown)):
            shortcut = QShortcut(QKeySequence(key), self)
            shortcut.activated.connect(handler)
        self.resize(720, 630)

    def show_frame(self, rgb_frame):
        if not self.isVisible():
            return
        h, w, channels = rgb_frame.shape
        qimg = QImage(rgb_frame.data, w, h, w * channels, QImage.Format.Format_RGB888).copy()
        pixmap = QPixmap.fromImage(qimg)
        self.video.setPixmap(pixmap.scaled(
            self.video.size(),
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        ))

    def closeEvent(self, event):
        if self.guard.has_tray and not self.guard.stopping:
            self.hide()
            event.ignore()
        else:
            self.guard.shutdown()
            event.accept()


class Guard:
    def __init__(self, app):
        self.app = app
        self.stopping = False
        self.paused = False
        self.muted = False
        self.has_tray = QSystemTrayIcon.isSystemTrayAvailable()
        self.cap = None
        self.face_detector = None
        self.hand_detector = None
        self.timer = QTimer()
        self.timer.setInterval(35)
        self.timer.timeout.connect(self.process_frame)
        self.start_time = time.monotonic()
        self.last_timestamp_ms = -1

        # Keep the v2.2 geometric and temporal detector as-is.
        self.detector_settings = dict(
            margin_ratio=0.0,
            edge_margin_ratio=0.0,
            forehead_extension_ratio=0.20,
            hold_seconds=0.35,
            release_seconds=0.35,
            max_motion_ratio=0.10,
        )
        self.detector = FaceTouchDetector(**self.detector_settings)
        self.timeline = AlertTimeline(detection_hold=self.detector.hold_seconds)
        self.overlay = AlertOverlay()
        self.audio = AlertAudio(volume=0.08)
        self.preview = Preview(self)
        self.tray = None
        self.tray_pause = None
        self.tray_mute = None
        if self.has_tray:
            self.setup_tray()

        try:
            self.open_camera_and_models()
        except Exception:
            self.shutdown()
            raise
        self.preview.show()
        self.timer.start()

    def open_camera_and_models(self):
        self.cap = cv2.VideoCapture(CAMERA_INDEX, CAMERA_BACKEND)
        if not self.cap.isOpened():
            raise RuntimeError(
                "Camera unavailable. Copy the working VideoCapture index/backend "
                "from main.py into CAMERA_INDEX / CAMERA_BACKEND."
            )
        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)

        Vision = mp.tasks.vision
        BaseOptions = mp.tasks.BaseOptions
        self.face_detector = Vision.FaceLandmarker.create_from_options(
            Vision.FaceLandmarkerOptions(
                base_options=BaseOptions(model_asset_path=str(MODEL_DIR / "face_landmarker.task")),
                running_mode=Vision.RunningMode.VIDEO,
                num_faces=1,
            )
        )
        self.hand_detector = Vision.HandLandmarker.create_from_options(
            Vision.HandLandmarkerOptions(
                base_options=BaseOptions(model_asset_path=str(MODEL_DIR / "hand_landmarker.task")),
                running_mode=Vision.RunningMode.VIDEO,
                num_hands=2,
            )
        )

    def setup_tray(self):
        self.tray = QSystemTrayIcon(make_tray_icon(), self.app)
        self.tray.setToolTip("Face Touch Guard — monitoring")
        menu = QMenu()
        show_action = menu.addAction("Show camera preview")
        show_action.triggered.connect(self.restore_preview)
        self.tray_pause = menu.addAction("Pause detection")
        self.tray_pause.triggered.connect(self.toggle_pause)
        self.tray_mute = menu.addAction("Mute audio")
        self.tray_mute.triggered.connect(self.toggle_mute)
        menu.addSeparator()
        quit_action = menu.addAction("Quit")
        quit_action.triggered.connect(self.shutdown)
        self.tray.setContextMenu(menu)
        self.tray.activated.connect(self.tray_activated)
        self.tray.show()

    def tray_activated(self, reason):
        if reason == QSystemTrayIcon.ActivationReason.DoubleClick:
            self.restore_preview()

    def restore_preview(self):
        self.preview.show()
        self.preview.raise_()
        self.preview.activateWindow()

    def toggle_mute(self):
        self.muted = not self.muted
        self.audio.set_muted(self.muted)
        self.preview.mute_button.setText("Unmute (M)" if self.muted else "Mute (M)")
        if self.tray_mute:
            self.tray_mute.setText("Unmute audio" if self.muted else "Mute audio")
        # If unmuted during a continuing stage-3 contact, resume the buzzer.
        if not self.muted and self.timeline.stage == 3 and not self.paused:
            self.audio.play_stage(3)

    def toggle_pause(self):
        self.paused = not self.paused
        self.overlay.set_stage(0)
        self.audio.stop()
        if not self.paused:
            # Discard stale per-frame state after being paused, preserving count.
            old_count = self.detector.touch_count
            self.detector = FaceTouchDetector(**self.detector_settings)
            self.detector.touch_count = old_count
            self.timeline.reset()
            self.timeline.event_count = old_count
        self.preview.pause_button.setText("Resume (P)" if self.paused else "Pause (P)")
        self.preview.status.setText("PAUSED" if self.paused else "Monitoring")
        if self.tray_pause:
            self.tray_pause.setText("Resume detection" if self.paused else "Pause detection")
        if self.tray:
            self.tray.setToolTip("Face Touch Guard — paused" if self.paused else "Face Touch Guard — monitoring")

    def process_frame(self):
        if self.stopping or self.paused:
            return
        ok, frame = self.cap.read()
        if not ok:
            self.preview.status.setText("Camera frame unavailable — paused")
            self.toggle_pause()
            return
        frame = cv2.flip(frame, 1)
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)
        now = time.monotonic()
        timestamp_ms = max(int((now - self.start_time) * 1000), self.last_timestamp_ms + 1)
        self.last_timestamp_ms = timestamp_ms
        face_result = self.face_detector.detect_for_video(mp_image, timestamp_ms)
        hand_result = self.hand_detector.detect_for_video(mp_image, timestamp_ms)
        labels = [
            cats[0].category_name if cats else f"hand-{i}"
            for i, cats in enumerate(hand_result.handedness)
        ]
        polygon, near_tips, contact_active, _, count = self.detector.update(
            face_result.face_landmarks,
            hand_result.hand_landmarks,
            frame.shape,
            now,
            hand_labels=labels,
        )

        feedback = self.timeline.update(
            now=now,
            event_count=count,
            contact_active=contact_active,
            has_proximity=bool(near_tips),
        )
        old_stage = self.overlay.stage
        self.overlay.set_stage(feedback.stage)
        if feedback.stage == 0 and old_stage != 0:
            self.audio.stop()
        elif feedback.entered_stage:
            self.audio.play_stage(feedback.stage)
        elif feedback.stage == 3 and old_stage == 0 and not self.muted:
            # Restore repeating tone if proximity returns during same event.
            self.audio.play_stage(3)

        # The preview is optional: inference and alerts continue when hidden.
        if self.preview.isVisible():
            for face in face_result.face_landmarks:
                h, w = frame.shape[:2]
                for lm in face[::4]:
                    cv2.circle(frame, (int(lm.x * w), int(lm.y * h)), 1, (255, 255, 0), -1)
            for hand in hand_result.hand_landmarks:
                draw_hand(frame, hand)
            if polygon is not None:
                cv2.polylines(frame, [polygon], True,
                              (0, 0, 255) if near_tips else (255, 255, 0), 2)
            for tip in near_tips:
                cv2.circle(frame, tip, 10, (0, 0, 255), 2)
            cv2.putText(frame, f"Touch events: {count}  Alert stage: {feedback.stage}",
                        (12, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.68, (255, 255, 255), 2)
            rgb_preview = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            self.preview.show_frame(rgb_preview)
        self.preview.status.setText(
            f"Events: {count} | Stage: {feedback.stage} | "
            f"{'Muted' if self.muted else 'Audio on'}"
        )

    def shutdown(self):
        if self.stopping:
            return
        self.stopping = True
        self.timer.stop()
        self.overlay.close()
        self.audio.close()
        if self.face_detector:
            self.face_detector.close()
        if self.hand_detector:
            self.hand_detector.close()
        if self.cap is not None:
            self.cap.release()
        if self.tray:
            self.tray.hide()
        self.app.quit()


def main():
    app = QApplication([])
    app.setApplicationName("Face Touch Guard")
    app.setQuitOnLastWindowClosed(False)
    guard = None
    try:
        guard = Guard(app)
        return app.exec()
    finally:
        if guard is not None:
            guard.shutdown()


if __name__ == "__main__":
    raise SystemExit(main())
