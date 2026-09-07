/* app.js — FaceChain UI logic */

// ── Element refs ──────────────────────────────────────────────
const dropZone          = document.getElementById('dropZone');
const fileInput         = document.getElementById('fileInput');
const browseBtn         = document.getElementById('browseBtn');
const previewRow        = document.getElementById('previewRow');
const previewImg        = document.getElementById('previewImg');
const previewName       = document.getElementById('previewName');
const previewSize       = document.getElementById('previewSize');
const runBtn            = document.getElementById('runBtn');
const clearBtn          = document.getElementById('clearBtn');
const uploadCard        = document.getElementById('uploadCard');
const pipelineCard      = document.getElementById('pipelineCard');
const logCard           = document.getElementById('logCard');
const logBody           = document.getElementById('logBody');
const searchResultsCard = document.getElementById('searchResultsCard');
const srList            = document.getElementById('srList');
const sidebarIdle       = document.getElementById('sidebarIdle');
const resultsCard       = document.getElementById('resultsCard');
const verifyCard        = document.getElementById('verifyCard');
const verifyInput       = document.getElementById('verifyInput');
const verifyBtn         = document.getElementById('verifyBtn');
const verifyResult      = document.getElementById('verifyResult');
const runAgainBtn       = document.getElementById('runAgainBtn');
const verifyAgainBtn    = document.getElementById('verifyAgainBtn');

let selectedFile       = null;
let currentEventSource = null;
let lastHash           = '';
let _cachedPost        = null;
let logVisible         = true;

// ── File selection ────────────────────────────────────────────
browseBtn.addEventListener('click', () => fileInput.click());
fileInput.addEventListener('change', () => { if (fileInput.files[0]) setFile(fileInput.files[0]); });
dropZone.addEventListener('dragover', e => { e.preventDefault(); dropZone.classList.add('drag-over'); });
dropZone.addEventListener('dragleave', () => dropZone.classList.remove('drag-over'));
dropZone.addEventListener('drop', e => {
  e.preventDefault(); dropZone.classList.remove('drag-over');
  if (e.dataTransfer.files[0]) setFile(e.dataTransfer.files[0]);
});

function setFile(file) {
  if (!file.type.match(/image\/(jpeg|png|webp)/)) { alert('Please upload a JPG, PNG or WebP image.'); return; }
  selectedFile = file;
  const reader = new FileReader();
  reader.onload = e => { previewImg.src = e.target.result; };
  reader.readAsDataURL(file);
  previewName.textContent  = file.name;
  previewSize.textContent  = formatBytes(file.size);
  dropZone.style.display   = 'none';
  previewRow.style.display = 'flex';
}

// ── Full reset ────────────────────────────────────────────────
clearBtn.addEventListener('click', fullReset);

function fullReset() {
  if (currentEventSource) { currentEventSource.close(); currentEventSource = null; }

  selectedFile = null; lastHash = ''; _cachedPost = null;
  fileInput.value = ''; previewImg.src = ''; runBtn.disabled = false;
  dropZone.style.display = ''; previewRow.style.display = 'none';

  pipelineCard.style.display    = 'none'; resetSteps();
  logCard.style.display         = 'none'; clearLog();
  searchResultsCard.style.display = 'none'; srList.innerHTML = '';
  sidebarIdle.style.display     = '';
  resultsCard.style.display     = 'none';

  ['foundSite','foundTitle','foundDesc','chainTs','chainUploader','hashBox'].forEach(id => {
    document.getElementById(id).textContent = '';
  });
  document.getElementById('foundLink').textContent = '';
  document.getElementById('foundLink').href = '#';
  document.getElementById('foundThumb').src = '';
  document.getElementById('foundThumb').style.display = 'none';
  document.getElementById('txLink').textContent = '';
  document.getElementById('txLink').href = '#';
  document.getElementById('verifiedBadge').textContent = '';
  document.getElementById('verifiedBadge').className = 'chain-value verified-badge';

  verifyInput.value = '';
  verifyResult.style.display = 'none';
  verifyResult.textContent = '';
  verifyResult.className = 'verify-result';
}

// ── Run pipeline ──────────────────────────────────────────────
runBtn.addEventListener('click', runPipeline);

async function runPipeline() {
  if (!selectedFile) return;

  pipelineCard.style.display = '';
  resultsCard.style.display  = 'none';
  logCard.style.display      = '';
  searchResultsCard.style.display = 'none';
  srList.innerHTML = '';
  sidebarIdle.style.display  = 'none';
  clearLog(); resetSteps();
  runBtn.disabled = true; _cachedPost = null;
  pipelineCard.scrollIntoView({ behavior: 'smooth', block: 'start' });

  const form = new FormData();
  form.append('image', selectedFile);

  let job_id;
  try {
    const res  = await fetch('/upload', { method: 'POST', body: form });
    const json = await res.json();
    if (json.error) { alert(`Upload error: ${json.error}`); runBtn.disabled = false; return; }
    job_id = json.job_id;
  } catch (err) {
    alert(`Upload error: ${err.message}`); runBtn.disabled = false; return;
  }

  if (currentEventSource) currentEventSource.close();
  currentEventSource = new EventSource(`/stream/${job_id}`);
  currentEventSource.onmessage = handleEvent;
  currentEventSource.onerror   = () => { currentEventSource.close(); runBtn.disabled = false; };
}

// ── SSE event handler ─────────────────────────────────────────
function handleEvent(e) {
  const ev = JSON.parse(e.data);

  if (ev.type === 'log')  { appendLog(ev.text); return; }
  if (ev.__done__)        { currentEventSource.close(); runBtn.disabled = false; return; }
  if (ev.step === 3 && ev.status === 'done' && ev.data?.post) _cachedPost = ev.data.post;

  const { step, status, message, data } = ev;
  if (status === 'error' && step === 0) { showGlobalError(message); runBtn.disabled = false; return; }

  const stepEl   = document.getElementById(`step${step}`);
  const resultEl = document.getElementById(`step${step}result`);
  if (!stepEl) return;

  stepEl.classList.remove('active', 'done', 'error');
  stepEl.classList.add(status === 'running' ? 'active' : status);
  resultEl.textContent = message;

  if (status === 'done') {
    enrichStep(step, data);
    if (step === 2) renderSearchResults(data);
    if (step === 5) setTimeout(() => showResults(data), 600);
  }
}

function enrichStep(step, data) {
  const el = document.getElementById(`step${step}result`);
  if (step === 1 && data.encoding_shape)
    el.textContent = `Face encoding: ${data.encoding_shape.join('×')} vector  ✓`;
  if (step === 2 && data.total_matches !== undefined)
    el.textContent = `${data.total_matches} matches found, ${data.social_matches} social — top: ${extractDomain(data.chosen?.link || '')}  ✓`;
  if (step === 3 && data.post)
    el.textContent = `Title: ${(data.post.title || data.post.url || 'found').slice(0, 55)}  ✓`;
  if (step === 4 && data.hash) { el.textContent = data.hash; lastHash = data.hash; }
  if (step === 5) {
    if (data.already_registered)
      el.textContent = `Already on-chain — original record from ${data.timestamp_human}  ✓`;
    else if (data.tx_hash)
      el.textContent = `Tx: ${data.tx_hash.slice(0, 20)}...  ✓`;
  }
}

// ── Search results sidebar ────────────────────────────────────
function renderSearchResults(data) {
  const results  = data.all_results || [];
  const chosen   = data.chosen || {};
  const quality  = data.quality || {};
  if (!results.length) return;

  srList.innerHTML = '';
  searchResultsCard.style.display = '';

  // Quality banner
  if (quality.quality) {
    const bannerEl = document.createElement('div');
    const bannerClass = quality.quality === 'good' ? 'quality-good'
                      : quality.quality === 'weak' ? 'quality-weak'
                      : 'quality-poor';
    bannerEl.className = `quality-banner ${bannerClass}`;
    const icon = quality.quality === 'good' ? '✓' : quality.quality === 'weak' ? '⚠' : '✕';
    bannerEl.textContent = `${icon}  ${quality.message}`;
    srList.appendChild(bannerEl);
  }

  results.forEach((r, i) => {
    const score    = r._score ?? 0;
    const isChosen = r.link === chosen.link;
    const domain   = extractDomain(r.link);

    const scoreClass = score >= 6 ? 'high' : score >= 3 ? 'mid' : 'low';

    const item = document.createElement('a');
    item.className = `sr-item${isChosen ? ' sr-chosen' : ''}`;
    item.href      = r.link;
    item.target    = '_blank';
    item.rel       = 'noopener noreferrer';

    item.innerHTML = `
      ${r.thumbnail ? `<img class="sr-thumb" src="${escapeHtml(r.thumbnail)}" alt="" onerror="this.style.display='none'"/>` : ''}
      <div class="sr-body">
        <div class="sr-top">
          <span class="sr-domain">${escapeHtml(domain)}</span>
          <span class="sr-score ${scoreClass}">${score.toFixed(1)}/10</span>
        </div>
        <div class="sr-title">${escapeHtml(r.title || r.link)}</div>
        ${isChosen ? '<span class="sr-chosen-badge">✓ Selected as best match</span>' : ''}
      </div>
    `;
    srList.appendChild(item);
  });
}

// ── Results card ──────────────────────────────────────────────
function showResults(data) {
  const post = _cachedPost;
  if (post) {
    document.getElementById('foundSite').textContent  = post.site_name || post.source || extractDomain(post.url);
    document.getElementById('foundTitle').textContent = post.title || post.search_title || extractDomain(post.url);
    document.getElementById('foundDesc').textContent  = post.description || 'Discovered via reverse image search.';
    const linkEl = document.getElementById('foundLink');
    linkEl.href = post.url; linkEl.target = '_blank'; linkEl.rel = 'noopener noreferrer';
    const loginWalls = ['instagram.com','twitter.com','x.com','tiktok.com','facebook.com'];
    linkEl.textContent = loginWalls.some(d => post.url.includes(d))
      ? `View on ${extractDomain(post.url)} (login may be required) →` : 'Open post →';
    const thumb = document.getElementById('foundThumb');
    if (post.og_image) { thumb.src = post.og_image; thumb.style.display = ''; thumb.onerror = () => { thumb.style.display = 'none'; }; }
    else { thumb.style.display = 'none'; }
  }

  document.getElementById('hashBox').textContent = data.data_hash || lastHash;
  const badge = document.getElementById('verifiedBadge');
  badge.className   = 'chain-value verified-badge ok';
  badge.textContent = data.already_registered ? '✓  Already registered on-chain' : '✓  Verified on-chain';
  const txLink = document.getElementById('txLink');
  txLink.href        = data.etherscan || '#';
  txLink.textContent = data.tx_hash ? `${data.tx_hash.slice(0, 30)}...` : 'Search on Etherscan →';
  document.getElementById('chainTs').textContent       = data.timestamp_human || '';
  document.getElementById('chainUploader').textContent = data.uploader || '';

  resultsCard.style.display = '';
  resultsCard.scrollIntoView({ behavior: 'smooth', block: 'start' });
}

// ── Step helpers ──────────────────────────────────────────────
function resetSteps() {
  for (let i = 1; i <= 5; i++) {
    const s = document.getElementById(`step${i}`);
    const r = document.getElementById(`step${i}result`);
    if (s) s.classList.remove('active', 'done', 'error');
    if (r) r.textContent = '';
  }
}

function showGlobalError(msg) {
  for (let i = 1; i <= 5; i++) {
    const s = document.getElementById(`step${i}`);
    if (s && !s.classList.contains('done')) s.classList.add('error');
  }
  const r = document.getElementById('step1result');
  if (r) r.textContent = `Error: ${msg}`;
}

// ── Buttons ───────────────────────────────────────────────────
runAgainBtn.addEventListener('click', () => { fullReset(); uploadCard.scrollIntoView({ behavior: 'smooth' }); });
verifyAgainBtn.addEventListener('click', () => {
  verifyInput.value = lastHash;
  verifyCard.scrollIntoView({ behavior: 'smooth' }); verifyInput.focus();
});

// ── Standalone verify ─────────────────────────────────────────
verifyBtn.addEventListener('click', doVerify);
verifyInput.addEventListener('keydown', e => { if (e.key === 'Enter') doVerify(); });

async function doVerify() {
  const hash = verifyInput.value.trim();
  if (hash.length !== 64) { showVerifyResult(false, 'Please enter a valid 64-character SHA-256 hash.'); return; }
  verifyBtn.disabled = true; verifyBtn.textContent = 'Checking...';
  verifyResult.style.display = 'none';
  try {
    const res  = await fetch('/verify', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ hash }) });
    const json = await res.json();
    if (json.error) { showVerifyResult(false, `Error: ${json.error}`); }
    else if (json.exists) {
      const ts = json.timestamp ? new Date(json.timestamp * 1000).toUTCString() : 'unknown';
      showVerifyResult(true, `Hash verified on-chain.\nRegistered: ${ts}\nUploader: ${json.uploader}\nMetadata: ${json.metadata}`);
    } else { showVerifyResult(false, 'Hash not found on-chain. It has not been registered.'); }
  } catch (err) { showVerifyResult(false, `Network error: ${err.message}`); }
  finally { verifyBtn.disabled = false; verifyBtn.textContent = 'Verify'; }
}

function showVerifyResult(ok, text) {
  verifyResult.style.display = '';
  verifyResult.className     = `verify-result ${ok ? 'ok' : 'fail'}`;
  verifyResult.textContent   = text;
}

// ── Log panel ─────────────────────────────────────────────────
function toggleLog() {
  logVisible = !logVisible;
  logBody.style.display = logVisible ? '' : 'none';
  document.getElementById('logToggleBtn').textContent = logVisible ? 'Hide' : 'Show';
}

function appendLog(text) {
  const now = new Date();
  const ts  = `${String(now.getHours()).padStart(2,'0')}:${String(now.getMinutes()).padStart(2,'0')}:${String(now.getSeconds()).padStart(2,'0')}`;
  let cls   = '';
  const lo  = text.toLowerCase();
  if (lo.includes('error') || lo.includes('failed') || lo.includes('exception')) cls = 'error';
  else if (lo.includes('warn')) cls = 'warn';
  else if (lo.includes('confirmed') || lo.includes('verified') || lo.includes('done') || lo.includes('loaded') || lo.includes('models')) cls = 'info';
  const line = document.createElement('div');
  line.className = 'log-line';
  line.innerHTML = `<span class="log-ts">${ts}</span><span class="log-text ${cls}">${escapeHtml(text)}</span>`;
  logBody.appendChild(line);
  logBody.scrollTop = logBody.scrollHeight;
}

function clearLog() { logBody.innerHTML = ''; }

// ── Utilities ─────────────────────────────────────────────────
function escapeHtml(t) {
  return String(t).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
}

function formatBytes(bytes) {
  if (bytes < 1024) return bytes + ' B';
  if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB';
  return (bytes / (1024 * 1024)).toFixed(1) + ' MB';
}

function extractDomain(url) {
  try { return new URL(url).hostname.replace('www.', ''); }
  catch { return url || ''; }
}
