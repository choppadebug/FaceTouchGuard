# Face Touch Guard

**A lightweight, privacy-conscious computer vision application that detects possible face-touching gestures through a laptop webcam and provides real-time Windows notifications.**

> **Status:** Working local prototype (v2.2 detection baseline). The app currently runs in an OpenCV preview window; a system-tray/background interface is not implemented yet.

## Motivation

Touching your face can be an unconscious habit, especially while studying or working at a computer. For people trying to avoid irritating their skin, the difficult part is often **not noticing when the gesture happens**.

Face Touch Guard explores a simple idea: can a laptop webcam recognize hand-to-face gestures in real time and provide immediate, unobtrusive feedback?

The goal is **habit awareness**, not medical diagnosis or definitive proof of physical contact. A single RGB camera sees a 2D projection of the scene, so a finger hovering in front of the face can sometimes look identical to a genuine touch.

## How it works

```text
Laptop webcam
    |
    v
OpenCV: capture and preprocess frames
    |
    v
MediaPipe: face + hand landmarks
    |
    v
Geometric proximity + movement/dwell checks
    |
    v
New possible face-touch event
    |                  \
    v                   v
On-screen warning    Windows notification (with cooldown)
```

| Component | Role / intuition |
| --- | --- |
| **Python** | Application logic and coordination of the processing loop. |
| **OpenCV** | Reads webcam frames, converts color formats, draws debugging overlays, and checks geometric relationships. |
| **MediaPipe Face Landmarker** | Locates facial landmarks so we can construct an approximate face region rather than relying on a fixed screen area. |
| **MediaPipe Hand Landmarker** | Tracks 21 landmarks per hand; fingertip positions are candidates for face contact. |
| **NumPy** | Handles landmark coordinates and face-region geometry. |
| **Custom `FaceTouchDetector`** | Tests fingertips against a face polygon, tracks each candidate over time, and counts separate contact-like episodes. |
| **Windows-Toasts** | Displays a native Windows notification when a new event occurs, with an independent notification cooldown. |

### Detection intuition

1. **Spatial proximity.** A polygon built from facial landmarks defines the region of interest. OpenCV's `pointPolygonTest` checks whether a fingertip lies inside or near it.
2. **Forehead coverage.** The standard face oval did not cover the full visible forehead in testing. In v2.2, the upper-center of the polygon is extended toward the hairline without broadening the cheek/ear regions.
3. **Motion stability.** Fingertips are tracked individually, with movement measured *relative to the face*, reducing false alerts from hands quickly passing in front of the camera.
4. **Temporal confirmation.** Proximity must persist for a short dwell period before an event is counted. A release period prevents counting one continuous touch repeatedly.
5. **Notification throttling.** Every accepted event increments the counter, but desktop notifications have their own cooldown to avoid spamming the user.

These checks are **heuristics**, not a trained contact classifier. Current baseline settings include approximately **350 ms** dwell, **350 ms** release, a maximum candidate displacement of **10% of face width**, and a forehead extension of **20% of face width**. They are configurable in `FaceTouchDetector`.

## Early experiments

We ran a small manual evaluation with **8 scenarios × 5 trials = 40 trials per version**: 20 actual touches and 20 non-touch gestures. A trial was considered *detected* if it produced a new event. These figures are exploratory, not a benchmark on an independent dataset.

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
| True positives (TP) | 18 | 15 |
| False positives (FP) | 16 | 6 |
| False negatives (FN) | 2 | 5 |
| True negatives (TN) | 4 | 14 |
| **Precision** | **52.9%** | **71.4%** |
| **Recall** | **90.0%** | **75.0%** |
| **F1 score** | **66.7%** | **73.2%** |

**What we learned:** adding fingertip-specific motion stability and stricter geometric boundaries eliminated fly-by and hair-adjustment false alarms in this test, but reduced detection of forehead and chin touches. Inspection revealed that the original blue face outline covered only part of the forehead. **V2.2 extends that region**, improving its visual coverage; quantitative accuracy for V2.2 has **not yet been measured**.

**Known limitation:** a stationary finger hovering near the nose still triggered 5/5 false alarms in the V2 evaluation. A monocular RGB webcam cannot reliably establish physical contact from 2D landmarks alone. More data or richer cues will be needed to address this.

## Getting started

### Requirements

- Windows 10/11 with a working webcam (developed and tested on Windows 11)
- Python 3.11 recommended
- Camera access enabled under Windows privacy settings

### 1. Clone and create a virtual environment

```powershell
git clone <YOUR-REPOSITORY-URL>
cd face-touch-guard
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
```

### 2. Install dependencies

```powershell
python -m pip install opencv-python mediapipe numpy windows-toasts
```

### 3. Download the MediaPipe models

Create the `models` directory and download the official `.task` model bundles:

```powershell
New-Item -ItemType Directory -Force models

Invoke-WebRequest -Uri "https://storage.googleapis.com/mediapipe-models/face_landmarker/face_landmarker/float16/latest/face_landmarker.task" -OutFile "models\face_landmarker.task"

Invoke-WebRequest -Uri "https://storage.googleapis.com/mediapipe-models/hand_landmarker/hand_landmarker/float16/latest/hand_landmarker.task" -OutFile "models\hand_landmarker.task"
```

### 4. Run the app

```powershell
python main.py
```

The application opens a webcam preview with face/hand landmarks, detection status, and an event counter. On a new possible touch, it displays a warning in the preview and submits a Windows notification, subject to the notification cooldown.

- **Quit:** focus the preview window and press `Q`.
- **Keep monitoring while multitasking:** minimize the preview window; keep the Python process running.
- **Camera not detected?** Check camera privacy settings and adjust the camera index or backend in `cv2.VideoCapture(...)` inside `main.py`.
- **No notification banner?** Check Windows Notifications and Do Not Disturb settings.

The app **does not currently** have a tray icon, automatic startup, or a fully headless background mode. Close it using `Q` so the camera is released cleanly.

## Project files

```text
face-touch-guard/
├── main.py                  # Webcam loop, MediaPipe inference, overlays
├── touch_detector.py        # Geometry, motion, temporal state and event count
├── notifier.py              # Native Windows notifications and cooldown
├── models/                  # Downloaded MediaPipe .task model files
└── test_notification.py     # Optional notification smoke test
```

## Privacy and limitations

- Video processing is local; the current prototype does not upload or intentionally save webcam footage.
- The current application does not persist touch history across sessions.
- Notifications are based on **possible** contact, not verified skin contact.
- Accuracy depends on camera position, lighting, occlusion, and individual behavior.
- The initial evaluation consists of a small number of manually performed trials by one tester; it should not be interpreted as generalizable accuracy.

## Possible next steps

- System-tray controls (pause/resume/quit) and an optional hidden preview
- Local, privacy-preserving event statistics
- Better discrimination between true contact and stationary hovering
- Evaluation with labeled touch/non-touch samples and more varied conditions
- Packaging as a Windows executable

---

*An exploratory project to learn real-time computer vision while building a useful everyday tool.*
