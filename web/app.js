/**
 * AirBrush phone client — WebXR (preferred) + DeviceOrientation fallback.
 * Streams pose over WebSocket to the Python server.
 */

import { quatNormalize, deviceOrientationToQuatZXY, quatToEuler, radToDeg }
  from './math.js';

// ── state ──────────────────────────────────────────────────────────────────
let ws = null;
let seq = 0;
let connected = false;
let tracking = false;
let trackingSource = 'none';  // 'webxr' | 'device_orientation' | 'none'
let xrSession = null;
let xrRefSpace = null;

const SEND_INTERVAL_MS = 25;  // ~40 Hz
let lastSendTime = 0;

// latest pose
let currentQuat = [0, 0, 0, 1];
let currentPos = null;

// ── exports for UI ─────────────────────────────────────────────────────────
export function getState() {
  return { connected, tracking, trackingSource, currentQuat, currentPos };
}

// ── WebSocket ──────────────────────────────────────────────────────────────
export function connect(url) {
  if (ws && ws.readyState <= 1) {
    ws.close();
  }
  ws = new WebSocket(url);
  ws.onopen = () => {
    connected = true;
    window.dispatchEvent(new Event('airbrush-status'));
    console.log('[WS] connected');
  };
  ws.onclose = () => {
    connected = false;
    window.dispatchEvent(new Event('airbrush-status'));
    console.log('[WS] disconnected');
  };
  ws.onerror = (e) => console.error('[WS] error', e);
  ws.onmessage = (e) => {
    try {
      const msg = JSON.parse(e.data);
      if (msg.type === 'ping') {
        ws.send(JSON.stringify({ type: 'pong' }));
      }
    } catch (_) { /* ignore non-JSON */ }
  };
}

export function disconnect() {
  if (ws) ws.close();
}

function sendMsg(obj) {
  if (ws && ws.readyState === 1) {
    ws.send(JSON.stringify(obj));
  }
}

function sendPose() {
  const now = performance.now();
  if (now - lastSendTime < SEND_INTERVAL_MS) return;
  lastSendTime = now;
  sendMsg({
    type: 'pose',
    t: Date.now() / 1000,
    seq: ++seq,
    pos: currentPos,
    quat: currentQuat.map(v => Math.round(v * 10000) / 10000),
    ref: trackingSource,
  });
}

// ── calibration ────────────────────────────────────────────────────────────
export function calibrateZero() {
  sendMsg({ type: 'calibrate_zero', quat: [...currentQuat] });
}

// ── kill / arm ─────────────────────────────────────────────────────────────
export function killSwitch() {
  sendMsg({ type: 'kill' });
}

export function armDrone() {
  sendMsg({ type: 'arm' });
}

// ── UI params ──────────────────────────────────────────────────────────────
export function sendUI(params) {
  sendMsg({ type: 'ui', ...params });
}

// ── WebXR tracking ─────────────────────────────────────────────────────────
export async function startWebXR() {
  if (!navigator.xr) {
    console.warn('WebXR not available');
    return false;
  }
  const supported = await navigator.xr.isSessionSupported('immersive-ar')
    .catch(() => false);
  if (!supported) {
    console.warn('immersive-ar not supported, trying inline');
    return startWebXRInline();
  }
  try {
    xrSession = await navigator.xr.requestSession('immersive-ar', {
      requiredFeatures: ['local-floor'],
    });
    xrRefSpace = await xrSession.requestReferenceSpace('local-floor');
    trackingSource = 'webxr';
    tracking = true;
    window.dispatchEvent(new Event('airbrush-status'));

    xrSession.requestAnimationFrame(xrFrame);
    xrSession.addEventListener('end', () => {
      tracking = false;
      trackingSource = 'none';
      window.dispatchEvent(new Event('airbrush-status'));
    });
    return true;
  } catch (err) {
    console.error('WebXR start failed:', err);
    return false;
  }
}

async function startWebXRInline() {
  try {
    xrSession = await navigator.xr.requestSession('inline', {
      requiredFeatures: ['viewer'],
    });
    xrRefSpace = await xrSession.requestReferenceSpace('viewer');
    trackingSource = 'webxr';
    tracking = true;
    window.dispatchEvent(new Event('airbrush-status'));
    xrSession.requestAnimationFrame(xrFrame);
    return true;
  } catch (err) {
    console.warn('Inline WebXR failed:', err);
    return false;
  }
}

function xrFrame(time, frame) {
  if (!xrSession) return;
  const pose = frame.getViewerPose(xrRefSpace);
  if (pose) {
    const t = pose.transform;
    const o = t.orientation;
    currentQuat = quatNormalize([o.x, o.y, o.z, o.w]);
    const p = t.position;
    currentPos = [p.x, p.y, p.z];
    sendPose();
    window.dispatchEvent(new Event('airbrush-pose'));
  }
  xrSession.requestAnimationFrame(xrFrame);
}

// ── DeviceOrientation fallback ─────────────────────────────────────────────
export function startDeviceOrientation() {
  if (typeof DeviceOrientationEvent === 'undefined') {
    console.warn('DeviceOrientationEvent not available');
    return false;
  }

  const startListening = () => {
    window.addEventListener('deviceorientation', onDeviceOrientation, true);
    trackingSource = 'device_orientation';
    tracking = true;
    window.dispatchEvent(new Event('airbrush-status'));
    return true;
  };

  // iOS 13+ requires explicit permission
  if (typeof DeviceOrientationEvent.requestPermission === 'function') {
    DeviceOrientationEvent.requestPermission().then(state => {
      if (state === 'granted') {
        startListening();
      } else {
        console.warn('DeviceOrientation permission denied');
      }
    }).catch(err => console.error('Permission error:', err));
    return true; // async — will resolve later
  }

  return startListening();
}

function onDeviceOrientation(e) {
  if (e.alpha === null) return;
  currentQuat = deviceOrientationToQuatZXY(e.alpha, e.beta, e.gamma);
  currentPos = null; // no position from device orientation
  sendPose();
  window.dispatchEvent(new Event('airbrush-pose'));
}

// ── auto-start best available tracking ─────────────────────────────────────
export async function autoStartTracking() {
  const ok = await startWebXR();
  if (!ok) {
    console.log('Falling back to DeviceOrientation');
    startDeviceOrientation();
  }
}
