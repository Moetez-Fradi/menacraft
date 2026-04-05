/**
 * MENACRAFT – Popup Script
 * Controls settings, displays history, pings API status.
 */

'use strict';

// ─── DOM refs ─────────────────────────────────────────────────────────────────
const masterToggle    = document.getElementById('masterToggle');
const statusDot       = document.getElementById('statusDot');
const statusText      = document.getElementById('statusText');
const sensitivitySlider = document.getElementById('sensitivitySlider');
const sensitivityValue  = document.getElementById('sensitivityValue');
const historyList     = document.getElementById('historyList');
const clearHistoryBtn = document.getElementById('clearHistory');
const apiStatusEl     = document.getElementById('apiStatus');
const statTotal       = document.getElementById('statTotal');
const statFake        = document.getElementById('statFake');
const statSuspicious  = document.getElementById('statSuspicious');
const statReal        = document.getElementById('statReal');

// ─── Init ─────────────────────────────────────────────────────────────────────
async function init() {
  const stored = await chrome.storage.local.get(['enabled', 'sensitivity', 'history']);

  // Master toggle
  const enabled = stored.enabled !== false;
  masterToggle.checked = enabled;
  updateStatusUI(enabled);

  // Sensitivity
  const sens = Math.round((stored.sensitivity ?? 0.4) * 100);
  sensitivitySlider.value = Math.min(Math.max(sens, 10), 90);
  sensitivityValue.textContent = sensitivitySlider.value + '%';
  updateSliderFill(sensitivitySlider);

  // History
  renderHistory(stored.history ?? []);

  // API ping
  checkApiStatus();
}

// ─── Master Toggle ────────────────────────────────────────────────────────────
masterToggle.addEventListener('change', async () => {
  const enabled = masterToggle.checked;
  await chrome.storage.local.set({ enabled });

  updateStatusUI(enabled);

  // Notify active tab's content script
  const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
  if (tab?.id) {
    chrome.tabs.sendMessage(tab.id, { type: 'MC_TOGGLE', enabled }).catch(() => {});
  }
});

function updateStatusUI(enabled) {
  if (enabled) {
    statusDot.className  = 'status-dot active';
    statusText.textContent = 'Active – scanning this page';
  } else {
    statusDot.className  = 'status-dot inactive';
    statusText.textContent = 'Paused – Digital Sieve off';
  }
}

// ─── Sensitivity Slider ───────────────────────────────────────────────────────
function updateSliderFill(slider) {
  const min = Number(slider.min) || 0;
  const max = Number(slider.max) || 100;
  const pct = ((slider.value - min) / (max - min)) * 100;
  slider.style.setProperty('--fill', pct.toFixed(1) + '%');
}

sensitivitySlider.addEventListener('input', () => {
  sensitivityValue.textContent = sensitivitySlider.value + '%';
  updateSliderFill(sensitivitySlider);
});

sensitivitySlider.addEventListener('change', async () => {
  const val = parseInt(sensitivitySlider.value) / 100;
  await chrome.storage.local.set({ sensitivity: val });
});

// ─── History Rendering ────────────────────────────────────────────────────────
function renderHistory(history) {
  // Stats
  const fake       = history.filter(h => h.verdict === 'FAKE').length;
  const suspicious = history.filter(h => h.verdict === 'SUSPICIOUS').length;
  const real       = history.filter(h => h.verdict === 'REAL').length;

  statTotal.textContent      = history.length;
  statFake.textContent       = fake;
  statSuspicious.textContent = suspicious;
  statReal.textContent       = real;

  // List
  historyList.innerHTML = '';

  if (!history.length) {
    historyList.innerHTML = `
      <li class="empty-state">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
          <circle cx="11" cy="11" r="8"/><path d="m21 21-4.35-4.35"/>
        </svg>
        <span>No flagged content yet</span>
      </li>`;
    return;
  }

  // Show last 20
  for (const entry of history.slice(0, 20)) {
    const li = document.createElement('li');
    li.className = 'history-item';

    const timeAgo = relTime(entry.ts);
    const domain  = tryDomain(entry.url);
    const pct     = Math.round(entry.threat_level * 100);
    const label   = entry.verdict === 'FAKE' ? 'Fake'
                  : entry.verdict === 'SUSPICIOUS' ? 'Suspicious'
                  : 'Real';

    li.innerHTML = `
      <div class="h-body">
        <div class="h-title">${escHtml(entry.title || domain)}</div>
        <div class="h-meta">
          <span class="h-badge h-badge--${entry.verdict}">${label}</span>
          <span class="h-domain">${escHtml(domain)}</span>
          <span class="h-sep">·</span>
          <span class="h-time">${timeAgo}</span>
        </div>
      </div>
      <span class="h-score h-score--${entry.verdict}">${pct}%</span>`;

    historyList.appendChild(li);
  }
}

function relTime(ts) {
  const diff = Date.now() - ts;
  if (diff < 60_000)       return 'just now';
  if (diff < 3_600_000)    return Math.floor(diff / 60_000) + 'm ago';
  if (diff < 86_400_000)   return Math.floor(diff / 3_600_000) + 'h ago';
  return Math.floor(diff / 86_400_000) + 'd ago';
}

function tryDomain(url) {
  try { return new URL(url).hostname.replace(/^www\./, ''); }
  catch { return url?.slice(0, 30) ?? ''; }
}

function escHtml(str) {
  if (!str) return '';
  return String(str)
    .replace(/&/g,'&amp;').replace(/</g,'&lt;')
    .replace(/>/g,'&gt;').replace(/"/g,'&quot;');
}

// ─── Clear History ────────────────────────────────────────────────────────────
clearHistoryBtn.addEventListener('click', async () => {
  await chrome.storage.local.set({ history: [] });
  renderHistory([]);
});

// ─── API Status Ping ──────────────────────────────────────────────────────────
async function checkApiStatus() {
  const ORCHESTRATOR = 'http://localhost:8080/health';
  try {
    const ctrl = new AbortController();
    setTimeout(() => ctrl.abort(), 3000);
    const resp = await fetch(ORCHESTRATOR, { signal: ctrl.signal });
    if (resp.ok) {
      apiStatusEl.textContent  = 'API connected';
      apiStatusEl.className    = 'api-status ok';
    } else {
      throw new Error('non-ok');
    }
  } catch {
    apiStatusEl.textContent = 'API offline';
    apiStatusEl.className   = 'api-status error';
    statusDot.className     = 'status-dot error';
    statusText.textContent  = 'API unreachable';
  }
}

// ─── Live storage updates ─────────────────────────────────────────────────────
chrome.storage.onChanged.addListener((changes) => {
  if (changes.history) renderHistory(changes.history.newValue ?? []);
  if (changes.enabled) {
    masterToggle.checked = changes.enabled.newValue;
    updateStatusUI(changes.enabled.newValue);
  }
});

// ─── Boot ─────────────────────────────────────────────────────────────────────
init();
