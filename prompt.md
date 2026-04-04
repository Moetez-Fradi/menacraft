# 🧠 MENACRAFT – Browser Extension (Manifest V3)

You are a **Senior Frontend & Browser Extension Engineer**.

Your task is to build a **high-performance, non-intrusive Chrome Extension (Manifest V3)** that:

* Intercepts visible web content (social feeds, news)
* Sends anonymized snapshots to backend
* Renders a **real-time verification overlay ("Digital Sieve")**

---

# 🎯 CORE GOALS

* ⚡ **Real-time feel** (no UI blocking, smooth scrolling)
* 🔐 **Privacy-first** (no raw data leakage)
* 🧩 **Non-intrusive overlay**
* 🎨 **Premium UI ("expensive" feel)**

---

# 🧩 SYSTEM ARCHITECTURE

## Flow:

1. **Content Script**
   → Detect elements (images, videos, posts)
   → Capture sanitized snapshot
   → Send to Background

2. **Background Service Worker**
   → Forward to Orchestrator API
   → Listen for results (polling or WebSocket)
   → Return scores to Content Script

3. **Content Script**
   → Inject overlay UI (Shadow DOM)
   → Apply blur / warnings

---

# 1️⃣ CONTENT SCRIPT (content.js)

## Role: The Interceptor

---

## 🔍 DOM Detection

Use:

* `MutationObserver` (NOT polling)

Detect:

* Images (`img`)
* Video containers (`video`, divs with video role)
* Social posts (Twitter, Facebook, Instagram-like structures)

---

## ⚡ Performance Constraints

* Debounce detection (avoid spam)
* Deduplicate elements using:

  * WeakMap OR dataset IDs
* Only process:

  * visible elements (IntersectionObserver)

---

## 📸 Snapshot Capture

* Use **canvas-based capture**
* Capture ONLY:

  * element bounding box
* DO NOT capture full page

Compress:

* low resolution (fast transfer)

Send:

```json
{
  "element_id": "...",
  "snapshot_base64": "...",
  "text_context": "...",
  "content_type": "image | video | text | post"
}
```

---

## 🧠 Overlay Injection

* Use **Shadow DOM** (critical to avoid CSS conflicts)
* Attach overlay to each detected element

---

# 2️⃣ BACKGROUND SERVICE WORKER (background.js)

## Role: Network + State Manager

---

## Responsibilities:

### API Communication

* Send payload → Go Orchestrator
* Use:

  * `fetch` (primary)
  * optional WebSocket for streaming results

---

### Async Handling

* Maintain a map:

  * `element_id → pending request`
* Return results to correct content script instance

---

### Messaging

Use:

* `chrome.runtime.sendMessage`
* `chrome.tabs.sendMessage`

---

### Response Format

Expect:

```json
{
  "threat_level": 0.0-1.0,
  "verdict": "REAL | SUSPICIOUS | FAKE",
  "axes": {
    "classifier": {...},
    "context": {...},
    "source": {...},
    "truth": {...}
  }
}
```

---

# 3️⃣ UI/UX SYSTEM (THE "DIGITAL SIEVE")

## 🎨 Design Philosophy

* Feels like a **security layer**
* Minimal but powerful
* Does NOT interrupt scroll flow

---

## 🛑 The Blur Shield

### Behavior:

* Trigger if:

  * high "Generated" score OR
  * high "Misinformation"

### Implementation:

* CSS:

  * `backdrop-filter: blur(...)`
* Overlay click → reveal content

---

## 📊 The Information Bar

Attach to element (top or bottom)

### Components:

### 1. Threat Meter

* Gradient:

  * Green → Yellow → Red
* Based on `threat_level`

---

### 2. Axis Badges

Icons:

* 🧠 Authenticity
* 🔄 Consistency
* 🌐 Source
* 📡 Truth

Each badge:

* color-coded
* hover → short explanation

---

### 3. Fact-Check Popover

On click:

Show:

* explanation ("why flagged")
* **corrected version (REAL DEAL)**
* source links (Axis 4)

---

## ⚡ Micro-interactions

* Smooth fade-in overlays
* Slide-up info panel
* No blocking layout shifts

---

# 4️⃣ STATE MANAGEMENT

* Use lightweight store (in content or background):

  * `Map` or `chrome.storage.session`

Store:

* user "whitelisted" elements
* revealed content state

---

# 5️⃣ EXTENSION FILES

## manifest.json

Permissions:

* `activeTab`
* `scripting`
* `storage`

Use:

* Manifest V3
* Service worker (background)

---

## Required Files:

* `manifest.json`
* `content.js`
* `background.js`
* `popup.html`
* `popup.css`
* `popup.js`

---

# 6️⃣ POPUP UI (Settings + History)

## Features:

* Toggle:

  * Enable/Disable Menacraft
* Show:

  * recently flagged content
* Settings:

  * sensitivity level (threshold)

---

# 7️⃣ UI THEME CONFIG (JSON)

Provide configurable schema:

```json
{
  "colors": {
    "safe": "#00FF88",
    "warning": "#FFA500",
    "danger": "#FF0033",
    "background": "#0D0D0D"
  },
  "thresholds": {
    "blur": 0.7,
    "warning": 0.4
  }
}
```

---

# ⚡ PERFORMANCE RULES (CRITICAL)

* Never block main thread
* Use async everywhere
* Avoid re-render loops
* Batch DOM updates
* Only process visible elements

---

# 🔐 PRIVACY RULES

* No full-page capture
* No persistent storage of content
* Only send anonymized snapshots

---

# 🚀 TASK

Generate the **full working Chrome extension code**.

DO NOT give explanations.

Provide:

* Complete file structure
* Clean, production-ready code
* Optimized for performance

