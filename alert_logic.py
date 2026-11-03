"""Pure Python state machine for three-stage face-touch feedback.

The CV detector still determines possible contact. This module only decides
how strongly to alert, and never claims that true physical contact occurred.
"""
from dataclasses import dataclass


@dataclass(frozen=True)
class AlertUpdate:
    stage: int  # 0=off, 1=initial, 2=stronger, 3=repeating
    entered_stage: bool  # True only once per stage/event, even after brief gaps
    elapsed: float  # approximate time since physical proximity began (seconds)


class AlertTimeline:
    def __init__(self, detection_hold=0.35, second_stage=1.5, third_stage=3.0):
        self.detection_hold = detection_hold
        self.second_stage = second_stage
        self.third_stage = third_stage
        self.reset()

    def reset(self):
        self.event_count = 0
        self.started_at = None
        self.highest_announced = 0
        self.stage = 0

    def update(self, now, event_count, contact_active, has_proximity):
        # A new accepted contact episode restarts its progression.
        if event_count != self.event_count:
            self.event_count = event_count
            # The detector already waited detection_hold before confirming.
            self.started_at = now - self.detection_hold
            self.highest_announced = 0

        # IMPORTANT: contact_active has a release hysteresis. We also require
        # live fingertip proximity to stop the alert on the first clear frame.
        if not (contact_active and has_proximity):
            self.stage = 0
            return AlertUpdate(0, False, 0.0)

        if self.started_at is None:
            # Fallback if attached in the middle of an already-active event.
            self.started_at = now - self.detection_hold

        elapsed = max(0.0, now - self.started_at)
        stage = 3 if elapsed >= self.third_stage else (2 if elapsed >= self.second_stage else 1)
        entered = stage > self.highest_announced
        if entered:
            self.highest_announced = stage
        self.stage = stage
        return AlertUpdate(stage, entered, elapsed)
