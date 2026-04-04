const CAPTURE_SELECTORS = [
  'article',
  '[role="article"]',
  'main article',
  '[data-testid*="post"]',
  '[id*="post"]',
  '.post',
  '.feed-item',
  '.story',
  '.entry',
  '.content'
];

const HOST_SPECIFIC_SELECTORS = {
  facebook: [
    'div[role="feed"] div[role="article"]',
    'div[data-pagelet*="FeedUnit"]',
    'div[data-testid*="story"]',
    'div[aria-posinset]',
    'div[data-ad-preview="message"]'
  ],
  instagram: [
    'main article',
    'article[role="presentation"]',
    'section main article'
  ],
  medium: [
    'article',
    'main article',
    'div[data-testid="storyContent"]'
  ],
  reddit: [
    'shreddit-post',
    'article[data-testid="post-container"]',
    'div[data-testid="post-container"]'
  ],
  cnn: [
    'article',
    '.container__item',
    '.card'
  ]
};

const EXTENSION_MESSAGE = {
  SUBMIT_CAPTURE_BATCH: 'SUBMIT_CAPTURE_BATCH'
};

const SUPPORTED_HOST_PATTERNS = [
  /(^|\.)facebook\.com$/i,
  /(^|\.)instagram\.com$/i,
  /(^|\.)medium\.com$/i,
  /(^|\.)reddit\.com$/i,
  /(^|\.)cnn\.com$/i
];

const sentPostHashes = new Set();

let scheduledCaptureHandle = null;
let periodicCaptureHandle = null;
let lastKnownUrl = window.location.href;

function normalizeWhitespace(text) {
  return text.replace(/\s+/g, ' ').trim();
}

function uniq(values) {
  return [...new Set(values.filter(Boolean))];
}

function getAbsoluteUrl(urlLike) {
  try {
    return new URL(urlLike, window.location.href).href;
  } catch {
    return null;
  }
}

function simpleHash(value) {
  let hash = 5381;

  for (let index = 0; index < value.length; index += 1) {
    hash = (hash * 33) ^ value.charCodeAt(index);
  }

  return `h${(hash >>> 0).toString(16)}`;
}

function extractTextBlocks(root) {
  const preferred = root.querySelectorAll('p, h1, h2, h3, li, blockquote, span, div[dir="auto"]');
  const blocks = [];
  const blacklist = /^(like|reply|share|comment|react)$/i;

  preferred.forEach((node) => {
    const text = normalizeWhitespace(node.textContent || '');
    if (!text) {
      return;
    }

    if (blacklist.test(text)) {
      return;
    }

    if (text.length >= 8) {
      blocks.push(text);
    }
  });

  if (blocks.length > 0) {
    return uniq(blocks).slice(0, 50);
  }

  const fallback = normalizeWhitespace(root.innerText || root.textContent || '');
  return fallback ? [fallback] : [];
}

function extractLinks(root) {
  const links = [...root.querySelectorAll('a[href]')].map((anchor) => {
    const href = getAbsoluteUrl(anchor.getAttribute('href') || '');
    return {
      href,
      text: normalizeWhitespace(anchor.textContent || '')
    };
  });

  return links
    .filter((item) => item.href)
    .slice(0, 80);
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

function extractImages(root) {
  const images = [...root.querySelectorAll('img')].map((image) => {
    const src = image.currentSrc || image.src || image.getAttribute('src') || '';
    return {
      url: getAbsoluteUrl(src),
      width: image.naturalWidth || null,
      height: image.naturalHeight || null
    };
  });

  return images
    .filter((image) => isUsefulMediaUrl(image.url))
    .filter((image) => (image.width || 0) >= 80 && (image.height || 0) >= 80)
    .slice(0, 20);
}

function extractVideos(root) {
  const htmlVideos = [...root.querySelectorAll('video')].map((video) => {
    const srcAttr = video.currentSrc || video.src || video.getAttribute('src') || '';
    const sourceElements = [...video.querySelectorAll('source[src]')].map((source) =>
      getAbsoluteUrl(source.getAttribute('src') || '')
    );

    const resolvedSrc = getAbsoluteUrl(srcAttr);
    const sources = uniq(sourceElements).filter((source) => isUsefulMediaUrl(source));

    return {
      url: isUsefulMediaUrl(resolvedSrc) ? resolvedSrc : (sources[0] || null),
      posterUrl: getAbsoluteUrl(video.poster || ''),
      durationSeconds: Number.isFinite(video.duration) ? video.duration : null
    };
  });

  return htmlVideos.filter((item) => isUsefulMediaUrl(item.url)).slice(0, 10);
}

function inferAuthor(root) {
  const ariaLabel = root.getAttribute('aria-label') || '';
  const ariaMatch = ariaLabel.match(/comment by\s+(.+?)\s+(?:\d+\s*[a-z]+|yesterday|today|just now)/i);
  if (ariaMatch && ariaMatch[1]) {
    return normalizeWhitespace(ariaMatch[1]);
  }

  const profileAnchor = [...root.querySelectorAll('a[href]')]
    .find((anchor) => {
      const href = anchor.getAttribute('href') || '';
      const text = normalizeWhitespace(anchor.textContent || '');
      return /facebook\.com\/(profile\.php\?|[A-Za-z0-9_.-]+)/i.test(href) && text.length >= 2;
    });

  if (profileAnchor) {
    return normalizeWhitespace(profileAnchor.textContent || '');
  }

  const candidates = [
    root.querySelector('[rel="author"]'),
    root.querySelector('[class*="author"]'),
    root.querySelector('[data-testid*="author"]')
  ].filter(Boolean);

  for (const candidate of candidates) {
    const text = normalizeWhitespace(candidate.textContent || '');
    if (text.length >= 2 && text.length <= 120) {
      return text;
    }
  }

  return null;
}

function inferAuthorProfileUrl(root) {
  const profileAnchor = [...root.querySelectorAll('a[href]')]
    .find((anchor) => {
      const href = anchor.getAttribute('href') || '';
      return /facebook\.com\/(profile\.php\?|[A-Za-z0-9_.-]+)/i.test(href);
    });

  if (!profileAnchor) {
    return null;
  }

  return getAbsoluteUrl(profileAnchor.getAttribute('href') || '');
}

function inferTimestamp(root) {
  const timeElement = root.querySelector('time');
  if (timeElement) {
    const datetime = timeElement.getAttribute('datetime');
    if (datetime) {
      return datetime;
    }

    const displayed = normalizeWhitespace(timeElement.textContent || '');
    if (displayed) {
      return displayed;
    }
  }

  const generic = root.querySelector('[class*="time"], [data-testid*="time"]');
  if (!generic) {
    return null;
  }

  const value = normalizeWhitespace(generic.textContent || '');
  return value || null;
}

function getCaptureSelectorsForHost(hostname) {
  const selectors = [...CAPTURE_SELECTORS];

  if (/(^|\.)facebook\.com$/i.test(hostname)) {
    selectors.push(...HOST_SPECIFIC_SELECTORS.facebook);
  } else if (/(^|\.)instagram\.com$/i.test(hostname)) {
    selectors.push(...HOST_SPECIFIC_SELECTORS.instagram);
  } else if (/(^|\.)medium\.com$/i.test(hostname)) {
    selectors.push(...HOST_SPECIFIC_SELECTORS.medium);
  } else if (/(^|\.)reddit\.com$/i.test(hostname)) {
    selectors.push(...HOST_SPECIFIC_SELECTORS.reddit);
  } else if (/(^|\.)cnn\.com$/i.test(hostname)) {
    selectors.push(...HOST_SPECIFIC_SELECTORS.cnn);
  }

  return uniq(selectors);
}

function pickCandidates() {
  const seen = new Set();
  const nodes = [];
  const selectors = getCaptureSelectorsForHost(window.location.hostname);

  for (const selector of selectors) {
    document.querySelectorAll(selector).forEach((node) => {
      if (!(node instanceof HTMLElement)) {
        return;
      }

      if (seen.has(node)) {
        return;
      }

      seen.add(node);
      nodes.push(node);
    });
  }

  return nodes;
}

function inferPostUrl(links) {
  const postLink = links.find((link) => {
    const href = link?.href || '';
    return /\/posts\/|\/reel\/|\/videos\/|\/p\//i.test(href);
  });

  return postLink ? postLink.href : null;
}

function classifyPostType(text, images, videos) {
  if (videos.length > 0 && text) {
    return 'video_with_text';
  }

  if (videos.length > 0) {
    return 'video_only';
  }

  if (images.length > 0 && text) {
    return 'text_with_image';
  }

  if (images.length > 0) {
    return 'image_only';
  }

  return 'text_only';
}

function isLikelyCommentNode(node, text) {
  const ariaLabel = (node.getAttribute('aria-label') || '').toLowerCase();
  if (ariaLabel.startsWith('comment by')) {
    return true;
  }

  const compact = text.toLowerCase();
  return /\blike\s+reply\b/.test(compact);
}

function extractPost(node, index) {
  const textBlocks = extractTextBlocks(node);
  const text = normalizeWhitespace(textBlocks.join(' '));

  if (!text || text.length < 8) {
    return null;
  }

  const links = extractLinks(node);
  const images = extractImages(node);
  const videos = extractVideos(node);

  if (isLikelyCommentNode(node, text) && images.length === 0 && videos.length === 0) {
    return null;
  }

  const pageUrl = window.location.href;
  const author = inferAuthor(node);
  const authorProfileUrl = inferAuthorProfileUrl(node);
  const postTimestamp = inferTimestamp(node);
  const postUrl = inferPostUrl(links);
  const type = classifyPostType(text, images, videos);
  const hashInput = [
    window.location.hostname,
    postUrl || pageUrl,
    author || '',
    postTimestamp || '',
    text,
    images.map((image) => image.url).join('|'),
    videos.map((video) => video.url).join('|'),
    links.map((link) => link.href).join('|')
  ].join('::');

  const postHash = simpleHash(hashInput);

  return {
    postId: postHash,
    postHash,
    type,
    platform: window.location.hostname,
    sourceUrl: pageUrl,
    postUrl,
    account: {
      name: author,
      handleOrProfileUrl: authorProfileUrl
    },
    publishedAt: postTimestamp,
    capturedAt: new Date().toISOString(),
    text,
    media: {
      images,
      videos
    }
  };
}

function runExtraction() {
  const candidates = pickCandidates();
  const posts = candidates
    .map((node, index) => extractPost(node, index))
    .filter(Boolean)
    .slice(-300);

  return {
    sourceUrl: window.location.href,
    sourceTitle: document.title,
    extractedAt: new Date().toISOString(),
    posts
  };
}

function isSupportedHost(hostname) {
  return SUPPORTED_HOST_PATTERNS.some((pattern) => pattern.test(hostname));
}

function collectNewPosts(posts) {
  const newPosts = [];

  for (const post of posts) {
    if (!post?.postHash) {
      continue;
    }

    if (sentPostHashes.has(post.postHash)) {
      continue;
    }

    sentPostHashes.add(post.postHash);
    newPosts.push(post);
  }

  return newPosts;
}

async function runAutoCapture(trigger) {
  if (!isSupportedHost(window.location.hostname)) {
    return;
  }

  const extraction = runExtraction();
  const newPosts = collectNewPosts(extraction.posts);
  if (newPosts.length === 0) {
    return;
  }

  try {
    await chrome.runtime.sendMessage({
      type: EXTENSION_MESSAGE.SUBMIT_CAPTURE_BATCH,
      payload: {
        sourceUrl: extraction.sourceUrl,
        sourceTitle: extraction.sourceTitle,
        extractedAt: extraction.extractedAt,
        trigger,
        posts: newPosts
      }
    });
  } catch (error) {
    console.error('Failed sending capture batch:', error);
  }
}

function scheduleCapture(trigger, delayMs) {
  if (scheduledCaptureHandle !== null) {
    return;
  }

  scheduledCaptureHandle = window.setTimeout(() => {
    scheduledCaptureHandle = null;
    runAutoCapture(trigger);
  }, delayMs);
}

function setupAutoCapture() {
  if (!isSupportedHost(window.location.hostname)) {
    return;
  }

  scheduleCapture('initial-load', 1500);

  document.addEventListener('scroll', () => {
    scheduleCapture('scroll', 1200);
  }, { passive: true });

  window.addEventListener('scroll', () => {
    scheduleCapture('window-scroll', 1200);
  }, { passive: true });

  const observer = new MutationObserver((mutations) => {
    let shouldCapture = false;

    for (const mutation of mutations) {
      if (mutation.addedNodes.length > 0) {
        shouldCapture = true;
        break;
      }
    }

    if (shouldCapture) {
      scheduleCapture('dom-mutation', 1200);
    }
  });

  if (!document.body) {
    window.setTimeout(setupAutoCapture, 250);
    return;
  }

  observer.observe(document.body, {
    childList: true,
    subtree: true
  });

  periodicCaptureHandle = window.setInterval(() => {
    if (window.location.href !== lastKnownUrl) {
      lastKnownUrl = window.location.href;
      sentPostHashes.clear();
      scheduleCapture('url-change', 800);
      return;
    }

    scheduleCapture('periodic-scan', 600);
  }, 5000);
}

setupAutoCapture();
