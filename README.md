# Face Touch Guard

**A local, privacy-conscious computer vision app that detects possible face-touching gestures and responds with escalating visual and audio feedback on Windows.**

> **Status:** Working Windows prototype. The current application combines the **V2.2 face-touch detector** with **Annoyance Mode** (desktop overlay, sounds, and system-tray controls). Detection accuracy has been measured for V1 and V2; V2.2 and the integrated alert experience have not yet undergone a new quantitative accuracy evaluation.

## Why build it?

Touching your face can be an unconscious habit while studying or working at a computer. If you're trying to reduce skin irritation, the challenge is often **not realizing that you're doing it**.

Face Touch Guard uses a laptop webcam to recognize *possible* hand-to-face contact and provide immediate feedback. Instead of passively displaying a notification, **Annoyance Mode** makes continued contact progressively more distracting, then stops when the hand moves away.

This is a small, exploratory computer vision and desktop-software project—not a medical tool or a definitive physical-contact sensor. A single RGB webcam observes a 2D scene, so hovering in front of the face can still be mistaken for contact.

## How it works

```text
Laptop webcam
    |
    v
OpenCV: capture / preprocess video frames
    |
    v
MediaPipe: face and hand landmarks
    |
    v
FaceTouchDetector V2.2
  - face polygon + forehead extension
  - fingertip proximity + relative motion
  - temporal confirmation + release hysteresis
    |
    v
AlertTimeline: duration of a confirmed proximity episode
    |
    +----> PySide6: click-through, always-on-top desktop overlay
    |
    +----> Windows audio: short / double / repeating beep
    |
    +----> Qt preview + system tray: preview, pause, mute, quit
```

| Component | Purpose and intuition |
| --- | --- |
| **Python** | Coordinates webcam inference, detection state, alerts, and application controls. |
| **OpenCV** | Reads webcam frames, converts color formats, draws debug visuals, and evaluates fingertip-to-face geometry with `pointPolygonTest`. |
| **MediaPipe Face Landmarker** | Supplies facial landmarks used to construct an approximate face region that follows head movement. |
| **MediaPipe Hand Landmarker** | Tracks 21 points per hand; fingertips become candidate contact points. |
| **NumPy** | Supports landmark coordinate and polygon calculations. |
| **`FaceTouchDetector` (V2.2)** | Applies geometric proximity, fingertip-specific motion constraints, dwell time, and event counting. |
| **`AlertTimeline`** | Converts detected contact duration into three escalating alert stages; it does not perform contact detection itself. |
| **PySide6 / Qt** | Draws the translucent click-through desktop overlay, runs the preview window, and provides system-tray controls. |
| **Windows `winsound`** | Plays locally generated, low-amplitude WAV cues asynchronously without intentionally blocking the processing loop. |

### Detection intuition

1. **Spatial proximity:** construct a polygon from facial landmarks and check whether a fingertip lies inside or near it.
2. **Forehead coverage:** the standard face oval only covered part of the visible forehead in testing; V2.2 extends the upper-central boundary toward the hairline without broadly expanding the cheek/ear region.
3. **Relative movement:** track fingertips individually and measure movement relative to the face, reducing false alerts when a hand passes quickly in front of it.
4. **Temporal confirmation:** require sustained proximity before counting an event; use release hysteresis so a brief tracking loss does not create duplicate events.
5. **Independent alert timing:** the visual/audio timeline responds to the detector's event and live proximity signals. Alerts stop on the first frame without proximity, even though the detector retains a short release delay for event-counting stability.

Current V2.2 defaults include approximately **350 ms confirmation**, **350 ms release hysteresis**, a **10%-of-face-width movement threshold**, and a **20%-of-face-width forehead extension**. These are configurable heuristics, not learned contact probabilities.

## Annoyance Mode: escalating alerts

Alerts escalate according to elapsed time **from the beginning of the detected proximity episode**. The first stage begins only after the detector confirms the event (normally after around 350 ms).

| Time from onset | Visual feedback | Audio feedback |
| --- | --- | --- |
| **0.35 s — Initial warning** | Orange desktop border and **“HANDS OFF!”** message | One short beep |
| **1.5 s — Continued contact** | Stronger red overlay and **“STILL TOUCHING?”** | Double beep |
| **3.0 s — Prolonged contact** | Most intense red overlay and **“REMOVE YOUR HAND!”** | Repeating buzzer |
| **Hand moves away** | Overlay disappears on the first clear detection frame | Sound stops, including the repeating buzzer |

The desktop overlay is **always on top but click-through**: it does not intentionally capture mouse clicks, typing, or keyboard focus. It uses a steady border and tint rather than flashing. Audio starts at a low amplitude, can be muted immediately, and remains subject to the Windows volume mixer.

**Implementation detail:** the underlying detector deliberately waits about 350 ms before ending a contact episode, which helps avoid duplicate counts. To avoid keeping an irritating alert on screen for that extra time, `AlertTimeline` also checks whether any fingertip is *currently* near the face (`near_tips`). A missed tracking frame can therefore briefly dismiss the overlay, even if the event has not yet ended internally.

## Early experiments

The detector was evaluated manually on **8 scenarios × 5 trials = 40 trials per version**: 20 intentional face touches and 20 non-touch gestures. A trial counted as detected if a new event was recorded. These are preliminary results from a small, manually conducted experiment—not an independent benchmark.

| Scenario (5 trials each) | Expected detections | V1 | V2 |
| --- | ---: | ---: | ---: |
| Touch left cheek | 5 | 5 | 5 |
| Touch right cheek | 5 | 5 | 5 |
| Touch forehead | 5 | 4 | 2 |
| Touch chin | 5 | 4 | 3 |
| Finger hovering near nose | 0 | 5 | 5 |
| Hand passing in front of face | 0 | 5 | 0 |
| Adjust hair without touching face | 0 | 2 | 0 |
| Rest hand beside ear | 0 | 4 | 1 |

| Metric | V1 | V2 |
| --- | ---: | ---: |
| True positives | 18 | 15 |
| False positives | 16 | 6 |
| False negatives | 2 | 5 |
| True negatives | 4 | 14 |
| **Precision** | **52.9%** | **71.4%** |
| **Recall** | **90.0%** | **75.0%** |
| **F1 score** | **66.7%** | **73.2%** |

**What changed:** V2's fingertip-specific motion checks and stricter boundaries eliminated hand-passing and hair-adjustment false positives in these trials, but reduced forehead/chin recall. Visual inspection showed that the face polygon did not cover the full forehead, motivating V2.2's upper-forehead extension.

**What is still unresolved:** stationary hovering near the nose produced **5/5 false alarms** with V2. The more complete forehead polygon looks better visually, but **no new precision/recall claims are made for V2.2 or Annoyance Mode**. More varied and independently labeled data will be needed to assess generalization.

## Getting started

### Requirements

- Windows 10 or 11 with a webcam (developed on Windows 11)
- Python **3.11 recommended** and an appropriate Python virtual environment
- Camera permission enabled in Windows settings
- The two MediaPipe `.task` model bundles downloaded locally

### 1. Clone the repository and prepare Python

```powershell
git clone <YOUR-REPOSITORY-URL>
cd face-touch-guard
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
```

### 2. Install dependencies

```powershell
python -m pip install opencv-python mediapipe numpy PySide6
```

Or, if the repository includes the alert implementation's requirements file:

```powershell
python -m pip install -r requirements-alerts.txt
```

`windows-toasts` was used in the earlier notification-only prototype, but **is not required by the integrated `main_alerts.py` application**; Annoyance Mode uses Qt and local sound cues instead.

### 3. Download the MediaPipe models

```powershell
New-Item -ItemType Directory -Force models

Invoke-WebRequest -Uri "https://storage.googleapis.com/mediapipe-models/face_landmarker/face_landmarker/float16/latest/face_landmarker.task" -OutFile "models\face_landmarker.task"

Invoke-WebRequest -Uri "https://storage.googleapis.com/mediapipe-models/hand_landmarker/hand_landmarker/float16/latest/hand_landmarker.task" -OutFile "models\hand_landmarker.task"
```

### 4. Run the integrated application

```powershell
python main_alerts.py
```

The preview displays the camera feed, tracked face/hand landmarks, touch-event counter, and active alert stage. You can **hide the preview while monitoring continues** via the system tray. If camera initialization fails, adjust these constants near the top of `main_alerts.py` to the index/backend that works for your webcam:

```python
CAMERA_INDEX = 0
CAMERA_BACKEND = cv2.CAP_MSMF
```

The older notification-only entry point (`python main.py`) can still be kept for comparison if it exists in your repository; the integrated app runs from **`main_alerts.py`**.

## Controls

| Control | Action |
| --- | --- |
| **P** (preview focused) | Pause / resume detection. Pausing stops the alert; resuming resets transient detector state while retaining the event count. |
| **M** (preview focused) | Mute / unmute audio. Visual alerts remain active. |
| **Q** (preview focused) | Quit and release the webcam. |
| **Hide preview** | Hide the camera window without stopping detection and alerts (requires an available system tray). |
| **Close preview (`X`)** | Hide to the tray when available; otherwise perform shutdown. |
| **Tray icon → Show camera preview** | Restore the preview. Double-clicking the icon also restores it. |
| **Tray icon → Pause / Resume** | Control monitoring without opening the preview. |
| **Tray icon → Mute / Unmute** | Toggle audio while retaining visual feedback. |
| **Tray icon → Quit** | Stop the application and release its resources. |

When the system tray is unavailable, keep the preview visible so you can access the controls and exit cleanly. The app does not currently install itself as a background service or auto-start with Windows.

## Testing

### A. Test the alerts without a webcam

```powershell
python demo_alerts.py
```

Click **Start simulated touch**, then observe the three stages at approximately 0.35 s, 1.5 s, and 3.0 s. Click **Release simulated touch** and confirm that the overlay and buzzer stop. You can also test the **Mute** button. The demo automatically stops the simulated touch after 9 seconds.

### B. Run automated alert-timeline tests

```powershell
python -m unittest -v test_alert_logic.py
```

The tests cover the escalation thresholds, stopping when current proximity disappears, avoiding replay after a brief tracking gap, resetting for a new event, and waiting for detector confirmation before alerting.

### C. Smoke-test the live application

1. Touch your cheek briefly: one event should be counted, followed by the orange border and initial beep.
2. Keep touching for 1.5 s and then 3 s: the visual and audio stages should escalate.
3. Move your hand away: overlay and sound should stop promptly; the event count should not repeatedly increment during one continuous gesture.
4. Press **M** while the alert is active: sound should stop, but the overlay should remain.
5. Press **P**, then resume: alerting should stop while paused and monitoring should restart afterward.
6. Hide the preview and use the tray to restore it or quit; the webcam should be released on exit.

For detection-accuracy evaluations, record **new event-counter increments**, not the presence of an older on-screen warning. Leave sufficient separation between trials and test both actual touches and hovering gestures.

## Project layout

```text
face-touch-guard/
├── main_alerts.py          # Integrated Qt app: webcam, preview, tray and alerts
├── touch_detector.py       # V2.2 geometric + temporal face-touch detector
├── alert_logic.py          # Three-stage alert timeline
├── alert_overlay.py        # Click-through desktop border and warning panel
├── alert_audio.py          # Locally generated Windows sounds
├── demo_alerts.py          # Demo without a webcam
├── test_alert_logic.py     # Automated tests for the alert state machine
├── requirements-alerts.txt # Dependencies for the integrated application
├── models/                 # Locally downloaded MediaPipe models
├── main.py                 # Optional earlier OpenCV/notification prototype
└── notifier.py             # Optional earlier native-toast notification module
```

The two older files are shown as **optional**: the integrated entry point does not depend on them.

## Privacy, limitations and safety

- **Local processing:** webcam frames are processed on the device. The application does not intentionally record, save, or upload video.
- **Not proof of contact:** visually similar hovering gestures may still trigger, especially in front of the nose.
- **Variable performance:** accuracy depends on lighting, camera angle, head movement, hand occlusion, and inference speed.
- **Small evaluation:** the measured percentages come from limited manual trials and should not be assumed to hold for other users or environments.
- **Feedback is adjustable:** audio can be muted, monitoring can be paused, and the application can be exited. The overlay does not deliberately flash or block input.
- **Performance consideration:** webcam processing and the Qt interface currently share an event loop, so slow inference could delay UI and alert updates.
- **Displays:** desktop overlays are initialized for monitors connected at launch; restart the application after changing monitor connections.
- **No persistence yet:** the touch counter is session-based, not a stored long-term behavioral history.

## Next steps

- Evaluate V2.2 on a larger set of true touches and difficult non-touch gestures.
- Explore better discrimination between physical contact and stationary hovering.
- Add optional local statistics (daily counts, touch-free streaks) without retaining video.
- Improve responsiveness by moving inference off the Qt UI thread if needed.
- Package the application as a standalone Windows executable and optionally support startup on login.

---

*An exploratory project for learning real-time computer vision, behavior detection, and native desktop integration—while building a useful everyday tool.*
