import time
from pathlib import Path
from detection.touch_detector_v2 import FaceTouchDetector
from legacy.notifier import TouchNotifier

import cv2
import mediapipe as mp


# Paths to the pretrained models
MODEL_DIR = Path(__file__).resolve().parent.parent / "models"

# Connections between hand joints (MediaPipe indices)
HAND_CONNECTIONS = [
    (0, 1), (1, 2), (2, 3), (3, 4),
    (0, 5), (5, 6), (6, 7), (7, 8),
    (5, 9), (9, 10), (10, 11), (11, 12),
    (9, 13), (13, 14), (14, 15), (15, 16),
    (13, 17), (17, 18), (18, 19), (19, 20),
    (0, 17)
]


def to_pixel(landmark, width, height):
    """Convert normalized coordinates into pixel coordinates."""
    return (
        int(landmark.x * width),
        int(landmark.y * height)
    )


def draw_face(frame, face_landmarks):
    height, width = frame.shape[:2]

    # Draw a subset of facial landmarks to avoid visual clutter
    for landmark in face_landmarks[::4]:
        x, y = to_pixel(landmark, width, height)
        cv2.circle(frame, (x, y), 1, (255, 255, 0), -1)


def draw_hand(frame, hand_landmarks):
    height, width = frame.shape[:2]

    points = [
        to_pixel(lm, width, height)
        for lm in hand_landmarks
    ]

    # Connect the hand joints
    for start, end in HAND_CONNECTIONS:
        cv2.line(
            frame, points[start], points[end],
            (0, 255, 0), 2
        )

    # Draw all 21 hand landmarks
    for point in points:
        cv2.circle(frame, point, 4, (0, 0, 255), -1)


def main():
    BaseOptions = mp.tasks.BaseOptions
    Vision = mp.tasks.vision

    face_options = Vision.FaceLandmarkerOptions(
        base_options=BaseOptions(
            model_asset_path=str(MODEL_DIR / "face_landmarker.task")
        ),
        running_mode=Vision.RunningMode.VIDEO,
        num_faces=1
    )

    hand_options = Vision.HandLandmarkerOptions(
        base_options=BaseOptions(
            model_asset_path=str(MODEL_DIR / "hand_landmarker.task")
        ),
        running_mode=Vision.RunningMode.VIDEO,
        num_hands=2
    )

    with (
        Vision.FaceLandmarker.create_from_options(face_options) as face_detector,
        Vision.HandLandmarker.create_from_options(hand_options) as hand_detector
    ):
        # Camera index/backend
        cap = cv2.VideoCapture(1, cv2.CAP_MSMF)

        if not cap.isOpened():
            raise RuntimeError("Unable to access webcam.")

        start_time = time.monotonic()
        last_timestamp_ms = -1
        touch_detector = FaceTouchDetector()
        notifier = TouchNotifier(cooldown_seconds=8.0)

        try:
            while True:
                success, frame = cap.read()

                if not success:
                    break

                frame = cv2.flip(frame, 1)

                # OpenCV uses BGR, while MediaPipe expects RGB.
                rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

                mp_image = mp.Image(
                    image_format=mp.ImageFormat.SRGB,
                    data=rgb_frame
                )

                # Each video frame needs an increasing timestamp.
                elapsed_ms = int(
                    (time.monotonic() - start_time) * 1000
                )
                timestamp_ms = max(
                    elapsed_ms, last_timestamp_ms + 1
                )
                last_timestamp_ms = timestamp_ms

                # Run the two detectors
                face_result = face_detector.detect_for_video(
                    mp_image, timestamp_ms
                )
                hand_result = hand_detector.detect_for_video(
                    mp_image, timestamp_ms
                )

                # Visualize detected faces
                for face in face_result.face_landmarks:
                    draw_face(frame, face)

                # Visualize detected hands
                for hand in hand_result.hand_landmarks:
                    draw_hand(frame, hand)

                hand_labels = [
                    categories[0].category_name
                    if categories else f"hand-{i}"
                    for i, categories in enumerate(hand_result.handedness)
                ]

                previous_count = touch_detector.touch_count

                # Analyze face-hand proximity.
                (
                    face_polygon,
                    near_tips,
                    contact_active,
                    show_alert,
                    touch_count
                ) = touch_detector.update(
                    face_result.face_landmarks,
                    hand_result.hand_landmarks,
                    frame.shape,
                    time.monotonic(),
                    hand_labels=hand_labels
                )

                if touch_count > previous_count:
                    now = time.monotonic()

                    notification_sent = notifier.notify(
                        event_count=touch_count,
                        now=now
                    )

                    print(
                        f"[{time.strftime('%H:%M:%S')}] "
                        f"New face-touch event #{touch_count}"
                        f"Notification: {notification_sent}"
                    )

                
                # Explain the detector's current state.
                if not face_result.face_landmarks:
                    detector_state = "FACE NOT TRACKED"
                elif contact_active:
                    detector_state = "CONTACT CONFIRMED"
                elif touch_detector.candidate_since is not None:
                    detector_state = "CANDIDATE"
                else:
                    detector_state = "CLEAR"

                debug_text = (
                    f"State: {detector_state} | "
                    f"Nearby fingertips: {len(near_tips)}"
                )

                cv2.putText(
                    frame,
                    debug_text,
                    (20, 145),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.55,
                    (0, 255, 255),
                    2
                )


                # Draw the face boundary.
                if face_polygon is not None:
                    color = (0, 0, 255) if near_tips else (255, 255, 0)

                    cv2.polylines(
                        frame,
                        [face_polygon],
                        isClosed=True,
                        color=color,
                        thickness=2
                    )

                # Highlight fingertips entering the face region.
                for tip in near_tips:
                    cv2.circle(
                        frame, tip, 10,
                        (0, 0, 255), 2
                    )

                # Show a warning for 1.5 seconds after a confirmed event.
                if show_alert:
                    cv2.rectangle(
                        frame, (10, 65), (410, 115),
                        (0, 0, 180), -1
                    )

                    cv2.putText(
                        frame,
                        "POSSIBLE FACE TOUCH!",
                        (20, 98),
                        cv2.FONT_HERSHEY_SIMPLEX,
                        0.8, (255, 255, 255), 2
                    )

                # Display the number of detected events.
                cv2.putText(
                    frame,
                    f"Touch events: {touch_count}",
                    (20, frame.shape[0] - 20),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.7, (255, 255, 255), 2
                )


                # Show tracking status
                status = (
                    f"Faces: {len(face_result.face_landmarks)} | "
                    f"Hands: {len(hand_result.hand_landmarks)}"
                )

                cv2.putText(
                    frame, status, (20, 40),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.7, (0, 255, 0), 2
                )

                cv2.imshow("Face Touch Guard", frame)

                if cv2.waitKey(1) & 0xFF == ord("q"):
                    break

        finally:
            cap.release()
            cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
