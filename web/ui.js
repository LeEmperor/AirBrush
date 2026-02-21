/**
 * AirBrush UI — buttons, sliders, status display.
 */

import * as app from './app.js';
import { quatToEuler, radToDeg } from './math.js';

// ── DOM refs ───────────────────────────────────────────────────────────────
const $ = (id) => document.getElementById(id);

const statusEl      = $('status');
const trackingEl    = $('tracking');
const poseEl        = $('pose-data');
const connectBtn    = $('btn-connect');
const calibrateBtn  = $('btn-calibrate');
const killBtn       = $('btn-kill');
const armBtn        = $('btn-arm');
const brightnessEl  = $('brightness');
const brightnessVal = $('brightness-val');
const modeSelect    = $('mode-select');

// ── helpers ────────────────────────────────────────────────────────────────
function wsUrl() {
  const proto = location.protocol === 'https:' ? 'wss' : 'ws';
  return `${proto}://${location.host}/ws`;
}

// ── event bindings ─────────────────────────────────────────────────────────
connectBtn.addEventListener('click', () => {
  const state = app.getState();
  if (state.connected) {
    app.disconnect();
  } else {
    app.connect(wsUrl());
    app.autoStartTracking();
  }
});

calibrateBtn.addEventListener('click', () => app.calibrateZero());

killBtn.addEventListener('click', () => app.killSwitch());

armBtn.addEventListener('click', () => app.armDrone());

brightnessEl.addEventListener('input', () => {
  const v = parseFloat(brightnessEl.value);
  brightnessVal.textContent = v.toFixed(2);
  app.sendUI({ brightness: v });
});

modeSelect.addEventListener('change', () => {
  app.sendUI({ mode: modeSelect.value });
});

// ── status updates ─────────────────────────────────────────────────────────
function refreshStatus() {
  const s = app.getState();
  statusEl.textContent = s.connected ? 'Connected' : 'Disconnected';
  statusEl.className = 'status ' + (s.connected ? 'on' : 'off');
  trackingEl.textContent = s.tracking
    ? `Tracking: ${s.trackingSource}` : 'Not tracking';
  connectBtn.textContent = s.connected ? 'Disconnect' : 'Connect';
}

function refreshPose() {
  const s = app.getState();
  const q = s.currentQuat;
  const e = quatToEuler(q);
  let txt = `Q: [${q.map(v => v.toFixed(3)).join(', ')}]\n`;
  txt += `Yaw: ${radToDeg(e.yaw).toFixed(1)}°  `;
  txt += `Pitch: ${radToDeg(e.pitch).toFixed(1)}°  `;
  txt += `Roll: ${radToDeg(e.roll).toFixed(1)}°`;
  if (s.currentPos) {
    const p = s.currentPos;
    txt += `\nPos: [${p.map(v => v.toFixed(3)).join(', ')}]`;
  }
  poseEl.textContent = txt;
}

window.addEventListener('airbrush-status', refreshStatus);
window.addEventListener('airbrush-pose', refreshPose);

// initial
refreshStatus();
