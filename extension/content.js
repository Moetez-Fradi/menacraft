/**
 * MENACRAFT – Content Script
 *
 * Pipeline:
 *   DOM element visible (IO) → extract text/image/metadata → send to BG
 *   BG → POST /analyze → ANALYSIS_RESULT → Shadow DOM overlay
 */

'use strict';

if (window.__mcSieve) throw new Error('mc:dup');
window.__mcSieve = true;

(function () {

const LOG = (...a) => console.debug('[MENACRAFT]', ...a);

// ─── Config ───────────────────────────────────────────────────────────────────
const CFG = {
  DEBOUNCE_MS:   120,
  IO_THRESHOLD:  0.05,        // fire when just 5% visible
  SNAP_MAX_W:    480,
  SNAP_MAX_H:    360,
  SNAP_QUALITY:  0.65,
  TEXT_MAX:      800,
  LINKS_MAX:     8,
  MIN_IMG_PX:    80,           // ignore tiny icons/avatars
};

// ─── State ────────────────────────────────────────────────────────────────────
let enabled       = true;
let sensitivity   = 0.4;
let blurThreshold = 0.7;
let colors        = { safe:'#00FF88', warning:'#FFA500', danger:'#FF0033', background:'#0D0D0D' };

const queued   = new WeakSet();   // elements already observed by IO
const overlays = new Map();       // elementId → { host, shadow }
let   idSeq    = 0;
const newId    = () => `mc-${Date.now()}-${++idSeq}`;

// Load settings
chrome.storage.local.get(['enabled','sensitivity','theme'], (s) => {
  if (s.enabled      != null)       enabled       = s.enabled;
  if (s.sensitivity  != null)       sensitivity   = s.sensitivity;
  if (s.theme?.thresholds?.blur)    blurThreshold = s.theme.thresholds.blur;
  if (s.theme?.thresholds?.warning) sensitivity   = s.theme.thresholds.warning;
  if (s.theme?.colors)              colors        = s.theme.colors;
  LOG(`ready | enabled=${enabled} | sensitivity=${sensitivity} | platform=${PLATFORM}`);
});
chrome.storage.onChanged.addListener((ch) => {
  if (ch.enabled)     enabled     = ch.enabled.newValue;
  if (ch.sensitivity) sensitivity = ch.sensitivity.newValue;
  if (ch.theme)       applyTheme(ch.theme.newValue);
});
function applyTheme(t) {
  if (t?.thresholds?.blur)    blurThreshold = t.thresholds.blur;
  if (t?.thresholds?.warning) sensitivity   = t.thresholds.warning;
  if (t?.colors)              colors        = t.colors;
}

// ─── Platform ─────────────────────────────────────────────────────────────────
const PLATFORM = (() => {
  const h = location.hostname.replace(/^www\./, '');
  if (/^(twitter|x)\.com/.test(h))  return 'twitter';
  if (/facebook\.com/.test(h))       return 'facebook';
  if (/instagram\.com/.test(h))      return 'instagram';
  if (/linkedin\.com/.test(h))       return 'linkedin';
  if (/reddit\.com/.test(h))         return 'reddit';
  if (/youtube\.com/.test(h))        return 'youtube';
  if (/tiktok\.com/.test(h))         return 'tiktok';
  return 'web';
})();

const SOURCE_TYPE = (() => {
  const social = ['twitter','facebook','instagram','linkedin','reddit','tiktok','youtube'];
  if (social.includes(PLATFORM)) return 'social';
  if (document.querySelector('meta[property="og:type"]')?.content === 'article') return 'news';
  return 'web';
})();

// ─── Selectors ────────────────────────────────────────────────────────────────
// Keep selectors simple and valid — wrap each in try-catch inside scan()
const SELECTORS = ({
  twitter:   ['article[data-testid="tweet"]'],
  facebook:  ['[role="article"]'],
  instagram: ['article'],
  linkedin:  ['div.feed-shared-update-v2', 'div.occludable-update'],
  reddit:    ['shreddit-post', 'div[data-testid="post-container"]', 'div.Post'],
  youtube:   ['ytd-video-renderer', 'ytd-rich-item-renderer'],
  tiktok:    ['article', 'div[class*="VideoCard"]'],
  web:       ['article', '[role="article"]', 'figure', 'section.post', '.post', '.entry'],
})[PLATFORM] ?? ['article', '[role="article"]'];

// Images are always scanned on every platform (universal selector, handled separately)
const IMG_SEL = 'img[src]:not([src=""])';

// ─── Extractors ───────────────────────────────────────────────────────────────
function extractContent(el) {
  try {
    switch (PLATFORM) {
      case 'twitter':   return extractTwitter(el);
      case 'facebook':  return extractFacebook(el);
      case 'instagram': return extractInstagram(el);
      case 'linkedin':  return extractLinkedIn(el);
      case 'reddit':    return extractReddit(el);
      default:          return extractGeneric(el);
    }
  } catch (e) {
    return { text: textOf(el, 200), img: null, links: [], content_type: 'text' };
  }
}

function extractTwitter(el) {
  const text     = qs(el, '[data-testid="tweetText"]')?.innerText ?? '';
  const username = qs(el, '[data-testid="User-Name"]')?.textContent?.trim() ?? '';
  const ts       = qs(el, 'time')?.getAttribute('datetime') ?? '';
  const links    = collectLinks(el, /twitter\.com|x\.com|t\.co/);
  const img      = qs(el, '[data-testid="tweetPhoto"] img') ??
                   qs(el, '[data-testid="card.layoutLarge.media"] img');
  return { text, username, timestamp: ts, links, img,
           content_type: img ? 'image' : 'post' };
}

function extractFacebook(el) {
  const text     = qs(el, '[data-ad-preview="message"]')?.innerText
                ?? textOf(el, 400);
  const username = qs(el, 'h2 a, strong a')?.textContent?.trim() ?? '';
  const links    = collectLinks(el, /facebook\.com/);
  const img      = qs(el, 'img[src*="scontent"]');
  return { text, username, links, img, content_type: img ? 'image' : 'post' };
}

function extractInstagram(el) {
  const text     = qs(el, 'h1') ?.innerText ?? textOf(el, 400);
  const username = qs(el, 'header a')?.textContent?.trim() ?? '';
  const img      = qs(el, 'img[srcset]') ?? qs(el, 'img');
  return { text, username, links: [], img, content_type: img ? 'image' : 'post' };
}

function extractLinkedIn(el) {
  const text     = qs(el, '.feed-shared-update-v2__description')?.innerText
                ?? qs(el, '.update-components-text')?.innerText
                ?? textOf(el, 400);
  const username = qs(el, '.feed-shared-actor__name, .update-components-actor__name')
                     ?.textContent?.trim() ?? '';
  const bio      = qs(el, '.feed-shared-actor__description')?.textContent?.trim() ?? '';
  const links    = collectLinks(el, /linkedin\.com/);
  const img      = qs(el, 'img[src*="licdn.com"]');
  return { text, username, bio, links, img, content_type: img ? 'image' : 'post' };
}

function extractReddit(el) {
  const title    = qs(el, 'h1, h3, [id^="post-title-"]')?.innerText ?? '';
  const body     = qs(el, '.RichTextJSON-root, [data-click-id="text"] p')?.innerText ?? '';
  const username = qs(el, 'a[href*="/user/"]')?.textContent?.replace('u/','').trim() ?? '';
  const links    = collectLinks(el, /reddit\.com/);
  const img      = qs(el, 'img[src*="redd.it"]') ?? qs(el, 'img[src*="preview"]');
  return { text: (title + ' ' + body).trim(), username, links, img,
           content_type: img ? 'image' : 'post' };
}

function extractGeneric(el) {
  const tag = el.tagName.toLowerCase();
  if (tag === 'img') {
    return { text: el.alt || el.title || '', img: el, links: [], content_type: 'image' };
  }
  if (tag === 'video') {
    return { text: el.title || '', img: null, links: [], content_type: 'video', isVideo: true };
  }
  const headline = qs(el, 'h1, h2')?.innerText ?? '';
  const body     = textOf(el, CFG.TEXT_MAX);
  const byline   = qs(el, '[rel="author"], .author, .byline')?.textContent?.trim() ?? '';
  const links    = collectLinks(el, null);
  const img      = qs(el, 'img[src]:not([src=""])');
  return { text: (headline + '\n' + body).trim(), username: byline,
           links, img, content_type: img ? 'image' : 'text' };
}

// ─── Page-level scan (news articles) ─────────────────────────────────────────
function maybeAnalyzePage() {
  if (SOURCE_TYPE === 'social') return;
  const h1  = document.querySelector('h1')?.innerText ?? '';
  const art = document.querySelector('article, main, [itemprop="articleBody"]');
  if (!h1 || !art) return;
  const text = (h1 + '\n' + art.innerText).trim().slice(0, CFG.TEXT_MAX);
  if (text.length < 80) return;

  LOG('page-level article scan:', text.slice(0, 60) + '…');
  const author  = document.querySelector('[rel="author"], .author, .byline')?.textContent?.trim() ?? '';
  const ts      = document.querySelector('time[datetime]')?.getAttribute('datetime') ?? '';
  const imgEl   = document.querySelector('article img[src], main img[src]');
  const links   = [...document.querySelectorAll('a[href^="http"]')]
    .map(a => a.href).filter(u => !u.includes(location.hostname)).slice(0, CFG.LINKS_MAX);

  const elementId = newId();
  sendAnalyze(elementId, {
    text, image_base64: null, content_type: imgEl ? 'image' : 'text',
    metadata: {
      platform: PLATFORM, source_type: SOURCE_TYPE,
      language: document.documentElement.lang?.slice(0,5) || 'en',
      timestamp: ts || new Date().toISOString(),
      ...(author && { username: author }),
      ...(links.length && { links }),
    },
  });
  // No visual overlay for page-level analysis (no element to attach to)
}

// ─── Intersection Observer ────────────────────────────────────────────────────
const iObs = new IntersectionObserver((entries) => {
  for (const e of entries) {
    if (e.isIntersecting) {
      iObs.unobserve(e.target);
      batch.add(e.target);
      scheduleFlush();
    }
  }
}, { threshold: CFG.IO_THRESHOLD });

const batch = new Set();
let flushTimer = 0;
const scheduleFlush = () => { clearTimeout(flushTimer); flushTimer = setTimeout(flush, CFG.DEBOUNCE_MS); };

function flush() {
  if (!enabled) { batch.clear(); return; }
  const items = [...batch];
  batch.clear();
  for (const el of items) {
    processElement(el).catch(e => LOG('processElement error:', e));
  }
}

// ─── Mutation Observer ────────────────────────────────────────────────────────
const mObs = new MutationObserver((muts) => {
  for (const m of muts) {
    for (const n of m.addedNodes) {
      if (n.nodeType !== Node.ELEMENT_NODE) continue;
      if (n.dataset?.mcHost != null || n.dataset?.mcWrap != null) continue;
      scan(n);
    }
  }
});

// ─── Scan ─────────────────────────────────────────────────────────────────────
function scan(root) {
  // 1. Platform-specific post selectors
  for (const sel of SELECTORS) {
    try {
      const els = root.matches(sel) ? [root] : root.querySelectorAll(sel);
      for (const el of els) {
        if (queued.has(el) || el.closest?.('[data-mc-host]')) continue;
        queued.add(el);
        iObs.observe(el);
      }
    } catch { /* invalid selector or detached node – skip */ }
  }

  // 2. Images – universal, every platform
  try {
    const imgs = root.tagName === 'IMG' ? [root] : root.querySelectorAll(IMG_SEL);
    for (const img of imgs) {
      if (queued.has(img)) continue;
      if (img.closest?.('[data-mc-host]')) continue;
      // Skip tiny icons / avatars
      const w = img.naturalWidth  || img.width  || parseInt(img.getAttribute('width'))  || 0;
      const h = img.naturalHeight || img.height || parseInt(img.getAttribute('height')) || 0;
      if (w && w < CFG.MIN_IMG_PX) continue;
      if (h && h < CFG.MIN_IMG_PX) continue;
      queued.add(img);
      iObs.observe(img);
    }
  } catch { /* skip */ }

  // 3. Videos
  try {
    const vids = root.tagName === 'VIDEO' ? [root] : root.querySelectorAll('video');
    for (const v of vids) {
      if (queued.has(v) || v.closest?.('[data-mc-host]')) continue;
      queued.add(v);
      iObs.observe(v);
    }
  } catch { /* skip */ }
}

// ─── Process element ──────────────────────────────────────────────────────────
async function processElement(el) {
  if (!document.contains(el)) return;

  const elementId  = newId();
  const extracted  = extractContent(el);
  const { text, img, links = [], username = '', handle = '', bio = '',
          timestamp = '', content_type = 'text', isVideo = false } = extracted;

  // ── Step 1: inject pending overlay IMMEDIATELY (before any async work) ──
  const overlayCreated = injectPending(el, elementId);
  LOG(`queued element ${elementId} | type=${content_type} | text="${text.slice(0,40)}"`);

  // ── Step 2: capture image asynchronously ──
  let image_base64 = null;
  try {
    if (img instanceof Element)   image_base64 = await captureImg(img);
    else if (isVideo)             image_base64 = captureVideo(el);
  } catch { /* cross-origin or capture failed – continue without image */ }

  // ── Step 3: build payload matching anonymizer AnonymizeRequest schema ──
  const payload = {
    element_id: elementId,
    text:         text.slice(0, CFG.TEXT_MAX),
    image_base64: image_base64 ?? '',
    content_type,
    metadata: {
      platform:    PLATFORM,
      source_type: SOURCE_TYPE,
      language:    document.documentElement.lang?.slice(0,5) || 'en',
      timestamp:   timestamp || new Date().toISOString(),
      ...(username && { username }),
      ...(handle   && { handle   }),
      ...(bio      && { bio      }),
      ...(links.length && { links }),
    },
  };

  sendAnalyze(elementId, payload);
}

function sendAnalyze(elementId, payload) {
  const msg = { type: 'ANALYZE', payload: { ...payload, element_id: elementId } };
  try {
    chrome.runtime.sendMessage(msg, (resp) => {
      // Consume lastError to avoid "unchecked runtime.lastError" warnings
      void chrome.runtime.lastError;
    });
  } catch (e) {
    LOG('sendMessage failed:', e);
  }
}

// ─── Canvas capture ───────────────────────────────────────────────────────────
async function captureImg(img) {
  if (!img.complete || img.naturalWidth === 0) {
    await new Promise((res, rej) => {
      const t = setTimeout(() => rej(new Error('timeout')), 3000);
      img.addEventListener('load',  () => { clearTimeout(t); res(); }, { once: true });
      img.addEventListener('error', () => { clearTimeout(t); rej(new Error('err')); }, { once: true });
    });
  }
  const sw = img.naturalWidth  || img.width  || 0;
  const sh = img.naturalHeight || img.height || 0;
  if (!sw || !sh) return null;
  const w = Math.min(sw, CFG.SNAP_MAX_W);
  const h = Math.min(sh, CFG.SNAP_MAX_H);

  // Try OffscreenCanvas first; fall back to regular canvas
  try {
    const oc = new OffscreenCanvas(w, h);
    oc.getContext('2d').drawImage(img, 0, 0, w, h);
    const blob = await oc.convertToBlob({ type: 'image/jpeg', quality: CFG.SNAP_QUALITY });
    return await blobToB64(blob);
  } catch {
    const c = document.createElement('canvas');
    c.width = w; c.height = h;
    c.getContext('2d').drawImage(img, 0, 0, w, h);
    return c.toDataURL('image/jpeg', CFG.SNAP_QUALITY).split(',')[1];
  }
}

function captureVideo(video) {
  const w = Math.min(video.videoWidth  || 320, CFG.SNAP_MAX_W);
  const h = Math.min(video.videoHeight || 240, CFG.SNAP_MAX_H);
  const c = document.createElement('canvas');
  c.width = w; c.height = h;
  c.getContext('2d').drawImage(video, 0, 0, w, h);
  return c.toDataURL('image/jpeg', CFG.SNAP_QUALITY).split(',')[1];
}

const blobToB64 = (blob) => new Promise((res, rej) => {
  const r = new FileReader();
  r.onload = () => res(r.result.split(',')[1]);
  r.onerror = rej;
  r.readAsDataURL(blob);
});

// ─── Overlay host ─────────────────────────────────────────────────────────────
const VOID = new Set(['img','input','br','hr','area','base','col','embed',
                      'link','meta','param','source','track','wbr']);
const HOST_STYLE = 'position:absolute;top:0;left:0;width:100%;height:100%;pointer-events:none;z-index:2147483647;overflow:hidden;';

function mountHost(el) {
  if (!el?.tagName) return null;
  const tag = el.tagName.toLowerCase();

  if (VOID.has(tag)) {
    // img / void: wrap in a positioned span
    if (!el.parentNode || el.parentNode === document.body || el.parentNode === document.documentElement) {
      // Can't safely wrap – inject a fixed-position overlay based on bounding rect instead
      return mountFixed(el);
    }
    const wrap = document.createElement('span');
    wrap.dataset.mcWrap = '';
    wrap.style.cssText = 'position:relative;display:inline-block;line-height:0;vertical-align:bottom;';
    el.parentNode.insertBefore(wrap, el);
    wrap.appendChild(el);

    const host = document.createElement('span');
    host.dataset.mcHost = '';
    host.style.cssText = HOST_STYLE;
    wrap.appendChild(host);
    return host;
  }

  // Block/container element
  const cs = getComputedStyle(el);
  if (cs.position === 'static') el.style.position = 'relative';
  // If overflow:hidden, the bottom bar would be clipped — allow visible overflow for host
  el.style.overflow = 'visible';

  const host = document.createElement('div');
  host.dataset.mcHost = '';
  host.style.cssText = HOST_STYLE;
  el.appendChild(host);
  return host;
}

function mountFixed(el) {
  // Fallback: a fixed-position host tracked to element's viewport rect
  const rect = el.getBoundingClientRect();
  if (rect.width < 10 || rect.height < 10) return null;

  const host = document.createElement('div');
  host.dataset.mcHost = '';
  host.style.cssText = [
    'position:fixed',
    `top:${rect.top + window.scrollY}px`,
    `left:${rect.left + window.scrollX}px`,
    `width:${rect.width}px`,
    `height:${rect.height}px`,
    'pointer-events:none',
    'z-index:2147483647',
    'overflow:hidden',
  ].join(';') + ';';
  document.body.appendChild(host);
  return host;
}

// ─── Pending indicator ────────────────────────────────────────────────────────
function injectPending(el, elementId) {
  let host;
  try { host = mountHost(el); } catch { host = null; }
  // Even if mounting fails, store a stub so applyResult can still record history
  const shadow = host ? host.attachShadow({ mode: 'closed' }) : null;
  if (shadow) {
    shadow.innerHTML = `
      <style>
        .d{position:absolute;bottom:6px;right:6px;width:7px;height:7px;
           border-radius:50%;background:rgba(255,255,255,.4);
           animation:p 1.4s ease-in-out infinite}
        @keyframes p{0%,100%{opacity:.3;transform:scale(.9)}50%{opacity:1;transform:scale(1.25)}}
      </style><div class="d"></div>`;
  }
  overlays.set(elementId, { host, shadow });
  return !!host;
}

// ─── Apply result ─────────────────────────────────────────────────────────────
function applyResult(elementId, result) {
  const { threat_level, verdict, axes } = result;

  // Always save to history regardless of overlay state
  saveHistory(elementId, result);

  const ov = overlays.get(elementId);

  if (threat_level < sensitivity) {
    if (ov?.host) { ov.host.remove(); }
    overlays.delete(elementId);
    return;
  }

  if (!ov?.host || !ov?.shadow) {
    overlays.delete(elementId);
    return;
  }

  const { host, shadow } = ov;
  const tc = tColor(threat_level);
  shadow.innerHTML = buildShadow(threat_level, verdict, axes, threat_level >= blurThreshold, tc);
  host.style.pointerEvents = 'auto';

  const blur    = shadow.querySelector('.blur');
  const reveal  = shadow.querySelector('.reveal');
  const factBtn = shadow.querySelector('.fact');
  const pop     = shadow.querySelector('.pop');
  const closeX  = shadow.querySelector('.pop-x');

  reveal?.addEventListener('click', (e) => {
    e.stopPropagation();
    if (blur) { blur.style.opacity = '0'; blur.style.pointerEvents = 'none'; }
    setTimeout(() => blur?.remove(), 280);
  });
  factBtn?.addEventListener('click', (e) => { e.stopPropagation(); pop?.classList.toggle('pop--on'); });
  closeX?.addEventListener('click',  (e) => { e.stopPropagation(); pop?.classList.remove('pop--on'); });
  shadow.addEventListener('click', (e) => {
    if (pop && !pop.contains(e.target) && e.target !== factBtn) pop.classList.remove('pop--on');
  });

  LOG(`result ${elementId} | verdict=${verdict} | threat=${threat_level.toFixed(2)}`);
}

// ─── Threat colour ────────────────────────────────────────────────────────────
const tColor = (v) => v < 0.4 ? colors.safe : v < 0.7 ? colors.warning : colors.danger;

function axisScore(ax) {
  if (!ax) return null;
  if ('category'         in ax) return (ax.category === 'altered' ? 0.85 : ax.category === 'ai_generated' ? 0.7 : 0.1) * (ax.confidence ?? 1);
  if ('is_misleading'    in ax) return ax.is_misleading    ? (ax.confidence ?? 0.5) : 0;
  if ('credibility_score' in ax) return 1 - (ax.credibility_score ?? 0.5);
  if ('is_misinformation' in ax) return ax.is_misinformation ? (ax.confidence ?? 0.5) : 0;
  return null;
}

// ─── Shadow DOM ───────────────────────────────────────────────────────────────
function buildShadow(level, verdict, axes, doBlur, tc) {
  const pct  = Math.round(level * 100);
  const AXES = [
    { icon:'🧠', label:'Authenticity', data: axes?.classifier, detail: axes?.classifier?.reasoning ?? axes?.classifier?.category ?? '—' },
    { icon:'🔄', label:'Consistency',  data: axes?.context,    detail: axes?.context?.explanation   ?? '—' },
    { icon:'🌐', label:'Source',       data: axes?.source,     detail: axes?.source?.risk_level      ?? '—' },
    { icon:'📡', label:'Truth',        data: axes?.truth,      detail: axes?.truth?.explanation      ?? '—' },
  ];

  const badges = AXES.map(({ icon, label, data, detail }) => {
    const sc  = axisScore(data);
    const col = sc != null ? tColor(sc) : 'rgba(255,255,255,.25)';
    return `<span class="bdg" style="border-color:${col}" title="${esc(label+': '+detail)}">${icon}</span>`;
  }).join('');

  const blurBlock = doBlur ? `
    <div class="blur">
      <div class="blur-in">
        <svg width="36" height="36" viewBox="0 0 24 24" fill="none" stroke="${colors.danger}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
          <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/>
        </svg>
        <span class="vl">${verdict}</span>
        <button class="reveal">Reveal content</button>
      </div>
    </div>` : '';

  const bar = `
    <div class="bar">
      <div class="mtr"><div class="mtr-f" style="width:${pct}%;background:${tc}"></div></div>
      <div class="bar-r">
        <div class="bdgs">${badges}</div>
        <span class="vc" style="color:${tc}">${verdict}</span>
        <button class="fact" title="Fact-check details">
          <svg viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="2"><circle cx="8" cy="8" r="6.5"/><path d="M8 7v5M8 5v.5"/></svg>
        </button>
      </div>
    </div>`;

  const popover = buildPopover(verdict, axes, AXES, tc);
  return `<style>${CSS(tc)}</style>${blurBlock}${bar}${popover}`;
}

function buildPopover(verdict, axes, AXES, tc) {
  const items = AXES.map(({ icon, label, data, detail }) => {
    const sc  = axisScore(data);
    const pct = sc != null ? Math.round(sc * 100) + '%' : '—';
    const col = sc != null ? tColor(sc) : 'rgba(255,255,255,.3)';
    return `<div class="ai"><span class="ai-ic">${icon}</span>
      <div class="ai-b"><div class="ai-n">${label}</div><div class="ai-d">${esc(detail)}</div></div>
      <span class="ai-p" style="color:${col}">${pct}</span></div>`;
  }).join('');

  const truth = axes?.truth;
  const corr  = truth?.corrected_version
    ? `<div class="ps"><div class="pl">Real Deal</div><div class="pt">${esc(truth.corrected_version)}</div></div>` : '';
  const srcs  = truth?.sources?.length
    ? `<div class="ps"><div class="pl">Sources</div>${truth.sources.map(s=>`<a class="sl" href="${esc(s.url)}" target="_blank" rel="noopener">${esc(s.title||s.url)}</a>`).join('')}</div>` : '';

  return `<div class="pop">
    <button class="pop-x">✕</button>
    <div class="ph" style="color:${tc}">Verification — ${verdict}</div>
    <div class="ps"><div class="al">${items}</div></div>
    ${corr}${srcs}
  </div>`;
}

const CSS = (tc) => `
*,*::before,*::after{box-sizing:border-box;margin:0;padding:0}
:host{display:block;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif}
.blur{position:absolute;inset:0;backdrop-filter:blur(14px) saturate(.7);-webkit-backdrop-filter:blur(14px) saturate(.7);
  background:rgba(13,13,13,.55);display:flex;align-items:center;justify-content:center;z-index:3;transition:opacity .28s}
.blur-in{display:flex;flex-direction:column;align-items:center;gap:10px;padding:20px;text-align:center}
.vl{font-size:11px;font-weight:800;letter-spacing:.14em;text-transform:uppercase;color:${colors.danger}}
.reveal{margin-top:2px;padding:6px 16px;border-radius:20px;background:rgba(255,255,255,.08);
  border:1px solid rgba(255,255,255,.18);color:#fff;font-size:11px;cursor:pointer;pointer-events:auto;
  transition:background .18s}
.reveal:hover{background:rgba(255,255,255,.18)}
.bar{position:absolute;bottom:0;left:0;right:0;background:rgba(13,13,13,.92);
  backdrop-filter:blur(10px);border-top:1px solid rgba(255,255,255,.06);z-index:4;
  animation:su .28s cubic-bezier(.22,.68,0,1.15) forwards}
@keyframes su{from{transform:translateY(100%);opacity:0}to{transform:translateY(0);opacity:1}}
.mtr{height:3px;background:rgba(255,255,255,.07);overflow:hidden}
.mtr-f{height:100%;border-radius:1px}
.bar-r{display:flex;align-items:center;gap:7px;padding:5px 9px}
.bdgs{display:flex;gap:3px}
.bdg{display:inline-flex;align-items:center;justify-content:center;width:22px;height:22px;
  border-radius:50%;border:1.5px solid;font-size:11px;cursor:default;transition:transform .12s}
.bdg:hover{transform:scale(1.18)}
.vc{font-size:9px;font-weight:800;letter-spacing:.1em;text-transform:uppercase;margin-left:auto}
.fact{width:21px;height:21px;border-radius:50%;flex-shrink:0;background:rgba(255,255,255,.08);
  border:1px solid rgba(255,255,255,.18);color:#bbb;cursor:pointer;
  display:flex;align-items:center;justify-content:center;padding:4px;pointer-events:auto;transition:background .15s}
.fact:hover{background:rgba(255,255,255,.18);color:#fff}
.fact svg{width:12px;height:12px}
.pop{position:absolute;bottom:100%;left:0;right:0;background:rgba(11,11,13,.97);
  border:1px solid rgba(255,255,255,.07);border-radius:10px 10px 0 0;padding:14px 14px 10px;
  z-index:5;color:#d4d4d4;transform:translateY(6px);opacity:0;
  transition:transform .22s,opacity .22s;pointer-events:none;max-height:320px;overflow-y:auto}
.pop--on{transform:translateY(0);opacity:1;pointer-events:auto}
.pop::-webkit-scrollbar{width:3px}
.pop::-webkit-scrollbar-thumb{background:rgba(255,255,255,.12);border-radius:2px}
.pop-x{position:absolute;top:9px;right:9px;background:none;border:none;color:#555;
  font-size:13px;cursor:pointer;display:flex;align-items:center;justify-content:center;transition:color .15s}
.pop-x:hover{color:#ccc}
.ph{font-size:10px;font-weight:800;letter-spacing:.11em;text-transform:uppercase;margin-bottom:12px;padding-right:20px}
.ps{margin-bottom:12px}
.pl{font-size:9px;font-weight:700;letter-spacing:.1em;text-transform:uppercase;color:#555;margin-bottom:6px}
.pt{font-size:12px;line-height:1.55;color:#aaa}
.al{display:flex;flex-direction:column;gap:5px}
.ai{display:flex;align-items:flex-start;gap:8px;padding:7px 8px;border-radius:7px;background:rgba(255,255,255,.03)}
.ai-ic{font-size:14px;line-height:1;flex-shrink:0;padding-top:1px}
.ai-b{flex:1;min-width:0}
.ai-n{font-size:9px;font-weight:700;letter-spacing:.08em;text-transform:uppercase;color:#555;margin-bottom:2px}
.ai-d{font-size:11px;color:#999;word-break:break-word}
.ai-p{font-size:11px;font-weight:700;font-variant-numeric:tabular-nums;flex-shrink:0}
.sl{display:block;font-size:11px;color:#5b9cf6;text-decoration:none;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;margin-bottom:3px}
.sl:hover{text-decoration:underline}
`;

// ─── History ──────────────────────────────────────────────────────────────────
function saveHistory(elementId, result) {
  chrome.storage.local.get(['history'], ({ history = [] }) => {
    history.unshift({
      id: elementId, url: location.href,
      title: document.title.slice(0, 80),
      verdict: result.verdict,
      threat_level: result.threat_level,
      ts: Date.now(),
    });
    chrome.storage.local.set({ history: history.slice(0, 50) });
  });
}

// ─── Helpers ──────────────────────────────────────────────────────────────────
function qs(el, sel)     { try { return el.querySelector(sel); } catch { return null; } }
function textOf(el, max) { return el.textContent?.replace(/\s+/g,' ').trim().slice(0, max) ?? ''; }
function collectLinks(el, excludeRe) {
  try {
    return [...el.querySelectorAll('a[href^="http"]')]
      .map(a => a.href)
      .filter(u => !excludeRe || !excludeRe.test(u))
      .slice(0, CFG.LINKS_MAX);
  } catch { return []; }
}
function esc(s) {
  return String(s||'').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
}

// ─── Message listener ─────────────────────────────────────────────────────────
chrome.runtime.onMessage.addListener((msg) => {
  if (msg.type === 'ANALYSIS_RESULT') {
    try { applyResult(msg.element_id, msg.result); } catch (e) { LOG('applyResult error:', e); }
  }
  if (msg.type === 'MC_TOGGLE') enabled = msg.enabled;
});

// ─── SPA navigation ───────────────────────────────────────────────────────────
let lastUrl = location.href;
function onNav() {
  if (location.href === lastUrl) return;
  lastUrl = location.href;
  setTimeout(() => { scan(document.body); maybeAnalyzePage(); }, 700);
}
window.addEventListener('popstate', onNav);
const _push = history.pushState.bind(history);
const _rep  = history.replaceState.bind(history);
history.pushState    = (...a) => { _push(...a);    onNav(); };
history.replaceState = (...a) => { _rep(...a);     onNav(); };

// ─── Init ─────────────────────────────────────────────────────────────────────
function init() {
  LOG(`init | platform=${PLATFORM} | readyState=${document.readyState}`);
  mObs.observe(document.body, { childList: true, subtree: true });

  // Immediate scan of what's already in the DOM
  try { scan(document.body); } catch (e) { LOG('initial scan error:', e); }

  // Delayed re-scan for SPAs that render content after document_idle
  setTimeout(() => {
    try { scan(document.body); } catch (e) { LOG('delayed scan error:', e); }
    maybeAnalyzePage();
  }, 1500);
}

if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', init, { once: true });
} else {
  init();
}

})();
