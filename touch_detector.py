import cv2
import numpy as np


# Ordered landmark indices describing the face outline.
FACE_OVAL = [
    10, 338, 297, 332, 284, 251, 389, 356, 454,
    323, 361, 288, 397, 365, 379, 378, 400, 377,
    152, 148, 176, 149, 150, 136, 172, 58, 132,
    93, 234, 127, 162, 21, 54, 103, 67, 109
]

# Thumb, index, middle, ring, and pinky fingertips.
FINGERTIPS = (4, 8, 12, 16, 20)


class FaceTouchDetector:
    def __init__(
        self,
        margin_ratio=0.03,
        hold_seconds=0.25,
        release_seconds=0.35
    ):
        self.margin_ratio = margin_ratio
        self.hold_seconds = hold_seconds
        self.release_seconds = release_seconds

        self.candidate_since = None
        self.release_since = None
        self.contact_active = False

        self.touch_count = 0
        self.alert_until = 0.0

    def update(
        self,
        faces,
        hands,
        frame_shape,
        now
    ):
        height, width = frame_shape[:2]
        polygon = None
        near_fingertips = []

        # 1. Build the face polygon.
        if faces:
            face = faces[0]

            polygon = np.array([
                [
                    int(face[idx].x * width),
                    int(face[idx].y * height)
                ]
                for idx in FACE_OVAL
            ], dtype=np.int32)

            # Scale the tolerance with the face size.
            face_width = float(
                np.ptp(polygon[:, 0])
            )
            margin_px = max(
                3.0,
                face_width * self.margin_ratio
            )

            # 2. Test each fingertip against the polygon.
            for hand in hands:
                for idx in FINGERTIPS:
                    tip = hand[idx]

                    x = int(tip.x * width)
                    y = int(tip.y * height)

                    signed_distance = cv2.pointPolygonTest(
                        polygon,
                        (float(x), float(y)),
                        True
                    )

                    if signed_distance >= -margin_px:
                        near_fingertips.append((x, y))

        # 3. Is any fingertip near the face?
        is_near = len(near_fingertips) > 0

        # 4. Confirm sustained proximity.
        if is_near:
            self.release_since = None

            if not self.contact_active:
                if self.candidate_since is None:
                    self.candidate_since = now

                elif now - self.candidate_since >= self.hold_seconds:
                    self.contact_active = True
                    self.candidate_since = None
                    self.touch_count += 1
                    self.alert_until = now + 1.5

        else:
            self.candidate_since = None

            # End an episode only after sustained separation.
            if self.contact_active:
                if self.release_since is None:
                    self.release_since = now

                elif now - self.release_since >= self.release_seconds:
                    self.contact_active = False
                    self.release_since = None

        show_alert = now < self.alert_until

        return (
            polygon,
            near_fingertips,
            self.contact_active,
            show_alert,
            self.touch_count
        )
