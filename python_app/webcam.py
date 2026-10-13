"""OpenCV webcam loop and demonstration overlay."""
import cv2

from gesture_recognition import GestureStabilizer, classify_landmarks, finger_pattern
from config import FINGER_ANGLE_THRESHOLDS
from finger_analysis import FingerStateSmoother, measure_fingers

WINDOW_NAME = "Smart Glove Webcam"


def draw_landmarks(frame, landmarks) -> None:
    if not landmarks:
        return
    for point in landmarks:
        x = int(point.x * frame.shape[1])
        y = int(point.y * frame.shape[0])
        cv2.circle(frame, (x, y), 4, (70, 220, 160), -1)


def _finger_text(states) -> str:
    return f"PATTERN T I M R P: {finger_pattern(states)}"


def run_camera(config, detector, sender, stabilizer: GestureStabilizer) -> None:
    camera = None
    last_sent = ""
    finger_smoother = FingerStateSmoother(FINGER_ANGLE_THRESHOLDS)
    try:
        camera = cv2.VideoCapture(config.camera_index)
        if not camera.isOpened():
            raise RuntimeError(f"Unable to open webcam index {config.camera_index}")
        camera.set(cv2.CAP_PROP_FRAME_WIDTH, config.camera_width)
        camera.set(cv2.CAP_PROP_FRAME_HEIGHT, config.camera_height)

        while True:
            ok, frame = camera.read()
            if not ok:
                raise RuntimeError("Webcam returned no frame")
            frame = cv2.flip(frame, 1)
            landmarks = detector.detect(frame)
            result = classify_landmarks(landmarks, detector.last_handedness)
            if result.hand_detected and len(landmarks) >= 21:
                measurements = measure_fingers(landmarks)
                finger_states = finger_smoother.update(measurements)
            else:
                measurements = None
                finger_states = None
                finger_smoother.reset()
            stable, should_send = stabilizer.update(result.label)
            if should_send and stable != last_sent:
                pattern = finger_pattern(result.finger_states)
                if sender.send(stable, pattern):
                    last_sent = stable
            draw_landmarks(frame, landmarks)
            transport_text = "CONNECTED" if sender.status.connected else "DISCONNECTED"
            cv2.putText(frame, f"GESTURE: {stable}", (20, 35), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 255, 255), 2)
            cv2.putText(frame, f"HAND: {'DETECTED' if result.hand_detected else 'NO HAND'}", (20, 70), cv2.FONT_HERSHEY_SIMPLEX, 0.65, (70, 220, 160), 2)
            cv2.putText(frame, f"LAST COMMAND: {last_sent or '-'}", (20, 105), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (230, 230, 230), 1)
            cv2.putText(frame, f"ESP32: {transport_text} {sender.status.last_response}", (20, 135), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (230, 230, 230), 1)
            cv2.putText(frame, f"RAW: {result.label} | HAND: {result.handedness}", (20, 165), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (230, 230, 230), 1)
            cv2.putText(frame, _finger_text(result.finger_states), (20, 195), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (255, 210, 90), 1)
            reason = result.reason[:70]
            cv2.putText(frame, f"WHY: {reason}", (20, 225), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 210, 90), 1)
            if measurements is None:
                cv2.putText(frame, "NO HAND DETECTED", (20, 265), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (80, 80, 255), 2)
            else:
                for row, name in enumerate(("THUMB", "INDEX", "MIDDLE", "RING", "LITTLE")):
                    text = f"{name}: {measurements[name]:.0f} deg  {finger_states[name]}"
                    cv2.putText(frame, text, (20, 265 + row * 25), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (80, 230, 130) if finger_states[name] == "STRAIGHT" else (80, 180, 255), 2)
            cv2.putText(frame, "Q: quit | R: reconnect", (20, frame.shape[0] - 20), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (230, 230, 230), 1)
            cv2.imshow(WINDOW_NAME, frame)
            key = cv2.waitKey(1) & 0xFF
            if key in (ord("q"), 27):
                break
            if key == ord("r"):
                sender.close()
                sender.connect()
            try:
                if cv2.getWindowProperty(WINDOW_NAME, cv2.WND_PROP_VISIBLE) < 1:
                    break
            except cv2.error:
                break
    finally:
        if camera is not None:
            camera.release()
        cv2.destroyAllWindows()
