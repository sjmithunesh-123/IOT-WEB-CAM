import { useEffect, useRef, useState } from 'react';
import { FilesetResolver, HandLandmarker } from '@mediapipe/tasks-vision';

type CameraStatus = 'idle' | 'starting' | 'active' | 'error';
type DeviceState = 'unknown' | 'connected' | 'disconnected';
type CommandState = 'pending' | 'acknowledged' | 'failed';

type GestureResult = {
  label: string;
  pattern: string;
  states: boolean[];
  handDetected: boolean;
  reason: string;
};

type HistoryItem = {
  time: string;
  label: string;
  pattern: string;
};

const GESTURE_BY_PATTERN: Record<string, string> = {
  '01111': 'HELLO',
  '10111': 'HELP ME',
  '11011': 'THANK YOU',
  '11101': 'WELCOME',
  '11110': 'YES',
  '11111': 'HI',
};

const AUDIO_BY_LABEL: Record<string, string> = {
  HELLO: '001.mp3',
  'HELP ME': '002.mp3',
  'THANK YOU': '003.mp3',
  WELCOME: '004.mp3',
  YES: '005.mp3',
  HI: '006.mp3',
};

const GESTURE_GUIDE = Object.entries(GESTURE_BY_PATTERN).map(([pattern, label]) => ({
  label,
  pattern,
  audio: AUDIO_BY_LABEL[label],
}));

const HAND_CONNECTIONS = [
  [0, 1], [1, 2], [2, 3], [3, 4],
  [0, 5], [5, 6], [6, 7], [7, 8],
  [5, 9], [9, 10], [10, 11], [11, 12],
  [9, 13], [13, 14], [14, 15], [15, 16],
  [13, 17], [17, 18], [18, 19], [19, 20],
  [0, 17],
] as const;

const MODEL_URL = 'https://storage.googleapis.com/mediapipe-models/hand_landmarker/hand_landmarker/float16/1/hand_landmarker.task';
const DEFAULT_ESP32_BASE_URL = (import.meta.env.VITE_ESP32_BASE_URL as string | undefined) ?? '';
const COMMAND_TIMEOUT_MS = 4000;
const STABLE_GESTURE_MS = 350;

function normalizeDeviceHost(rawValue: string): string {
  if (!rawValue) return '';
  const trimmed = rawValue.trim().replace(/\/$/, '');
  if (/^https?:\/\//i.test(trimmed)) return trimmed.replace(/^https?:\/\//i, '');
  return trimmed;
}

function buildDeviceUrl(host: string, path: string): string {
  const normalizedHost = normalizeDeviceHost(host);
  if (!normalizedHost) return '';
  const base = normalizedHost.includes('://') ? normalizedHost : `http://${normalizedHost}`;
  return `${base.replace(/\/$/, '')}${path}`;
}

function distance(first: { x: number; y: number; z: number }, second: { x: number; y: number; z: number }): number {
  return Math.hypot(first.x - second.x, first.y - second.y, first.z - second.z);
}

function isExtended(landmarks: Array<{ x: number; y: number; z: number }>, tipIndex: number, pipIndex: number): boolean {
  const wrist = landmarks[0];
  const pip = landmarks[pipIndex];
  const tip = landmarks[tipIndex];
  const wristToPip = distance(wrist, pip);
  const wristToTip = distance(wrist, tip);
  if (wristToPip < 1e-6) return false;
  return wristToTip > wristToPip * 1.08;
}

function isThumbExtended(landmarks: Array<{ x: number; y: number; z: number }>): boolean {
  const tip = landmarks[4];
  const indexMcp = landmarks[5];
  const ip = landmarks[3];
  const tipToIndexMcp = distance(tip, indexMcp);
  const ipToIndexMcp = distance(ip, indexMcp);
  if (ipToIndexMcp < 1e-6) return false;
  return tipToIndexMcp > ipToIndexMcp * 1.08;
}

function getFingerStates(landmarks: Array<{ x: number; y: number; z: number }>): boolean[] {
  return [
    isThumbExtended(landmarks),
    isExtended(landmarks, 8, 6),
    isExtended(landmarks, 12, 10),
    isExtended(landmarks, 16, 14),
    isExtended(landmarks, 20, 18),
  ];
}

function fingerPattern(states: boolean[]): string {
  return states.map((state) => (state ? '1' : '0')).join('');
}

function detectGesture(landmarks: Array<{ x: number; y: number; z: number }>, handedness: string): GestureResult {
  if (!landmarks || landmarks.length < 21) {
    return {
      label: 'UNKNOWN',
      pattern: '00000',
      states: [false, false, false, false, false],
      handDetected: false,
      reason: 'Incomplete hand landmarks',
    };
  }

  const states = getFingerStates(landmarks);
  const pattern = fingerPattern(states);
  const label = GESTURE_BY_PATTERN[pattern] ?? 'UNKNOWN';

  return {
    label,
    pattern,
    states,
    handDetected: true,
    reason: label === 'UNKNOWN' ? `Unsupported pattern ${pattern}` : `Pattern ${pattern}: ${label} (${handedness || 'UNKNOWN'})`,
  };
}

function drawHandOverlay(
  canvas: HTMLCanvasElement,
  landmarks: Array<{ x: number; y: number; z: number }> | undefined,
  videoWidth: number,
  videoHeight: number,
): void {
  const context = canvas.getContext('2d');
  if (!context) return;

  canvas.width = videoWidth;
  canvas.height = videoHeight;
  context.clearRect(0, 0, canvas.width, canvas.height);

  if (!landmarks || landmarks.length === 0) {
    return;
  }

  context.strokeStyle = '#34d399';
  context.lineWidth = 2;
  context.fillStyle = '#f8fafc';

  for (const [start, end] of HAND_CONNECTIONS) {
    const from = landmarks[start];
    const to = landmarks[end];
    context.beginPath();
    context.moveTo(from.x * videoWidth, from.y * videoHeight);
    context.lineTo(to.x * videoWidth, to.y * videoHeight);
    context.stroke();
  }

  for (const landmark of landmarks) {
    context.beginPath();
    context.arc(landmark.x * videoWidth, landmark.y * videoHeight, 3, 0, Math.PI * 2);
    context.fill();
  }
}

export default function App() {
  const videoRef = useRef<HTMLVideoElement | null>(null);
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const landmarkerRef = useRef<HandLandmarker | null>(null);
  const animationFrameRef = useRef<number | null>(null);
  const selectedCameraRef = useRef<string>('');
  const patternHistoryRef = useRef<string[]>([]);
  const lastStableLabelRef = useRef<string>('');
  const candidateGestureRef = useRef<{ label: string; pattern: string; since: number } | null>(null);
  const esp32IpRef = useRef('');

  const [cameraStatus, setCameraStatus] = useState<CameraStatus>('idle');
  const [cameraError, setCameraError] = useState('');
  const [cameraDevices, setCameraDevices] = useState<MediaDeviceInfo[]>([]);
  const [selectedCameraId, setSelectedCameraId] = useState('');
  const [gestureStatus, setGestureStatus] = useState('initializing');
  const [recognizedGesture, setRecognizedGesture] = useState('NO HAND');
  const [rawPattern, setRawPattern] = useState('00000');
  const [fingerStates, setFingerStates] = useState<boolean[]>([false, false, false, false, false]);
  const [reason, setReason] = useState('Waiting for hand landmarks...');
  const [history, setHistory] = useState<HistoryItem[]>([]);
  const [modelStatus, setModelStatus] = useState('Model not loaded');
  const [esp32Ip, setEsp32Ip] = useState('');
  const [esp32Status, setEsp32Status] = useState<DeviceState>('unknown');
  const [esp32Health, setEsp32Health] = useState<{
    wifi: string;
    oled: string;
    audio: string;
    mpu6050: string;
    status: string;
  }>({
    wifi: 'unknown',
    oled: 'unknown',
    audio: 'unknown',
    mpu6050: 'unknown',
    status: 'unknown',
  });
  const [lastCommand, setLastCommand] = useState<CommandState>('pending');
  const [lastSeen, setLastSeen] = useState<string>('Not checked yet');

  const updateHistory = (label: string, pattern: string) => {
    const item: HistoryItem = {
      time: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' }),
      label,
      pattern,
    };
    setHistory((prev) => [item, ...prev].slice(0, 8));
  };

  useEffect(() => {
    if (DEFAULT_ESP32_BASE_URL) {
      const normalized = normalizeDeviceHost(DEFAULT_ESP32_BASE_URL);
      esp32IpRef.current = normalized;
      setEsp32Ip(normalized);
    }
  }, []);

  const sendGestureToEsp32 = async (label: string, pattern: string) => {
    const targetUrl = buildDeviceUrl(esp32IpRef.current, '/gesture');
    if (!targetUrl) {
      setLastCommand('failed');
      setEsp32Status('disconnected');
      setReason(`Cannot send ${label}: enter the ESP32 IP address first.`);
      console.error('[ESP32] Missing device address', { label, pattern });
      return;
    }

    setLastCommand('pending');
    const payload = { gesture: label, pattern, eventId: `${label}-${Date.now()}` };
    console.info('[ESP32] Sending gesture', { url: targetUrl, payload });

    try {
      const controller = new AbortController();
      const timeoutId = window.setTimeout(() => controller.abort(), COMMAND_TIMEOUT_MS);
      const response = await fetch(targetUrl, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
        signal: controller.signal,
      });
      window.clearTimeout(timeoutId);
      const bodyText = await response.text();
      const data = bodyText ? JSON.parse(bodyText) as { accepted?: boolean; error?: string; message?: string } : {};
      const accepted = response.ok && data.accepted !== false;
      console.info('[ESP32] Gesture response', { status: response.status, data });
      setLastCommand(accepted ? 'acknowledged' : 'failed');
      setEsp32Status(accepted ? 'connected' : 'disconnected');
      setLastSeen(new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' }));
      if (!accepted) {
        setReason(`ESP32 rejected ${label}: ${data.error || data.message || 'invalid command'}`);
      }
    } catch (error) {
      const message = error instanceof DOMException && error.name === 'AbortError'
        ? `ESP32 command timed out after ${COMMAND_TIMEOUT_MS} ms`
        : `ESP32 command failed: ${error instanceof Error ? error.message : String(error)}`;
      setLastCommand('failed');
      setEsp32Status('disconnected');
      setLastSeen(new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' }));
      setReason(message);
      console.error('[ESP32] Gesture request failed', { url: targetUrl, payload, error });
    }
  };

  const healthCheckEsp32 = async () => {
    const targetUrl = buildDeviceUrl(esp32IpRef.current, '/health');
    if (!targetUrl) {
      setEsp32Status('disconnected');
      setEsp32Health({ wifi: 'unknown', oled: 'unknown', audio: 'unknown', mpu6050: 'unknown', status: 'unknown' });
      return;
    }

    try {
      const controller = new AbortController();
      const timeoutId = window.setTimeout(() => controller.abort(), COMMAND_TIMEOUT_MS);
      console.info('[ESP32] Checking health', { url: targetUrl });
      const response = await fetch(targetUrl, { method: 'GET', signal: controller.signal });
      window.clearTimeout(timeoutId);
      if (!response.ok) {
        setEsp32Status('disconnected');
        setEsp32Health({ wifi: 'unknown', oled: 'unknown', audio: 'unknown', mpu6050: 'unknown', status: 'unknown' });
        return;
      }
      const data = await response.json();
      console.info('[ESP32] Health response', { status: response.status, data });
      const health = data as { wifi?: boolean | string; oled?: boolean | string; audio?: boolean | string; mpu6050?: boolean | string; message?: string };
      setEsp32Status('connected');
      setEsp32Health({
        wifi: health.wifi ? 'connected' : 'disconnected',
        oled: health.oled ? 'initialized' : 'error',
        audio: health.audio ? 'initialized' : 'error',
        mpu6050: health.mpu6050 ? 'available' : 'error',
        status: health.message || 'unknown',
      });
      setLastSeen(new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' }));
    } catch (error) {
      setEsp32Status('disconnected');
      setEsp32Health({ wifi: 'unknown', oled: 'unknown', audio: 'unknown', mpu6050: 'unknown', status: 'unknown' });
      setReason(`ESP32 health check failed: ${error instanceof Error ? error.message : String(error)}`);
      console.error('[ESP32] Health request failed', { url: targetUrl, error });
    }
  };

  const stopCamera = () => {
    setCameraStatus('idle');
    setGestureStatus('initializing');
    setReason('Camera stopped. Press Start Camera to begin.');
    if (animationFrameRef.current) {
      cancelAnimationFrame(animationFrameRef.current);
      animationFrameRef.current = null;
    }
    if (streamRef.current) {
      streamRef.current.getTracks().forEach((track) => track.stop());
      streamRef.current = null;
    }
    if (videoRef.current) {
      videoRef.current.srcObject = null;
    }
    lastStableLabelRef.current = '';
    patternHistoryRef.current = [];
    candidateGestureRef.current = null;
    candidateGestureRef.current = null;
  };

  useEffect(() => {
    return () => {
      stopCamera();
    };
  }, []);

  const createHandLandmarker = async () => {
    const vision = await FilesetResolver.forVisionTasks('https://cdn.jsdelivr.net/npm/@mediapipe/tasks-vision@latest/wasm');
    const landmarker = await HandLandmarker.createFromOptions(vision, {
      baseOptions: { modelAssetPath: MODEL_URL },
      runningMode: 'VIDEO',
      numHands: 1,
      minHandDetectionConfidence: 0.6,
      minTrackingConfidence: 0.6,
      minHandPresenceConfidence: 0.6,
    });
    landmarkerRef.current = landmarker;
    setModelStatus('MediaPipe model ready');
  };

  const startCamera = async () => {
    if (!navigator.mediaDevices?.getUserMedia) {
      setCameraStatus('error');
      setCameraError('This browser does not support camera capture.');
      return;
    }

    try {
      setCameraStatus('starting');
      setCameraError('');
      if (!landmarkerRef.current) await createHandLandmarker();

      const devices = await navigator.mediaDevices.enumerateDevices();
      const videoInputs = devices.filter((device) => device.kind === 'videoinput');
      setCameraDevices(videoInputs);
      if (!selectedCameraRef.current && videoInputs.length > 0) {
        selectedCameraRef.current = videoInputs[0].deviceId;
        setSelectedCameraId(videoInputs[0].deviceId);
      }

      const constraints: MediaStreamConstraints = {
        video: selectedCameraRef.current ? { deviceId: { exact: selectedCameraRef.current } } : { facingMode: 'user' },
        audio: false,
      };
      const stream = await navigator.mediaDevices.getUserMedia(constraints);
      streamRef.current = stream;
      if (videoRef.current) {
        videoRef.current.srcObject = stream;
        await videoRef.current.play();
      }

      const detectFrame = () => {
        const video = videoRef.current;
        const canvas = canvasRef.current;
        const landmarker = landmarkerRef.current;
        if (!video || !canvas || !landmarker) {
          animationFrameRef.current = window.requestAnimationFrame(detectFrame);
          return;
        }
        if (video.readyState >= 2) {
          const result = landmarker.detectForVideo(video, performance.now());
          const landmarks = result.landmarks[0];
          const handedness = result.handedness?.[0]?.[0]?.categoryName || 'UNKNOWN';
          drawHandOverlay(canvas, landmarks, video.videoWidth, video.videoHeight);
          if (!landmarks || landmarks.length === 0) {
            setGestureStatus('unknown');
            setRecognizedGesture('NO HAND');
            setRawPattern('00000');
            setFingerStates([false, false, false, false, false]);
            setReason('No hand detected. Show a palm inside the frame.');
            lastStableLabelRef.current = '';
            patternHistoryRef.current = [];
          } else {
            const detected = detectGesture(landmarks, handedness);
            setRawPattern(detected.pattern);
            setFingerStates(detected.states);
            setReason(detected.reason);
            setGestureStatus(detected.label === 'UNKNOWN' ? 'unknown' : 'active');
            if (detected.pattern !== '00000') {
              patternHistoryRef.current.push(detected.pattern);
              if (patternHistoryRef.current.length > 5) patternHistoryRef.current.shift();
              const counts = new Map<string, number>();
              for (const pattern of patternHistoryRef.current) counts.set(pattern, (counts.get(pattern) ?? 0) + 1);
              const stablePattern = [...counts.entries()].sort((a, b) => b[1] - a[1])[0]?.[0] ?? detected.pattern;
              const stableLabel = GESTURE_BY_PATTERN[stablePattern] ?? 'UNKNOWN';
              if (stableLabel !== 'UNKNOWN') {
                const now = performance.now();
                if (!candidateGestureRef.current || candidateGestureRef.current.label !== stableLabel || candidateGestureRef.current.pattern !== stablePattern) {
                  candidateGestureRef.current = { label: stableLabel, pattern: stablePattern, since: now };
                }
                if (now - candidateGestureRef.current.since >= STABLE_GESTURE_MS && lastStableLabelRef.current !== stableLabel) {
                  lastStableLabelRef.current = stableLabel;
                  setRecognizedGesture(stableLabel);
                  updateHistory(stableLabel, stablePattern);
                  void sendGestureToEsp32(stableLabel, stablePattern);
                }
              } else {
                candidateGestureRef.current = null;
                lastStableLabelRef.current = '';
                setRecognizedGesture('UNKNOWN');
              }
            }
          }
        }
        animationFrameRef.current = window.requestAnimationFrame(detectFrame);
      };
      animationFrameRef.current = window.requestAnimationFrame(detectFrame);
      setCameraStatus('active');
      setGestureStatus('active');
    } catch (error) {
      setCameraStatus('error');
      setCameraError(error instanceof Error ? error.message : 'Unable to access camera.');
    }
  };

  useEffect(() => {
    const loadCameraOptions = async () => {
      if (!navigator.mediaDevices?.enumerateDevices) return;
      try {
        const devices = await navigator.mediaDevices.enumerateDevices();
        const videoInputs = devices.filter((device) => device.kind === 'videoinput');
        setCameraDevices(videoInputs);
        if (videoInputs.length > 0 && !selectedCameraRef.current) {
          selectedCameraRef.current = videoInputs[0].deviceId;
          setSelectedCameraId(videoInputs[0].deviceId);
        }
      } catch (error) {
        console.warn('[Camera] Device enumeration unavailable', error);
      }
    };
    void loadCameraOptions();
  }, []);

  const gestureCounts = history.reduce<Record<string, number>>((counts, item) => {
    counts[item.label] = (counts[item.label] ?? 0) + 1;
    return counts;
  }, {});
  const mostUsedGesture = Object.entries(gestureCounts).sort((a, b) => b[1] - a[1])[0]?.[0] ?? '—';
  const clearHistory = () => setHistory([]);
  const statusText = cameraStatus === 'active' ? 'Live' : cameraStatus === 'starting' ? 'Starting' : cameraStatus === 'error' ? 'Needs attention' : 'Standby';

  return (
    <div className="app-shell">
      <header className="topbar">
        <a className="brand-group" href="#overview" aria-label="Signa home"><div className="brand-mark"><span>SG</span><i /></div><div><p className="eyebrow">SIGNALAB / ACCESSIBILITY AI</p><h1>Signa<span>.</span></h1></div></a>
        <nav className="nav-links" aria-label="Main navigation"><a href="#overview">Home</a><a href="#studio">Live Recognition</a><a href="#dashboard">Dashboard</a><a href="#guide">Gesture Guide</a><a href="#about">About</a></nav>
        <div className="nav-status"><span className={`status-dot ${esp32Status}`} /> {esp32Ip ? 'Device configured' : 'Device not configured'}</div>
      </header>

      <main>
        <section id="overview" className="hero">
          <div className="hero-copy"><div className="hero-kicker"><span className="pulse-dot" /> AI-POWERED ACCESSIBILITY PLATFORM</div><h2>Bridging Communication<br /><em>Through Intelligent</em> Gesture Recognition</h2><p className="lead">Recognize hand gestures in real time and communicate through text and voice using webcam-based AI and IoT-enabled hardware.</p><div className="hero-actions"><button className="primary" onClick={startCamera}><span className="button-icon">↗</span> Start Live Recognition</button><a className="secondary" href="#guide">Explore Gestures <span>→</span></a></div><div className="feature-row"><div><b>01</b><strong>Real-Time Recognition</strong><span>MediaPipe vision</span></div><div><b>02</b><strong>Text Output</strong><span>Instant translation</span></div><div><b>03</b><strong>Voice Output</strong><span>IoT-ready audio</span></div></div></div>
          <div className="hero-visual" aria-label="Illustration of hand landmark recognition"><div className="visual-orbit orbit-one" /><div className="visual-orbit orbit-two" /><div className="landmark-hand"><span className="hand-palm" /><i className="finger f1" /><i className="finger f2" /><i className="finger f3" /><i className="finger f4" /><i className="finger f5" /><b className="node n1" /><b className="node n2" /><b className="node n3" /><b className="node n4" /></div><div className="visual-label label-top">HAND LANDMARKS <strong>21 / 21</strong></div><div className="visual-label label-bottom"><span className="pulse-dot" /> VISION ENGINE <strong>READY</strong></div></div>
        </section>

        <div className="section-heading"><div><p className="eyebrow">01 / LIVE WORKSPACE</p><h2>Recognition studio</h2></div><span className={`status-pill ${cameraStatus}`}>{statusText}</span></div>
        <section id="studio" className="studio-grid">
          <div className="panel camera-panel"><div className="panel-header"><div><p className="panel-label">CAMERA FEED</p><h3>Live gesture capture</h3></div><span className="model-state"><span className="status-dot connected" /> {modelStatus}</span></div><div className="video-container"><video ref={videoRef} playsInline muted autoPlay className="video-feed" hidden={cameraStatus !== 'active'} />{cameraStatus !== 'active' && <div className="camera-placeholder"><div className="empty-camera-icon">◎</div><strong>{cameraStatus === 'error' ? 'Camera needs attention' : 'Ready when you are'}</strong><span>{cameraStatus === 'error' ? cameraError : 'Start the camera to begin recognizing gestures.'}</span></div>}<canvas ref={canvasRef} className="overlay-canvas" />{cameraStatus === 'active' && <div className="feed-badge"><span className="pulse-dot" /> LIVE</div>}{cameraStatus === 'active' && <div className="feed-hint">Position your hand inside the frame</div>}</div><div className="camera-toolbar"><button className="primary" onClick={startCamera}>{cameraStatus === 'active' ? 'Restart camera' : 'Start camera'}</button><button className="secondary compact" onClick={stopCamera}>Stop</button><label className="camera-select"><span>Source</span><select aria-label="Camera source" value={selectedCameraId} onChange={(event) => { selectedCameraRef.current = event.target.value; setSelectedCameraId(event.target.value); }}><option value="">Default camera</option>{cameraDevices.map((device) => <option key={device.deviceId} value={device.deviceId}>{device.label || `Camera ${device.deviceId.slice(0, 6)}`}</option>)}</select></label></div></div>
          <aside className="panel recognition-panel"><div className="panel-header"><div><p className="panel-label">TRANSLATION OUTPUT</p><h3>Recognized gesture</h3></div><span className={`status-pill ${gestureStatus}`}>{gestureStatus === 'active' ? 'Stable' : gestureStatus}</span></div><div className="recognized-word">{recognizedGesture}<span className="word-caret">_</span></div><p className="recognition-note">{reason}</p><div className="data-row"><span>Finger pattern</span><code>{rawPattern}</code></div><div className="data-row"><span>Audio file</span><strong>{AUDIO_BY_LABEL[recognizedGesture] ?? 'Not available'}</strong></div><div className="finger-grid">{['Thumb', 'Index', 'Middle', 'Ring', 'Pinky'].map((finger, index) => <div key={finger} className={`finger-state ${fingerStates[index] ? 'extended' : ''}`}><span className="finger-bar" /><span>{finger}</span><strong>{fingerStates[index] ? 'Open' : 'Closed'}</strong></div>)}</div><div className="command-state"><span>Device command</span><strong className={lastCommand}>{lastCommand === 'acknowledged' ? 'Acknowledged' : lastCommand === 'failed' ? 'Failed' : 'Not sent'}</strong></div></aside>
        </section>

        <section id="dashboard" className="dashboard-section"><div className="section-heading"><div><p className="eyebrow">02 / SYSTEM OVERVIEW</p><h2>Session dashboard</h2></div><span className="muted-note">Live session data only</span></div><div className="metrics-grid"><div className="metric-card accent"><span>Total recognized</span><strong>{history.length.toString().padStart(2, '0')}</strong><small>This session</small></div><div className="metric-card"><span>Most frequent</span><strong>{mostUsedGesture}</strong><small>{mostUsedGesture === '—' ? 'Awaiting recognition' : `${gestureCounts[mostUsedGesture]} occurrence${gestureCounts[mostUsedGesture] === 1 ? '' : 's'}`}</small></div><div className="metric-card"><span>Camera status</span><strong>{statusText}</strong><small>MediaPipe vision</small></div><div className="metric-card"><span>Device status</span><strong>{esp32Status === 'unknown' ? 'Unavailable' : esp32Status}</strong><small>{lastSeen}</small></div></div><div className="dashboard-grid"><section className="panel hardware-panel"><div className="panel-header"><div><p className="panel-label">IOT HARDWARE</p><h3>Device status</h3></div><button className="text-button" onClick={healthCheckEsp32}>Refresh status ↻</button></div><div className="device-controls"><label className="field-label">ESP32 address<input value={esp32Ip} onChange={(event) => { esp32IpRef.current = event.target.value; setEsp32Ip(event.target.value); }} placeholder="192.168.1.20" /></label><span className="configured-note">{esp32Ip ? 'Configured' : 'Not configured'}</span></div><div className="connection-list"><div><span><i className={`status-dot ${esp32Health.wifi}`} /> Wi-Fi network</span><strong>{esp32Health.wifi}</strong></div><div><span><i className={`status-dot ${esp32Health.oled}`} /> OLED display</span><strong>{esp32Health.oled}</strong></div><div><span><i className={`status-dot ${esp32Health.audio}`} /> DFPlayer Mini</span><strong>{esp32Health.audio}</strong></div><div><span><i className={`status-dot ${esp32Health.mpu6050}`} /> MPU6050 sensor</span><strong>{esp32Health.mpu6050}</strong></div></div><div className="hardware-footer"><span>Last command: <b>{lastCommand}</b></span><span>Last seen: <b>{lastSeen}</b></span></div></section><section id="history" className="panel history-panel"><div className="panel-header"><div><p className="panel-label">ACTIVITY LOG</p><h3>Recent recognition</h3></div><button className="text-button" onClick={clearHistory} disabled={history.length === 0}>Clear history</button></div>{history.length === 0 ? <div className="list-empty"><span>◌</span><strong>No gestures recognized yet</strong><small>Your live session activity will appear here.</small></div> : <ul className="history-list">{history.map((item, index) => <li key={`${item.label}-${item.time}-${index}`}><span className="history-index">{String(history.length - index).padStart(2, '0')}</span><div><strong>{item.label}</strong><small>{item.time} · Pattern {item.pattern}</small></div><code>{AUDIO_BY_LABEL[item.label] ?? '—'}</code></li>)}</ul>}</section></div></section>

        <section id="guide" className="guide-section"><div className="section-heading"><div><p className="eyebrow">03 / REFERENCE</p><h2>Gesture guide</h2></div><span className="muted-note">Custom demonstration mappings</span></div><div className="guide-grid">{GESTURE_GUIDE.map((gesture) => <article className="guide-card" key={gesture.pattern}><div className="guide-pattern">{gesture.pattern.split('').map((bit, index) => <span className={bit === '1' ? 'on' : ''} key={`${gesture.pattern}-${index}`} />)}</div><div><h3>{gesture.label}</h3><p>Pattern <code>{gesture.pattern}</code></p></div><span className="guide-audio">{gesture.audio}</span></article>)}</div><p className="disclaimer">These are custom demonstration mappings for this project, not universal sign-language standards or a complete dictionary.</p></section>
        <section id="about" className="about-strip"><div><p className="eyebrow">04 / ABOUT THE PLATFORM</p><h2>Technology with a human purpose.</h2></div><p>Signa combines browser-based MediaPipe hand landmarks with an optional local ESP32 relay for OLED and DFPlayer Mini output. Camera recognition works in the browser; hardware status is only shown when the configured device reports it.</p></section>
      </main>
      <footer><span>SMART GLOVE BASED SIGN LANGUAGE TO SPEECH CONVERSION SYSTEM</span><span>Session history is held in memory and clears on refresh.</span></footer>
    </div>
  );
}
