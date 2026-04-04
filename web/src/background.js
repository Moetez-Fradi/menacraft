const EXTENSION_MESSAGE = {
  SUBMIT_CAPTURE_BATCH: 'SUBMIT_CAPTURE_BATCH',
  EXPORT_CAPTURE_LOG: 'EXPORT_CAPTURE_LOG',
  GET_CAPTURE_STATS: 'GET_CAPTURE_STATS'
};

const STORAGE_KEYS = {
  SAVED_POST_MAP: 'savedPostMap',
  CAPTURE_LOG: 'captureLog',
  UNEXPORTED_COUNT: 'unexportedCount'
};

const MAX_SAVED_POST_KEYS = 5000;
const MAX_CAPTURE_LOG_ITEMS = 5000;

function sanitizeFilenamePart(value) {
  return value
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/^-+|-+$/g, '')
    .slice(0, 60) || 'unknown';
}

function buildExportFileName(hostname, timestamp) {
  const safeHost = sanitizeFilenamePart(hostname);
  const fileTimestamp = new Date(timestamp).toISOString().replace(/[:.]/g, '-');
  return `captures/${safeHost}/${fileTimestamp}-capture-export.json`;
}

function resolveCaptureHostname(capture) {
  const sourceUrl = capture?.sourceUrl;
  if (!sourceUrl) {
    return 'unknown-source';
  }

  try {
    return new URL(sourceUrl).hostname || 'unknown-source';
  } catch {
    return 'unknown-source';
  }
}

function groupCapturesByHostname(captureLog) {
  const groups = new Map();

  for (const capture of captureLog) {
    const hostname = resolveCaptureHostname(capture);

    if (!groups.has(hostname)) {
      groups.set(hostname, []);
    }

    groups.get(hostname).push(capture);
  }

  return groups;
}

function sanitizeCapturedText(value) {
  const text = String(value || '').replace(/\s+/g, ' ').trim();
  if (!text) {
    return '';
  }

  return text
    .replace(/\b(Like|Reply|Share|Comment|React)\b/gi, ' ')
    .replace(/\s+/g, ' ')
    .trim();
}

function isUsefulMediaUrl(url) {
  if (!url || typeof url !== 'string') {
    return false;
  }

  if (url.startsWith('data:')) {
    return false;
  }

  if (/emoji\.php|\/emoji\//i.test(url)) {
    return false;
  }

  return true;
}

function normalizeLegacyPost(capture) {
  const post = capture?.post || {};
  const textBlocks = Array.isArray(post.textBlocks) ? post.textBlocks : [];
  const cleanedText = sanitizeCapturedText(textBlocks.join(' ').trim());

  const images = ((post.media && post.media.images) || [])
    .filter((image) => isUsefulMediaUrl(image?.src))
    .filter((image) => (image?.width || 0) >= 80 && (image?.height || 0) >= 80)
    .map((image) => ({
      url: image.src,
      width: image.width || null,
      height: image.height || null
    }));

  const videos = ((post.media && post.media.videos && post.media.videos.htmlVideos) || [])
    .map((video) => ({
      url: video?.src || (Array.isArray(video?.sources) ? video.sources[0] : null),
      posterUrl: video?.poster || null,
      durationSeconds: Number.isFinite(video?.duration) ? video.duration : null
    }))
    .filter((video) => isUsefulMediaUrl(video.url));

  let type = 'text_only';
  if (videos.length > 0 && cleanedText) {
    type = 'video_with_text';
  } else if (videos.length > 0) {
    type = 'video_only';
  } else if (images.length > 0 && cleanedText) {
    type = 'text_with_image';
  } else if (images.length > 0) {
    type = 'image_only';
  }

  return {
    postId: post.postHash || post.id || null,
    type,
    platform: post.platformHint || resolveCaptureHostname(capture),
    sourceUrl: capture?.sourceUrl || post.pageUrl || null,
    postUrl: post.postUrl || null,
    account: {
      name: post.author || null,
      handleOrProfileUrl: post.authorProfileUrl || null
    },
    publishedAt: post.postTimestamp || null,
    capturedAt: capture?.capturedAt || post.capturedAt || null,
    text: cleanedText || null,
    media: {
      images,
      videos
    }
  };
}

function toExportPost(capture) {
  if (capture?.post && capture.post.type && capture.post.media) {
    return capture.post;
  }

  return normalizeLegacyPost(capture);
}

async function downloadCaptureExport(payload, filename) {
  const content = JSON.stringify(payload, null, 2);
  const encoded = encodeURIComponent(content);
  const dataUrl = `data:application/json;charset=utf-8,${encoded}`;

  await chrome.downloads.download({
    url: dataUrl,
    filename,
    saveAs: false,
    conflictAction: 'uniquify'
  });
}

async function getSavedPostMap() {
  const stored = await chrome.storage.local.get(STORAGE_KEYS.SAVED_POST_MAP);
  return stored[STORAGE_KEYS.SAVED_POST_MAP] || {};
}

async function getCaptureLog() {
  const stored = await chrome.storage.local.get(STORAGE_KEYS.CAPTURE_LOG);
  const captureLog = stored[STORAGE_KEYS.CAPTURE_LOG];
  return Array.isArray(captureLog) ? captureLog : [];
}

async function getUnexportedCount() {
  const stored = await chrome.storage.local.get(STORAGE_KEYS.UNEXPORTED_COUNT);
  const value = stored[STORAGE_KEYS.UNEXPORTED_COUNT];
  return Number.isFinite(value) ? value : 0;
}

function trimSavedPostMap(savedPostMap) {
  const entries = Object.entries(savedPostMap);
  if (entries.length <= MAX_SAVED_POST_KEYS) {
    return savedPostMap;
  }

  const trimmedEntries = entries
    .sort((left, right) => left[1] - right[1])
    .slice(entries.length - MAX_SAVED_POST_KEYS);

  return Object.fromEntries(trimmedEntries);
}

async function saveSavedPostMap(savedPostMap) {
  const trimmed = trimSavedPostMap(savedPostMap);
  await chrome.storage.local.set({
    [STORAGE_KEYS.SAVED_POST_MAP]: trimmed
  });
}

function trimCaptureLog(captureLog) {
  if (captureLog.length <= MAX_CAPTURE_LOG_ITEMS) {
    return captureLog;
  }

  return captureLog.slice(captureLog.length - MAX_CAPTURE_LOG_ITEMS);
}

async function saveCaptureState(savedPostMap, captureLog, addedCount) {
  const trimmedCaptureLog = trimCaptureLog(captureLog);
  const currentUnexportedCount = await getUnexportedCount();
  const increment = Number.isFinite(addedCount) ? Math.max(addedCount, 0) : 0;
  const nextUnexportedCount = Math.min(currentUnexportedCount + increment, MAX_CAPTURE_LOG_ITEMS);

  await chrome.storage.local.set({
    [STORAGE_KEYS.SAVED_POST_MAP]: trimSavedPostMap(savedPostMap),
    [STORAGE_KEYS.CAPTURE_LOG]: trimmedCaptureLog,
    [STORAGE_KEYS.UNEXPORTED_COUNT]: nextUnexportedCount
  });

  await updateActionBadge(nextUnexportedCount);
}

async function updateActionBadge(count) {
  const badgeValue = count > 999 ? '999+' : String(count);

  await chrome.action.setBadgeText({
    text: count > 0 ? badgeValue : ''
  });

  await chrome.action.setBadgeBackgroundColor({ color: '#2563eb' });
}

async function processCaptureBatch(payload) {
  if (!payload || !Array.isArray(payload.posts) || payload.posts.length === 0) {
    return { savedCount: 0, skippedCount: 0 };
  }

  try {
    const sourceUrl = payload.sourceUrl || '';
    const baseTimestamp = Date.now();
    const savedPostMap = await getSavedPostMap();
    const captureLog = await getCaptureLog();

    let savedCount = 0;
    let skippedCount = 0;
    const acceptedCaptures = [];

    for (let index = 0; index < payload.posts.length; index += 1) {
      const post = payload.posts[index];
      const postHash = post?.postHash;

      if (!postHash || savedPostMap[postHash]) {
        skippedCount += 1;
        continue;
      }

      const capture = {
        capturedAt: new Date(baseTimestamp + index).toISOString(),
        extractorVersion: '0.4.0',
        sourceUrl,
        sourceTitle: payload.sourceTitle || '',
        trigger: payload.trigger || 'auto',
        post
      };

      acceptedCaptures.push(capture);

      savedPostMap[postHash] = baseTimestamp + index;
      savedCount += 1;
    }

    if (acceptedCaptures.length > 0) {
      captureLog.push(...acceptedCaptures);
    }

    await saveCaptureState(savedPostMap, captureLog, acceptedCaptures.length);

    return { savedCount, skippedCount };
  } catch (error) {
    console.error('Automatic capture processing failed:', error);
    return { savedCount: 0, skippedCount: 0, error: String(error) };
  }
}

async function exportCaptureLog() {
  const captureLog = await getCaptureLog();

  if (captureLog.length === 0) {
    return { exportedCount: 0, message: 'No captures to export yet.' };
  }

  const now = Date.now();
  const captureGroups = groupCapturesByHostname(captureLog);
  const exportedFiles = [];

  for (const [hostname, captures] of captureGroups.entries()) {
    const posts = captures.map(toExportPost).filter(Boolean);
    if (posts.length === 0) {
      continue;
    }

    const filename = buildExportFileName(hostname, now);

    const payload = {
      exportedAt: new Date(now).toISOString(),
      sourceHostname: hostname,
      count: posts.length,
      posts
    };

    await downloadCaptureExport(payload, filename);
    exportedFiles.push(filename);
  }

  await chrome.storage.local.set({
    [STORAGE_KEYS.UNEXPORTED_COUNT]: 0
  });
  await updateActionBadge(0);

  return {
    exportedCount: captureLog.length,
    exportedFileCount: exportedFiles.length,
    exportedFiles
  };
}

async function getCaptureStats() {
  const captureLog = await getCaptureLog();
  return {
    captureCount: captureLog.length,
    unexportedCount: await getUnexportedCount(),
    latestCapturedAt: captureLog.length > 0 ? captureLog[captureLog.length - 1].capturedAt : null
  };
}

chrome.runtime.onInstalled.addListener(async () => {
  try {
    const unexportedCount = await getUnexportedCount();
    await updateActionBadge(unexportedCount);
  } catch (error) {
    console.error('Failed to initialize badge state:', error);
  }
});

chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  if (message?.type === EXTENSION_MESSAGE.SUBMIT_CAPTURE_BATCH) {
    processCaptureBatch(message.payload)
      .then((result) => sendResponse(result))
      .catch((error) => {
        sendResponse({ savedCount: 0, skippedCount: 0, error: String(error) });
      });

    return true;
  }

  if (message?.type === EXTENSION_MESSAGE.EXPORT_CAPTURE_LOG) {
    exportCaptureLog()
      .then((result) => sendResponse(result))
      .catch((error) => {
        sendResponse({ exportedCount: 0, error: String(error) });
      });

    return true;
  }

  if (message?.type === EXTENSION_MESSAGE.GET_CAPTURE_STATS) {
    getCaptureStats()
      .then((result) => sendResponse(result))
      .catch((error) => {
        sendResponse({ captureCount: 0, latestCapturedAt: null, error: String(error) });
      });

    return true;
  }

  if (!message?.type) {
    return;
  }
});
