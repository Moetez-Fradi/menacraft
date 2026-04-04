const EXTENSION_MESSAGE = {
  EXPORT_CAPTURE_LOG: 'EXPORT_CAPTURE_LOG',
  GET_CAPTURE_STATS: 'GET_CAPTURE_STATS'
};

const statsElement = document.getElementById('stats');
const statusElement = document.getElementById('status');
const exportButton = document.getElementById('exportButton');

function formatDate(value) {
  if (!value) {
    return 'never';
  }

  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return value;
  }

  return date.toLocaleString();
}

function setStatus(message) {
  statusElement.textContent = message;
}

async function refreshStats() {
  try {
    const stats = await chrome.runtime.sendMessage({
      type: EXTENSION_MESSAGE.GET_CAPTURE_STATS
    });

    const captureCount = stats?.captureCount || 0;
    const unexportedCount = stats?.unexportedCount || 0;
    const latest = formatDate(stats?.latestCapturedAt || null);
    statsElement.textContent = `${captureCount} stored · ${unexportedCount} new · latest: ${latest}`;
  } catch (error) {
    statsElement.textContent = 'Unable to load stats.';
  }
}

async function handleExportClick() {
  exportButton.disabled = true;
  setStatus('Exporting…');

  try {
    const result = await chrome.runtime.sendMessage({
      type: EXTENSION_MESSAGE.EXPORT_CAPTURE_LOG
    });

    if (result?.exportedCount > 0) {
      const files = result?.exportedFileCount || 1;
      setStatus(`Exported ${result.exportedCount} captures to ${files} file(s).`);
    } else {
      setStatus(result?.message || 'No captures to export yet.');
    }
  } catch (error) {
    setStatus('Export failed. Check extension errors.');
  } finally {
    exportButton.disabled = false;
    refreshStats();
  }
}

exportButton.addEventListener('click', handleExportClick);
refreshStats();
