// Minimal, modular front-end for De‑ID UI
// Modules: state, api, ui, render

const $ = (s, r = document) => r.querySelector(s);
const $$ = (s, r = document) => Array.from(r.querySelectorAll(s));

const els = {
  original: $('#original'),
  deid: $('#deid'),
  lang: $('#lang'),
  policy: $('#policy'),
  run: $('#run-btn'),
  clear: $('#clear-btn'),
  upload: $('#upload-btn'),
  fileInput: $('#file-input'),
  download: $('#download-btn'),
  copy: $('#copy-btn'),
  paste: $('#paste-btn'),
  charCounter: $('#char-counter'),
  dropzone: $('#dropzone'),
  metrics: $('#metrics-text'),
  lastEvalLink: $('#last-eval-link'),
  evalModal: $('#eval-modal'),
  evalContent: $('#eval-content'),
  evalClose: $('#close-eval'),
  entitiesBody: $('#entities-body'),
  labelFilter: $('#label-filter'),
  actionFilter: $('#action-filter'),
  minLenRange: $('#minlen-range'),
  minLenValue: $('#minlen-value'),
  sortBy: $('#sort-by'),
  search: $('#search-input'),
  prevPage: $('#prev-page'),
  nextPage: $('#next-page'),
  pageInfo: $('#page-info'),
  themeBtn: $('#theme-btn'),
  themeIcon: $('#theme-icon'),
  sampleEn: $('#sample-en'),
  sampleEl: $('#sample-el'),
  tabs: $('#files-tabs'),
  tablist: $('#file-tablist'),
  panels: $('#file-panels'),
  apiKey: $('#api-key'),
};

// Toast helper
const toast = (msg, type = 'success', timeout = 3500) => {
  const t = document.createElement('div');
  t.className = `toast ${type}`;
  t.textContent = msg;
  $('#toaster').appendChild(t);
  setTimeout(() => t.remove(), timeout);
};

const state = {
  theme: localStorage.getItem('theme') || 'dark',
  policy: 'mask',
  lang: '',
  entities: [],
  originalText: '',
  page: 1,
  pageSize: 20,
  labels: new Set(),
  files: [], // [{name, result}]
  maxTextSize: 500000,
};

async function fetchJSON(url, opts = {}) {
  const headers = new Headers(opts.headers || {});
  const k = localStorage.getItem('apiKey');
  if (k) headers.set('X-API-Key', k);
  opts.headers = headers;
  const res = await fetch(url, opts);
  const ct = (res.headers.get('content-type') || '').toLowerCase();
  if (!res.ok) {
    if (ct.includes('application/json')) {
      const err = await res.json().catch(() => ({ detail: `HTTP ${res.status}` }));
      throw new Error(err.detail || `HTTP ${res.status}`);
    } else {
      const txt = await res.text().catch(() => '');
      throw new Error(txt || `HTTP ${res.status}`);
    }
  }
  if (ct.includes('application/json')) return res.json();
  return { detail: await res.text() };
}

const api = {
  async getConfig() {
    return fetchJSON('/api/v1/config');
  },
  async putConfig(data) {
    return fetchJSON('/api/v1/config', { method: 'PUT', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(data)});
  },
  async deid(text, lang_hint) {
    return fetchJSON('/api/v1/deid', { method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({ text, lang_hint })});
  },
  async deidFiles(files, lang_hint) {
    const fd = new FormData();
    for (const f of files) fd.append('files', f);
    if (lang_hint) fd.append('lang_hint', lang_hint);
    return fetchJSON('/api/v1/deid/file', { method: 'POST', body: fd });
  },
  async lastMetrics() {
    return fetchJSON('/api/v1/metrics/last');
  }
};

const ui = {
  setTheme(t) {
    state.theme = t; localStorage.setItem('theme', t);
    document.documentElement.dataset.theme = t;
    els.themeIcon.innerHTML = `<use href="/static/icons.svg#${t === 'light' ? 'moon' : 'sun'}"/>`;
  },
  toggleTheme() { ui.setTheme(state.theme === 'light' ? 'dark' : 'light'); },
  disableActions(disabled) {
    [els.run, els.clear, els.upload, els.download].forEach(b => b.disabled = disabled);
  },
  updateCharCount() { els.charCounter.textContent = (els.original.value || '').length.toLocaleString(); },
  copyOutput() { navigator.clipboard.writeText(els.deid.value || '').then(() => toast('Copied'), () => toast('Copy failed','error')); },
  downloadResult(name='deidentified.txt') {
    const blob = new Blob([els.deid.value || ''], { type: 'text/plain;charset=utf-8' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a'); a.href = url; a.download = name; a.click();
    URL.revokeObjectURL(url);
  },
  setMetrics({ time_ms, entities }) {
    const count = (entities || []).length;
    els.metrics.textContent = `${time_ms ?? '—'} ms · ${count} ent`;
  },
  showEvalModal(data) {
    if (!data) { els.evalContent.textContent = 'No evaluation yet'; els.evalModal.showModal(); return; }
    const f1 = data.f1 || {};
    const fmt = (x)=> typeof x === 'number' ? x.toFixed(3) : (x ?? '—');
    const micro = fmt(f1.micro); const macro = fmt(f1.macro);
    const labels = Object.keys(f1).filter(k => k !== 'micro' && k !== 'macro').sort();
    let html = `<div>F1 micro: <strong>${micro}</strong> · F1 macro: <strong>${macro}</strong></div>`;
    if (labels.length) {
      html += '<div style="margin-top:8px"></div>';
      html += '<table class="entities-table small mono"><thead><tr><th>Label</th><th>F1</th></tr></thead><tbody>';
      for (const lab of labels) html += `<tr><td>${lab}</td><td>${fmt(f1[lab])}</td></tr>`;
      html += '</tbody></table>';
    }
    els.evalContent.innerHTML = html;
    els.evalModal.showModal();
  },
  closeEvalModal() { els.evalModal.close(); }
};

const KNOWN_LABELS = [
  'PERSON','EMAIL','PHONE_GR','AMKA','MRN','GPE','URL','IP','ADDRESS','ADDRESS_GR','ORG','LOC','POSTAL_CODE_GR','GENERIC_ID'
];

const render = {
  refreshFilters() {
    const sel = els.labelFilter;
    const prev = Array.from(sel.selectedOptions).map(o=>o.value).filter(Boolean);
    sel.innerHTML = '';
    const labels = Array.from(new Set([...KNOWN_LABELS, ...state.labels])).sort();
    const all = document.createElement('option'); all.value=''; all.textContent='Labels: All'; sel.appendChild(all);
    labels.forEach(l => { const o=document.createElement('option'); o.value=l; o.textContent=l; if (prev.includes(l)) o.selected = true; sel.appendChild(o); });
  },
  entitiesTable() {
    const body = els.entitiesBody; body.innerHTML = '';
    let items = state.entities.slice();
    const q = (els.search.value || '').toLowerCase().trim();
    const selectedLabels = Array.from(els.labelFilter.selectedOptions).map(o=>o.value).filter(Boolean);
    const act = els.actionFilter.value || '';
    const minLen = parseInt(els.minLenRange.value || '0', 10);
    if (q) items = items.filter(e => (e.sample || '').toLowerCase().includes(q));
    if (selectedLabels.length) items = items.filter(e => selectedLabels.includes(e.label));
    if (act) items = items.filter(e => e.action === act);
    if (minLen > 0) items = items.filter(e => (e.sample || '').length >= minLen);
    const sortBy = els.sortBy.value || 'start';
    items.sort((a,b) => sortBy==='label'? a.label.localeCompare(b.label): sortBy==='length'? (b.sample.length-a.sample.length): (a.start-b.start));
    // pagination
    const total = items.length; const pages = Math.max(1, Math.ceil(total/state.pageSize));
    if (state.page>pages) state.page=pages; if (state.page<1) state.page=1;
    const startIdx = (state.page-1)*state.pageSize; const pageItems = items.slice(startIdx, startIdx+state.pageSize);
    els.pageInfo.textContent = `Page ${state.page} / ${pages}`;
    els.prevPage.disabled = state.page<=1; els.nextPage.disabled = state.page>=pages;
    if (pageItems.length===0) { const tr=document.createElement('tr'); tr.className='empty'; const td=document.createElement('td'); td.colSpan=5; td.textContent='No entities'; tr.appendChild(td); body.appendChild(tr); return; }
    pageItems.forEach(e => {
      const tr=document.createElement('tr');
      tr.innerHTML = `<td>${e.label}</td><td class="mono small">${e.sample}</td><td>${e.action||''}</td><td>${e.start}</td><td>${e.end}</td>`;
      body.appendChild(tr);
    });
  },
  fileTabs(files) {
    if (!files || files.length===0) { els.tabs.classList.add('hidden'); els.tablist.innerHTML=''; els.panels.innerHTML=''; localStorage.removeItem('activeTabFile'); return; }
    els.tabs.classList.remove('hidden'); els.tablist.innerHTML=''; els.panels.innerHTML='';
    const stored = localStorage.getItem('activeTabFile');
    let activeIdx = files.findIndex(f => f.name === stored);
    if (activeIdx < 0) activeIdx = 0;
    files.forEach((res, idx) => {
      const id = `tab-${idx}`;
      const tab = document.createElement('button');
      tab.className='tab'+(idx===activeIdx?' active':'');
      tab.setAttribute('role','tab'); tab.dataset.target=id; tab.dataset.idx = String(idx);
      tab.innerHTML = `<span class="label">${res.name}</span><button class="close" title="Close" aria-label="Close tab">×</button>`;
      tab.addEventListener('click', (ev) => { if (ev.target && ev.target.classList.contains('close')) return; setActiveTab(idx); });
      tab.querySelector('.close').addEventListener('click', (ev)=>{ ev.stopPropagation(); removeTab(idx); });
      els.tablist.appendChild(tab);
      const panel=document.createElement('div'); panel.className='panel'+(idx===activeIdx?' active':''); panel.id=id; panel.innerHTML = `<textarea readonly rows=\"12\">${res.result.result_text}</textarea>`; els.panels.appendChild(panel);
    });
    updateFromFileIndex(activeIdx);
  }
};

function withSamples(entities, _origLen, originalText) {
  const safe = (entities||[]).map(e => {
    const [s,e2] = e.span; const sample = (originalText||'').slice(s,e2);
    return { ...e, start:s, end:e2, sample };
  });
  return safe;
}

function debounce(fn, t=250){ let h; return (...a)=>{ clearTimeout(h); h=setTimeout(()=>fn(...a),t); } }

async function runDeidInline() {
  const text = els.original.value || '';
  if (!text.trim()) { toast('Please paste some text','error'); return; }
  if (text.length > state.maxTextSize) { toast('Text too large. Consider splitting (client guard).','error'); return; }
  ui.disableActions(true); els.deid.value = 'Processing…';
  const runLabel = els.run.querySelector('span');
  const prevText = runLabel ? runLabel.textContent : '';
  els.run.classList.add('loading'); if (runLabel) runLabel.textContent = 'De‑Identifying…';
  try {
    const data = await api.deid(text, els.lang.value || null);
    els.deid.value = data.result_text || '';
    state.originalText = text;
    state.entities = withSamples(data.entities, data.original_len, text);
    state.labels = new Set(state.entities.map(e => e.label));
    ui.setMetrics({ time_ms: data.time_ms, entities: data.entities });
    render.refreshFilters(); state.page=1; render.entitiesTable();
    toast('De‑identification complete','success');
  } catch (e) {
    const msg = String(e && e.message ? e.message : e);
    if (msg.includes('401') || msg.toLowerCase().includes('unauthorized')) {
      toast('Unauthorized. Add a valid API Key in the header.', 'error');
    } else if (msg.includes('413') || msg.toLowerCase().includes('payload too large')) {
      toast('The text exceeds the server limit. Please split the input.', 'error');
    } else if (msg.toLowerCase().includes('max_text_size')) {
      toast('The text exceeds MAX_TEXT_SIZE. Please split or increase the limit.', 'error');
    } else {
      toast(msg, 'error');
    }
    els.deid.value = '';
  } finally { ui.disableActions(false); els.run.classList.remove('loading'); if (runLabel) runLabel.textContent = prevText || 'De‑Identify'; }
}

async function runDeidFiles(fileList) {
  if (!fileList || fileList.length===0) return;
  ui.disableActions(true);
  try {
    const data = await api.deidFiles(fileList, els.lang.value || null);
    const results = data.map((r,i) => ({ name: fileList[i]?.name || `file-${i+1}.txt`, result: r, original: '' }));
    // We need original texts to slice samples; read files client-side
    await Promise.all(results.map(async (x,i)=>{ x.original = await fileList[i].text(); }));
    // Append and render
    state.files = [...state.files, ...results];
    render.fileTabs(state.files);
    // Set active to first of newly added
    const newIdx = state.files.length - results.length;
    setActiveTab(newIdx);
    // metrics chip for batch
    const totalDocs = results.length; const totalMs = results.reduce((a,b)=>a+(b.result.time_ms||0),0); const dps = totalDocs && totalMs ? (totalDocs/(totalMs/1000)).toFixed(1) : '—';
    els.metrics.textContent = `${totalMs} ms · ${totalDocs} docs (${dps}/s)`;
  } catch (e) {
    const msg = String(e && e.message ? e.message : e);
    if (msg.includes('401') || msg.toLowerCase().includes('unauthorized')) {
      toast('Unauthorized. Add a valid API Key in the header.', 'error');
    } else if (msg.includes('413') || msg.toLowerCase().includes('payload too large')) {
      toast('The text exceeds the server limit. Please split the input.', 'error');
    } else if (msg.toLowerCase().includes('max_text_size')) {
      toast('The text exceeds MAX_TEXT_SIZE. Please split or increase the limit.', 'error');
    } else {
      toast(msg, 'error');
    }
  } finally { ui.disableActions(false); }
}

function updateFromFileIndex(idx) {
  const f = state.files[idx]; if (!f) return;
  els.deid.value = f.result.result_text;
  state.entities = withSamples(f.result.entities, f.result.original_len, f.original);
  state.labels = new Set(state.entities.map(e=>e.label));
  render.refreshFilters(); state.page=1; render.entitiesTable();
}

function setActiveTab(idx) {
  const files = state.files; if (!files[idx]) return;
  $$('.tab', els.tablist).forEach((t,i)=> t.classList.toggle('active', i===idx));
  $$('.panel', els.panels).forEach((p,i)=> p.classList.toggle('active', i===idx));
  updateFromFileIndex(idx);
  localStorage.setItem('activeTabFile', files[idx].name);
}

function removeTab(idx) {
  if (!state.files[idx]) return;
  const removed = state.files[idx].name;
  state.files.splice(idx, 1);
  if (state.files.length === 0) {
    els.tabs.classList.add('hidden'); els.tablist.innerHTML=''; els.panels.innerHTML=''; localStorage.removeItem('activeTabFile');
    return;
  }
  // Choose next active
  const nextIdx = Math.max(0, idx - 1);
  localStorage.setItem('activeTabFile', state.files[nextIdx].name);
  render.fileTabs(state.files);
  setActiveTab(nextIdx);
}

function bindEvents() {
  // Theme
  els.themeBtn.addEventListener('click', ui.toggleTheme);
  ui.setTheme(localStorage.getItem('theme') || 'dark');

  // API Key hydrate/persist
  if (els.apiKey) {
    els.apiKey.value = localStorage.getItem('apiKey') || '';
    els.apiKey.addEventListener('input', ()=>{
      localStorage.setItem('apiKey', els.apiKey.value.trim());
    });
    // Dev-friendly default: if empty, use 'change-me' so initial calls don't 401
    if (!els.apiKey.value) {
      els.apiKey.value = 'change-me';
      localStorage.setItem('apiKey', 'change-me');
    }
  }

  // Config (only if auth likely present)
  const hasAuth = () => (!!localStorage.getItem('apiKey') || document.cookie.includes('X-API-Key='));
  if (hasAuth()) {
    api.getConfig().then(cfg => { if (cfg?.default_policy) els.policy.value = cfg.default_policy; }).catch(()=>{});
  }
  els.policy.addEventListener('change', (e)=>{ api.putConfig({ default_policy: e.target.value }).catch(()=>{}); localStorage.setItem('policy', e.target.value); });

  // Buttons
  els.run.addEventListener('click', (e)=>{ e.preventDefault(); runDeidInline(); });
  els.clear.addEventListener('click', (e)=>{ e.preventDefault(); els.original.value=''; els.deid.value=''; state.entities=[]; render.entitiesTable(); ui.updateCharCount(); });
  els.copy.addEventListener('click', ui.copyOutput);
  function activeDownloadName() {
    const stored = localStorage.getItem('activeTabFile');
    if (stored && stored.trim()) return `${stored}.deid.txt`;
    return 'deid.txt';
  }
  els.download.addEventListener('click', ()=> ui.downloadResult(activeDownloadName()));
  els.paste.addEventListener('click', async ()=>{ const txt = await navigator.clipboard.readText().catch(()=>null); if (txt) { els.original.value = txt; ui.updateCharCount(); } });
  els.original.addEventListener('input', ui.updateCharCount);

  // Samples
  const sampleEN = "Patient John Papadopoulos was admitted on 2024-03-12 in Athens.\nContact: +30 694 123 4567, john_doe+test@example.co.uk\nRecord: MRN=ABCD_778899\nRefer to: https://hospital.example.org/cases/7788\nClient IP noted: 192.168.10.25\n";
  const sampleEL = "Ο ασθενής Γιάννης Παπαδόπουλος, ΑΜΚΑ 12039912345, τηλ 210 123 4567, email giannis@example.com, διεύθυνση Οδός Σοφοκλέους 10, ΤΚ 10559, Αθήνα.";
  els.sampleEn.addEventListener('click', ()=>{ els.original.value = sampleEN; ui.updateCharCount(); });
  els.sampleEl.addEventListener('click', ()=>{ els.original.value = sampleEL; ui.updateCharCount(); });

  // Drag & drop
  ['dragenter','dragover'].forEach(ev=> els.dropzone.addEventListener(ev, e=>{ e.preventDefault(); e.stopPropagation(); els.dropzone.classList.add('dragover'); }));
  ['dragleave','drop'].forEach(ev=> els.dropzone.addEventListener(ev, e=>{ e.preventDefault(); e.stopPropagation(); els.dropzone.classList.remove('dragover'); }));
  els.dropzone.addEventListener('drop', e=>{ const files = Array.from(e.dataTransfer.files || []).filter(f=>/\.txt$/i.test(f.name)); if (files.length) runDeidFiles(files); else toast('Only .txt files supported','error'); });
  els.upload.addEventListener('click', ()=> els.fileInput.click());
  els.fileInput.addEventListener('change', ()=>{ const files= Array.from(els.fileInput.files||[]); if (files.length) runDeidFiles(files); });

  // Entities filters
  [els.search, els.labelFilter, els.actionFilter, els.minLenRange, els.sortBy].forEach(el => el.addEventListener('input', debounce(()=>{ state.page=1; render.entitiesTable(); }, 250)));
  els.minLenRange.addEventListener('input', ()=> { els.minLenValue.textContent = els.minLenRange.value; });
  $('#clear-filters').addEventListener('click', ()=>{
    els.search.value = '';
    Array.from(els.labelFilter.options).forEach(o=> o.selected = false);
    els.actionFilter.value = '';
    els.minLenRange.value = '0'; els.minLenValue.textContent = '0';
    els.sortBy.value = 'start';
    state.page = 1; render.entitiesTable();
  });
  els.prevPage.addEventListener('click', ()=>{ state.page = Math.max(1, state.page-1); render.entitiesTable(); });
  els.nextPage.addEventListener('click', ()=>{ state.page = state.page+1; render.entitiesTable(); });

  // Last eval modal
  els.lastEvalLink.addEventListener('click', async (e)=>{ e.preventDefault(); const m = await api.lastMetrics().catch(()=>null); ui.showEvalModal(m); });
  els.evalClose.addEventListener('click', ui.closeEvalModal);
  els.evalModal.addEventListener('click', (e)=>{ if (e.target === els.evalModal) ui.closeEvalModal(); });
  document.addEventListener('keydown', (e)=>{ if (e.key === 'Escape' && els.evalModal.open) ui.closeEvalModal(); });

  // Shortcuts
  document.addEventListener('keydown', (e)=>{
    if ((e.ctrlKey||e.metaKey) && e.key.toLowerCase()==='enter') { e.preventDefault(); runDeidInline(); }
    if ((e.ctrlKey||e.metaKey) && e.key.toLowerCase()==='k') { e.preventDefault(); els.search.focus(); }
  });
}

document.addEventListener('DOMContentLoaded', async ()=>{
  bindEvents(); ui.updateCharCount();
  // Fetch last metrics only if we likely have auth (cookie or stored key)
  try {
    const hasAuth = () => (!!localStorage.getItem('apiKey') || document.cookie.includes('X-API-Key='));
    if (hasAuth()) {
      const last = await api.lastMetrics();
      if (last) els.lastEvalLink.classList.remove('hidden');
    }
  } catch (e) { /* ignore */ }
});
