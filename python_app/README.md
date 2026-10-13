# Python application

Run from the project root after installing `python_app/requirements.txt`:

```powershell
python python_app/main.py --transport wifi --esp32-ip 192.168.1.100 --camera 0
python python_app/main.py --transport serial --port COM5 --camera 0
```

Wi-Fi is the default transport. Configure `SMART_GLOVE_ESP32_IP`, `SMART_GLOVE_ESP32_HTTP_PORT`, and `SMART_GLOVE_HTTP_TIMEOUT` with environment variables, or use the command-line options. `--transport serial` preserves the original USB protocol.

The model file must be at `../assets/models/hand_landmarker.task` relative to this directory. Tests are hardware-independent and run with:

```powershell
python -m unittest discover -s python_app/tests -v
```

The five live diagnostic rows show an interior joint angle in **degrees** from normalized MediaPipe x/y/z coordinates: thumb uses the angle at its IP joint (landmarks 2-3-4), and index/middle/ring/little use the angle at their PIP joint (MCP-PIP-DIP: 5-6-7, 9-10-11, 13-14-15, 17-18-19). A straight finger approaches 180 degrees; bending decreases the angle. These are image-space diagnostics, not calibrated physical or clinical angles. The angle is invariant to left/right image orientation because it is computed from vectors around each joint, while MediaPipe handedness remains shown in the overlay. Each finger has separate configurable hysteresis thresholds, defaulting to STRAIGHT at >=155 degrees and BENT at <=140 degrees, with the gap retaining the previous state and a short vote reducing flicker. Set `SMART_GLOVE_<FINGER>_STRAIGHT_ANGLE` and `SMART_GLOVE_<FINGER>_BENT_ANGLE` (for example `SMART_GLOVE_INDEX_STRAIGHT_ANGLE=160`) before launching to tune one finger. For calibration, hold each finger independently straight and bent for several seconds, note the displayed ranges, then choose each threshold pair between the observed ranges with a gap larger than normal jitter.

If no hand is detected, all current angle values are cleared and `NO HAND DETECTED` appears. To validate each finger, face the palm toward the webcam, keep the other fingers extended, then curl and straighten only the thumb, index, middle, ring, and little finger in turn. Confirm the selected finger's angle falls on bending and its state changes while other rows remain stable. Repeat with the other hand and adjust thresholds from actual webcam readings. Defaults are starting values and have not been validated against physical webcam input.
