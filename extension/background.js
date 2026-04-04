/**
 * MENACRAFT – Background Service Worker
 * Manages API communication, state, and tab messaging.
 */

'use strict';

// ─── Config ──────────────────────────────────────────────────────────────────

const ORCHESTRATOR_URL = 'http://localhost:8080/analyze';
const REQUEST_TIMEOUT_MS = 10_000;

// ─── State ────────────────────────────────────────────────────────────────────

/** elementId → { tabId, ts } */
const pending = new Map();

// ─── Message Handler ─────────────────────────────────────────────────────────

chrome.runtime.onMessage.addListener((msg, sender) => {
  if (msg.type === 'ANALYZE') {
    const tabId = sender.tab?.id;
    if (!tabId) return;
    pending.set(msg.payload.element_id, { tabId, ts: Date.now() });
    analyzeContent(tabId, msg.payload).catch(() => {});
    return false; // synchronous – no async sendResponse needed
  }

  if (msg.type === 'CLEAR_HISTORY') {
    chrome.storage.local.set({ history: [] });
    return false;
  }
});

// ─── Core Analysis ───────────────────────────────────────────────────────────

async function analyzeContent(tabId, payload) {
  const { element_id } = payload;
  let result;

  try {
    const ctrl = new AbortController();
    const timer = setTimeout(() => ctrl.abort(), REQUEST_TIMEOUT_MS);

    const resp = await fetch(ORCHESTRATOR_URL, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
      signal: ctrl.signal,
    });

    clearTimeout(timer);

    if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
    result = await resp.json();
  } catch (err) {
    // On any error, return a neutral/real verdict so the UI clears gracefully
    result = {
      threat_level: 0,
      verdict: 'REAL',
      axes: {},
      latency_ms: 0,
      _error: err.name === 'AbortError' ? 'timeout' : 'network',
    };
  } finally {
    pending.delete(element_id);
  }

  // Deliver result to the originating tab's content script
  try {
    await chrome.tabs.sendMessage(tabId, {
      type: 'ANALYSIS_RESULT',
      element_id,
      result,
    });
  } catch {
    // Tab may have navigated away – ignore
  }
}

// ─── Extension Install / Update ───────────────────────────────────────────────

chrome.runtime.onInstalled.addListener(({ reason }) => {
  if (reason === 'install') {
    chrome.storage.local.set({
      enabled: true,
      sensitivity: 0.4,
      history: [],
      theme: {
        colors: {
          safe:       '#00FF88',
          warning:    '#FFA500',
          danger:     '#FF0033',
          background: '#0D0D0D',
        },
        thresholds: {
          blur:    0.7,
          warning: 0.4,
        },
      },
    });
  }
});

// ─── Periodic cleanup of stale pending entries ────────────────────────────────

setInterval(() => {
  const cutoff = Date.now() - REQUEST_TIMEOUT_MS * 2;
  for (const [id, entry] of pending) {
    if (entry.ts < cutoff) pending.delete(id);
  }
}, 30_000);
