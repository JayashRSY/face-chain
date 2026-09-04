/* app.js — FaceChain UI logic */

// ── Element refs ──────────────────────────────────────────────
const dropZone      = document.getElementById('dropZone');
const fileInput     = document.getElementById('fileInput');
const browseBtn     = document.getElementById('browseBtn');
const previewRow    = document.getElementById('previewRow');
const previewImg    = document.getElementById('previewImg');
const previewName   = document.getElementById('previewName');
const previewSize   = document.getElementById('previewSize');
const runBtn        = document.getElementById('runBtn');
const clearBtn      = document.getElementById('clearBtn');
const uploadCard    = document.getElementById('uploadCard');
const pipelineCard  = document.getElementById('pipelineCard');
const resultsCard   = document.getElementById('resultsCard');
const verifyCard    = document.getElementById('verifyCard');
const verifyInput   = document.getElementById('verifyInput');
const verifyBtn     = document.getElementById('verifyBtn');
const verifyResult  = document.getElementById('verifyResult');
const runAgainBtn   = document.getElementById('runAgainBtn');
const verifyAgainBtn = document.getElementById('verifyAgainBtn');

let selectedFile = null;
let currentEventSource = null;
let lastHash = '';

// ── File selection ────────────────────────────────────────────
browseBtn.addEventListener('click', () => fileInput.click());
fileInput.addEventListener('change', () => {
  if (fileInput.files[0]) setFile(fileInput.files[0]);
});

dropZone.addEventListener('dragover', e => {
  e.preventDefault();
  dropZone.classList.add('drag-over');
});
dropZone.addEventListener('dragleave', () => dropZone.classList.remove('drag-over'));
dropZone.addEventListener('drop', e => {
  e.preventDefault();
  dropZone.classList.remove('drag-over');
  if (e.dataTransfer.files[0]) setFile(e.dataTransfer.files[0]);
});

function setFile(file) {
  if (!file.type.match(/image\/(jpeg|png|webp)/)) {
    alert('Please upload a JPG, PNG or WebP image.');
    return;
  }
  selectedFile = file;
  const reader = new FileReader();
  reader.onload = e => { previewImg.src = e.target.result; };
  reader.readAsDataURL(file);
  previewName.textContent = file.name;
  previewSize.textContent = formatBytes(file.size);
  dropZone.style.display = 'none';
  previewRow.style.display = 'flex';
}

clearBtn.addEventListener('click', resetUpload);

function resetUpload() {
  selectedFile = null;
  fileInput.value = '';
  previewImg.src = '';
  dropZone.style.display = '';
  previewRow.style.display = 'none';
  if (currentEventSource) { currentEventSource.close(); currentEventSource = null; }
}

// ── Run pipeline ──────────────────────────────────────────────
runBtn.addEventListener('click', startPipeline);

async function startPipeline() {
  if (!selectedFile) return;

  pipelineCard.style.display = '';
  resultsCard.style.display = 'none';
  resetSteps();
  runBtn.disabled = true;
  pipelineCard.scrollIntoView({ behavior: 'smooth', block: 'start' });

  const form = new FormData();
  form.append('image', selectedFile);

  let job_id;
  try {
    const res = await fetch('/upload', { method: 'POST', body: form });
    const json = await res.json();
    if (json.error) { showUploadError(json.error); return; }
    job_id = json.job_id;
  } catch (err) {
    showUploadError(err.message);
    return;
  }

  // Stream SSE events
  if (currentEventSource) currentEventSource.close();
  currentEventSource = new EventSource(`/stream/${job_id}`);
  currentEventSource.onmessage = handleEvent;
  currentEventSource.onerror = () => {
    currentEventSource.close();
    runBtn.disabled = false;
  };
}

// ── Event handler ─────────────────────────────────────────────
function handleEvent(e) {
  const ev = JSON.parse(e.data);

  if (ev.__done__) {
    currentEventSource.close();
    runBtn.disabled = false;
    return;
  }

  const { step, status, message, data } = ev;

  if (status === 'error' && step === 0) {
    // Global pipeline error
    showGlobalError(message);
    runBtn.disabled = false;
    return;
  }

  const stepEl = document.getElementById(`step${step}`);
  const resultEl = document.getElementById(`step${step}result`);
  if (!stepEl) return;

  // Remove all state classes, set new one
  stepEl.classList.remove('active', 'done', 'error');
  stepEl.classList.add(status === 'running' ? 'active' : status);
  resultEl.textContent = message;

  // Enrich result panels per step
  if (status === 'done') {
    enrichStep(step, data);

    // After step 5 done, show results card
    if (step === 5) {
      setTimeout(() => showResults(data), 600);
    }
  }
}

function enrichStep(step, data) {
  const el = document.getElementById(`step${step}result`);
  if (step === 1 && data.encoding_shape) {
    el.textContent = `Face encoding: ${data.encoding_shape.join('×')} vector  ✓`;
  }
  if (step === 2 && data.total_matches !== undefined) {
    el.textContent = `${data.total_matches} visual matches found, ${data.social_matches} on social media  ✓`;
  }
  if (step === 3 && data.post) {
    el.textContent = `Title: ${data.post.title?.slice(0, 60) || '(no title)'}  ✓`;
  }
  if (step === 4 && data.hash) {
    el.textContent = data.hash;
    lastHash = data.hash;
  }
  if (step === 5 && data.tx_hash) {
    el.textContent = `Tx: ${data.tx_hash.slice(0, 20)}...  ✓`;
  }
}

// ── Results card ──────────────────────────────────────────────
function showResults(data) {
  // Found post
  const post = getPipelinePost();
  if (post) {
    document.getElementById('foundSite').textContent = post.site_name || post.source || extractDomain(post.url);
    document.getElementById('foundTitle').textContent = post.title || '(no title)';
    document.getElementById('foundDesc').textContent = post.description || '';
    const linkEl = document.getElementById('foundLink');
    linkEl.href = post.url;
    linkEl.textContent = 'Open post →';
    const thumb = document.getElementById('foundThumb');
    if (post.og_image) { thumb.src = post.og_image; thumb.style.display = ''; }
    else { thumb.style.display = 'none'; }
  }

  // Hash
  document.getElementById('hashBox').textContent = data.data_hash || lastHash;

  // Chain record
  document.getElementById('verifiedBadge').className = 'chain-value verified-badge ok';
  const txLink = document.getElementById('txLink');
  txLink.href = data.etherscan || '#';
  txLink.textContent = data.tx_hash ? `${data.tx_hash.slice(0, 30)}...` : '';
  document.getElementById('chainTs').textContent = data.timestamp_human || '';
  document.getElementById('chainUploader').textContent = data.uploader || '';

  resultsCard.style.display = '';
  resultsCard.scrollIntoView({ behavior: 'smooth', block: 'start' });
}

// Retrieve the post data cached from step 3 event
let _cachedPost = null;
const origHandle = window.EventSource;
function getPipelinePost() { return _cachedPost; }

// Patch handleEvent to cache post
const _origHandleEvent = handleEvent;
window._handleEventWrapper = function(e) {
  const ev = JSON.parse(e.data);
  if (ev.step === 3 && ev.status === 'done' && ev.data?.post) {
    _cachedPost = ev.data.post;
  }
  _origHandleEvent(e);
};
// Replace the listener assignment
document.addEventListener('DOMContentLoaded', () => {});

// Re-wire to use wrapper — patch startPipeline SSE listener
(function() {
  const orig = EventSource.prototype.addEventListener;
  // We just override onmessage assignment inside startPipeline below
})();

// Override startPipeline SSE to use wrapper
function patchSSE(es) {
  es.onmessage = function(e) {
    const ev = JSON.parse(e.data);
    if (ev.step === 3 && ev.status === 'done' && ev.data?.post) {
      _cachedPost = ev.data.post;
    }
    handleEvent(e);
  };
  es.onerror = () => {
    es.close();
    runBtn.disabled = false;
  };
}

// Monkey-patch startPipeline to call patchSSE
const _origStart = startPipeline;
window.startPipeline = async function() {
  if (!selectedFile) return;
  pipelineCard.style.display = '';
  resultsCard.style.display = 'none';
  resetSteps();
  runBtn.disabled = true;
  _cachedPost = null;
  pipelineCard.scrollIntoView({ behavior: 'smooth', block: 'start' });

  const form = new FormData();
  form.append('image', selectedFile);

  let job_id;
  try {
    const res = await fetch('/upload', { method: 'POST', body: form });
    const json = await res.json();
    if (json.error) { showUploadError(json.error); runBtn.disabled = false; return; }
    job_id = json.job_id;
  } catch (err) {
    showUploadError(err.message);
    runBtn.disabled = false;
    return;
  }

  if (currentEventSource) currentEventSource.close();
  currentEventSource = new EventSource(`/stream/${job_id}`);
  patchSSE(currentEventSource);
};
runBtn.removeEventListener('click', startPipeline);
runBtn.addEventListener('click', window.startPipeline);

// ── Step state helpers ────────────────────────────────────────
function resetSteps() {
  for (let i = 1; i <= 5; i++) {
    const s = document.getElementById(`step${i}`);
    const r = document.getElementById(`step${i}result`);
    if (s) s.classList.remove('active', 'done', 'error');
    if (r) r.textContent = '';
  }
}

function showUploadError(msg) {
  pipelineCard.style.display = 'none';
  runBtn.disabled = false;
  alert(`Upload error: ${msg}`);
}

function showGlobalError(msg) {
  // Mark all pending steps as error
  for (let i = 1; i <= 5; i++) {
    const s = document.getElementById(`step${i}`);
    if (s && !s.classList.contains('done')) {
      s.classList.add('error');
      document.getElementById(`step${i}result`).textContent = 'Pipeline error — see message below';
    }
  }
  const r = document.getElementById('step1result');
  if (r) r.textContent = `Error: ${msg}`;
}

// ── Run again / Verify buttons ────────────────────────────────
runAgainBtn.addEventListener('click', () => {
  resultsCard.style.display = 'none';
  pipelineCard.style.display = 'none';
  resetUpload();
  uploadCard.scrollIntoView({ behavior: 'smooth' });
});

verifyAgainBtn.addEventListener('click', () => {
  verifyInput.value = lastHash;
  verifyCard.scrollIntoView({ behavior: 'smooth' });
  verifyInput.focus();
});

// ── Standalone verify ─────────────────────────────────────────
verifyBtn.addEventListener('click', doVerify);
verifyInput.addEventListener('keydown', e => { if (e.key === 'Enter') doVerify(); });

async function doVerify() {
  const hash = verifyInput.value.trim();
  if (hash.length !== 64) {
    showVerifyResult(false, 'Please enter a valid 64-character SHA-256 hash.');
    return;
  }
  verifyBtn.disabled = true;
  verifyBtn.textContent = 'Checking...';
  verifyResult.style.display = 'none';

  try {
    const res = await fetch('/verify', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ hash }),
    });
    const json = await res.json();
    if (json.error) {
      showVerifyResult(false, `Error: ${json.error}`);
    } else if (json.exists) {
      const ts = json.timestamp
        ? new Date(json.timestamp * 1000).toUTCString()
        : 'unknown';
      showVerifyResult(true,
        `Hash verified on-chain.\n` +
        `Registered: ${ts}\n` +
        `Uploader: ${json.uploader}\n` +
        `Metadata: ${json.metadata}`
      );
    } else {
      showVerifyResult(false, 'Hash not found on-chain. It has not been registered.');
    }
  } catch (err) {
    showVerifyResult(false, `Network error: ${err.message}`);
  } finally {
    verifyBtn.disabled = false;
    verifyBtn.textContent = 'Verify';
  }
}

function showVerifyResult(ok, text) {
  verifyResult.style.display = '';
  verifyResult.className = `verify-result ${ok ? 'ok' : 'fail'}`;
  verifyResult.textContent = text;
}

// ── Utilities ─────────────────────────────────────────────────
function formatBytes(bytes) {
  if (bytes < 1024) return bytes + ' B';
  if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB';
  return (bytes / (1024 * 1024)).toFixed(1) + ' MB';
}

function extractDomain(url) {
  try { return new URL(url).hostname.replace('www.', ''); }
  catch { return url; }
}
