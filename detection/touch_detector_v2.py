"""Face Touch Guard v2.2: extended forehead detection region.

Extend only the upper-center of the face polygon; preserve existing
fingertip motion and dwell logic. Avoid a second forehead margin by default.
"""
import math

import cv2
import numpy as np

FACE_OVAL = [
    10, 338, 297, 332, 284, 251, 389, 356, 454,
    323, 361, 288, 397, 365, 379, 378, 400, 377,
    152, 148, 176, 149, 150, 136, 172, 58, 132,
    93, 234, 127, 162, 21, 54, 103, 67, 109
]
FINGERTIPS = (4, 8, 12, 16, 20)


def build_face_polygon(face, width, height, forehead_extension_ratio=0.20):
    """Extend the upper central oval without widening the cheek/ear boundary.

    Extension direction follows the brow-to-upper-forehead vector, so the
    patch stays approximately aligned with a tilted head in image space.
    This is a heuristic ROI, not a hairline or skin segmentation model.
    """
    polygon = np.array(
        [
            (round(face[idx].x * width), round(face[idx].y * height))
            for idx in FACE_OVAL
        ],
        dtype=np.int32,
    )
    face_width = max(1.0, float(np.ptp(polygon[:, 0])))

    upper = np.array(
        [face[10].x * width, face[10].y * height], dtype=float
    )
    brow_center = np.array(
        [
            (face[70].x + face[300].x) * width / 2,
            (face[70].y + face[300].y) * height / 2,
        ],
        dtype=float,
    )
    direction = upper - brow_center
    length = float(np.linalg.norm(direction))
    direction = direction / length if length > 1 else np.array([0., -1.])

    shift = forehead_extension_ratio * face_width * direction
    n = len(polygon)
    weights = {
        0: 1.00,
        1: 0.80, n - 1: 0.80,
        2: 0.55, n - 2: 0.55,
        3: 0.20, n - 3: 0.20,
    }
    for index, weight in weights.items():
        polygon[index] = np.rint(polygon[index] + shift * weight).astype(np.int32)
    polygon[:, 0] = np.clip(polygon[:, 0], 0, width - 1)
    polygon[:, 1] = np.clip(polygon[:, 1], 0, height - 1)
    return polygon


class FaceTouchDetector:
    def __init__(
        self,
        margin_ratio=0.0,
        hold_seconds=0.35,
        release_seconds=0.35,
        max_motion_ratio=0.10,
        edge_margin_ratio=0.0,
        edge_band_ratio=0.22,
        forehead_extension_ratio=0.20,
    ):
        self.margin_ratio = margin_ratio
        self.hold_seconds = hold_seconds
        self.release_seconds = release_seconds
        self.max_motion_ratio = max_motion_ratio
        self.edge_margin_ratio = edge_margin_ratio
        self.edge_band_ratio = edge_band_ratio
        self.forehead_extension_ratio = forehead_extension_ratio

        self.candidates = {}
        self.candidate_since = None
        self.release_since = None
        self.contact_active = False
        self.touch_count = 0
        self.alert_until = 0.0
        self.debug = {}

    def update(self, faces, hands, frame_shape, now, hand_labels=None):
        height, width = frame_shape[:2]
        polygon = None
        near_fingertips = []
        current_candidates = {}
        edge_margin_hits = 0
        motion_resets = 0

        if faces:
            polygon = build_face_polygon(
                faces[0], width, height, self.forehead_extension_ratio
            )

            min_x, max_x = polygon[:, 0].min(), polygon[:, 0].max()
            min_y, max_y = polygon[:, 1].min(), polygon[:, 1].max()
            face_width = max(1.0, float(max_x - min_x))
            face_height = max(1.0, float(max_y - min_y))
            center_x, center_y = polygon.mean(axis=0)
            bbox_center_x = (float(min_x) + float(max_x)) / 2.0

            for hand_i, hand in enumerate(hands):
                hand_id = (
                    hand_labels[hand_i]
                    if hand_labels is not None and hand_i < len(hand_labels)
                    else f"hand-{hand_i}"
                )

                for finger_i in FINGERTIPS:
                    tip = hand[finger_i]
                    x, y = int(tip.x * width), int(tip.y * height)

                    # Apply the extra margin only near the central forehead
                    # or central chin, not near the temples or ears.
                    upper = (
                        y <= min_y + self.edge_band_ratio * face_height
                        and abs(x - bbox_center_x) <= 0.36 * face_width
                    )
                    lower = (
                        y >= max_y - self.edge_band_ratio * face_height
                        and abs(x - bbox_center_x) <= 0.32 * face_width
                    )
                    use_edge_margin = upper or lower
                    margin_ratio = (
                        self.edge_margin_ratio if use_edge_margin
                        else self.margin_ratio
                    )
                    margin_px = face_width * margin_ratio
                    signed_distance = cv2.pointPolygonTest(
                        polygon, (float(x), float(y)), True
                    )
                    if signed_distance < -margin_px:
                        continue

                    if use_edge_margin and signed_distance < 0:
                        edge_margin_hits += 1
                    near_fingertips.append((x, y))
                    key = (hand_id, finger_i)
                    relative_pos = (
                        (x - center_x) / face_width,
                        (y - center_y) / face_width,
                    )
                    old = self.candidates.get(key)
                    if old is None:
                        current_candidates[key] = (now, relative_pos)
                    else:
                        stable_since, origin = old
                        displacement = math.dist(relative_pos, origin)
                        if displacement > self.max_motion_ratio:
                            motion_resets += 1
                            current_candidates[key] = (now, relative_pos)
                        else:
                            current_candidates[key] = (stable_since, origin)

        self.candidates = current_candidates
        is_near = bool(near_fingertips)

        candidate_ages = [now - started for started, _ in self.candidates.values()]
        self.debug = {
            "near_tips": len(near_fingertips),
            "edge_margin_hits": edge_margin_hits,
            "motion_resets": motion_resets,
            "longest_candidate_ms": int(1000 * max(candidate_ages, default=0.0)),
        }

        if not self.contact_active:
            self.candidate_since = min(
                (started for started, _ in self.candidates.values()),
                default=None,
            )
            if any(
                now - started >= self.hold_seconds
                for started, _ in self.candidates.values()
            ):
                self.contact_active = True
                self.candidate_since = None
                self.touch_count += 1
                self.alert_until = now + 1.5
                self.release_since = None
        else:
            if is_near:
                self.release_since = None
            elif self.release_since is None:
                self.release_since = now
            elif now - self.release_since >= self.release_seconds:
                self.contact_active = False
                self.release_since = None

        return (
            polygon,
            near_fingertips,
            self.contact_active,
            now < self.alert_until,
            self.touch_count,
        )
