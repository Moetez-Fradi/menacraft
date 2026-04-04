# MenaCraft Web Extension

This folder contains a Chrome Manifest V3 extension that automatically captures user-visible content while browsing supported sites and stores captures silently in extension storage.

## What it does

- Runs only on pages the user opens (no random/off-site crawling).
- Automatically reads DOM content on supported domains after page load, scrolling, and feed updates.
- Extracts post-like blocks (`article`, `[role=article]`, `.post`, etc.).
- Captures text, links, image/video URLs, metadata, and HTML snippet.
- Stores captures in extension-local storage without prompting downloads.
- Left-clicking the extension icon opens a popup with capture count and an export button.
- Export creates multiple JSON files grouped by source hostname (for example, separate files for Facebook and CNN).
- Export format is `posts[]` with practical fields (`type`, `text`, `account`, `postUrl`, `media`) and filtered media URLs.
- Badge count reflects new/unexported captures and resets after export.

## Supported domains

- `facebook.com`
- `instagram.com`
- `medium.com`
- `reddit.com`
- `cnn.com`

## Build

```bash
cd web
npm run build
```

This creates `web/dist`.
Note: The popup shows capture counts and export actions; see `src/popup.js` for behavior.

## Load into Chrome

1. Open `chrome://extensions`.
2. Enable **Developer mode**.
3. Click **Load unpacked**.
4. Select the `web/dist` folder.
5. Open a supported site and browse normally; captures are collected automatically in the background.
6. Left-click the extension icon to open the popup.
7. Click **Export all captures** to download grouped JSON export files (one per source hostname).