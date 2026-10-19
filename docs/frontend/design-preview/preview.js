/* Visual study: local fixture navigation only. No product requests or auth logic. */
(() => {
  const { runs, authority, fixtureDate } = window.PREVIEW_FIXTURES;
  const params = new URLSearchParams(location.search);
  const screen = params.get('screen') || 'runs';
  const defaults = { trace: 1040, evidence: 1042, runs: 1042 };
  const scaleSize = screen === 'trace' && [100,1000,2100].includes(Number(params.get('size'))) ? Number(params.get('size')) : null;
  const baseRun = scaleSize ? window.TRACE_SCALE_FIXTURES.create(scaleSize) : runs.find(r => r.number === Number(params.get('run'))) || runs.find(r => r.number === defaults[screen]) || runs[0];
  const run = params.get('variant') === 'raw-statuses' ? {...baseRun,spans:baseRun.spans.map((s,i)=>({...s,status:i===1?'VENDOR_PENDING':i===2?'UNSET':i===3?null:s.status}))} : baseRun;
  const store = { get(key, fallback) { try { return localStorage.getItem('debugger-design.' + key) || fallback; } catch { return fallback; } },
    set(key, value) { try { localStorage.setItem('debugger-design.' + key, value); } catch { /* preference is optional */ } } };
  const session = {get(key){try{return JSON.parse(sessionStorage.getItem('debugger-design.'+key)||'null');}catch{return null;}},set(key,value){try{sessionStorage.setItem('debugger-design.'+key,JSON.stringify(value));}catch{/* optional presentation memory */}}};
  const traceMemoryKey='trace.'+run.traceId, evidenceMemoryKey='evidence.'+run.traceId;
  const restoredTrace=screen==='trace'&&params.get('restore')==='1'?session.get(traceMemoryKey):null;
  const restoredEvidence=screen==='evidence'&&params.get('restore')==='1'?session.get(evidenceMemoryKey):null;
  const state = { theme: params.get('theme') === 'dark' ? 'dark' : params.get('theme') === 'light' ? 'light' : store.get('theme', 'light'),
    collapsed: store.get('sidebar', 'expanded') === 'collapsed', selected: params.get('span') || run.selected,
    tab: 'Content', view: params.get('view') === 'timeline' ? 'Timeline' : 'Tree', search: '', outcome: 'All outcomes', completeness: 'All completeness',
    expanded: new Set(run.spans.map(s => s.key)), treeSearch: '', revealQuery:null, sourceA: 'retrieval', sourceB: 'document',
    payloadMode: 'Readable', layout:'Auto', wrap:true, focusSource:null, accent:params.get('accent') === 'blue' ? 'blue' : 'steel',
    evidenceUnavailable: params.get('variant') === 'unavailable', redacted: params.get('variant') === 'redacted', finding:params.get('finding')||'F-01', sourceContexts:new Set(restoredEvidence?.sourceContexts||[]), attributeQuery:'', notice: '' };
  if(restoredTrace){for(const key of ['tab','payloadMode','layout','wrap'])if(key in restoredTrace)state[key]=restoredTrace[key];if(!params.has('span'))state.selected=restoredTrace.selected;if(!params.has('view'))state.view=restoredTrace.view;state.expanded=new Set(restoredTrace.expanded.filter(key=>run.spans.some(s=>s.key===key)));}
  if(restoredEvidence)for(const key of ['sourceA','sourceB','focusSource','finding'])if(key in restoredEvidence)state[key]=restoredEvidence[key];
  const scrollMemory = new Map(restoredEvidence?.scroll||[]);
  const app = document.getElementById('app');
  let traceStudy = null;
  const escape = value => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const icons = {
    panel: '<rect x="3" y="3" width="18" height="18" rx="2"/><path d="M9 3v18M15 9l-3 3 3 3"/>',
    runs: '<path d="M5 6h14M5 12h14M5 18h14"/><circle cx="3" cy="6" r=".5"/>',
    setup: '<path d="m8 7-5 5 5 5m8-10 5 5-5 5m-3-13-2 19"/>',
    book: '<path d="M4 4h7a3 3 0 0 1 3 3v14a4 4 0 0 0-3-2H4zm16 0h-3a3 3 0 0 0-3 3"/><path d="M20 4v15h-3"/>',
    settings: '<circle cx="12" cy="12" r="3"/><path d="m9 3-1 3-3 2-2 1 1 4 2 1 2 4 1 3h5l1-3 3-2 3-1-1-5-3-1-2-3-1-3z"/>',
    moon: '<path d="M20 14a8 8 0 0 1-10-10 8.5 8.5 0 1 0 10 10Z"/>',
    sun: '<circle cx="12" cy="12" r="4"/><path d="M12 2v2m0 16v2M2 12h2m16 0h2M5 5l1 1m12 12 1 1M5 19l1-1M18 6l1-1"/>',
    search: '<circle cx="10" cy="10" r="6"/><path d="m15 15 5 5"/>',
    filter: '<path d="M3 5h18l-7 8v6l-4 2v-8Z"/>',
    arrow: '<path d="M5 12h14m-5-5 5 5-5 5"/>', back: '<path d="M19 12H5m5-5-5 5 5 5"/>',
    down: '<path d="m7 10 5 5 5-5"/>', check: '<path d="m5 12 4 4L19 6"/>',
    error: '<circle cx="12" cy="12" r="9"/><path d="M12 7v6m0 3v1"/>',
    clock: '<circle cx="12" cy="12" r="9"/><path d="M12 6v6l4 2"/>',
    copy: '<rect x="8" y="8" width="12" height="13" rx="2"/><path d="M16 8V3H3v13h5"/>',
    branch: '<path d="M6 4v12a4 4 0 0 0 4 4h7M6 9h11"/><circle cx="6" cy="4" r="2"/><circle cx="19" cy="9" r="2"/><circle cx="19" cy="20" r="2"/>',
    refresh: '<path d="M20 10a8 8 0 1 0 0 5M20 4v6h-6"/>',
    external: '<path d="M14 3h7v7m0-7L10 14M10 3H3v18h18v-7"/>',
    run:'<path d="m5 4 14 8L5 20Z"/>',
    agent:'<rect x="4" y="6" width="16" height="14" rx="3"/><path d="M12 2v4M8 11h.01M16 11h.01M8 16h8"/>',
    model:'<rect x="5" y="5" width="14" height="14" rx="2"/><path d="M9 1v4m6-4v4M9 19v4m6-4v4M1 9h4m-4 6h4m14-6h4m-4 6h4M9 9h6v6H9Z"/>',
    tool:'<path d="M14 4a6 6 0 0 0-7 7l-4 4a3 3 0 0 0 4 4l4-4a6 6 0 0 0 7-7l-4 4-3-3Z"/>',
    retrieval:'<path d="M4 3h12v7M4 3v18h8M7 7h6M7 11h3"/><circle cx="16" cy="15" r="4"/><path d="m19 18 3 3"/>',
    api:'<path d="M3 7h16m-4-4 4 4-4 4M21 17H5m4-4-4 4 4 4"/>',
    state:'<path d="M4 4h16v16H4Z M8 8h8M8 12h8M8 16h5"/>',
    custom:'<path d="m12 3 9 9-9 9-9-9Z"/>',
    retry:'<path d="M4 10a8 8 0 1 1 1 8M4 4v6h6"/>',
    chevron:'<path d="m9 5 7 7-7 7"/>', expand:'<path d="M8 3H3v5m13-5h5v5M3 16v5h5m13-5v5h-5"/>'
  };
  const icon = (name, cls = '') => `<svg class="icon ${cls}" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${icons[name] || icons.branch}</svg>`;
  const badge = (text, kind = '', glyph = '') => `<span class="badge ${kind}">${glyph ? icon(glyph) : ''}${escape(text)}</span>`;
  const rawStatus = span => span.status===null||span.status===undefined||span.status===''?'Unknown':['OK','ERROR','UNSET'].includes(span.status)?span.status:'Unknown · '+span.status;
  const ms = n => n >= 1000 ? `${(n / 1000).toFixed(3)} s` : `${Number(n.toFixed(1))} ms`;
  const typeLabel = type => ({run:'Run',agent:'Agent',model:'Model',tool:'Tool',retrieval:'Retrieval',api:'API',state:'State',custom:'Custom'}[type] || 'Custom');
  const operationIcon = type => icon(icons[type] ? type : 'custom');
  const retryFor = span => run.spans.find(item => item.retryOf === span.id);
  const hasEvidence = item => item.analysis === 'Completed' && item.findings > 0;
  const href = (next, number = run.number, extra = '') => {const q=new URLSearchParams({screen:next,run:number,theme:state.theme,accent:state.accent,view:state.view.toLowerCase()});if(params.get('review')==='1')q.set('review','1');if(next==='evidence'&&number===run.number&&state.selected)q.set('span',state.selected);if(next==='trace'&&scaleSize&&number===run.number)q.set('size',scaleSize);if(number===run.number&&params.get('variant'))q.set('variant',params.get('variant'));for(const [key,value] of new URLSearchParams(extra.replace(/^&/,'')))q.set(key,value);return '?'+q;};
  const button = (label, action, cls = '', glyph = '', disabled = false) => `<button class="button ${cls}" data-action="${action}" ${disabled ? 'disabled title="Outside this disconnected visual preview"' : ''}>${glyph ? icon(glyph) : ''}${label}</button>`;
  function sidebar() {
    return `<aside class="sidebar" aria-label="Project navigation">
      <div class="brand"><span class="brand-mark">${icon('branch')}</span><strong class="nav-text">Agent Debugger</strong></div>
      <button class="project-select" disabled title="Project switching requires backend access"><span class="project-avatar">A</span><span class="nav-text"><strong>Agent examples</strong><small>Development</small></span>${icon('down', 'nav-text')}</button>
      <nav><a class="nav-item active" href="${href('runs')}" aria-current="page" title="Runs">${icon('runs')}<span class="nav-text">Runs</span></a>
      <button class="nav-item" aria-label="SDK Setup" disabled title="SDK Setup is specified; not rendered in this preview">${icon('setup')}<span class="nav-text">SDK Setup</span></button>
      </nav>
      <div class="sidebar-bottom"><button class="nav-item" aria-label="Settings" disabled title="Settings are outside this visual preview">${icon('settings')}<span class="nav-text">Settings</span></button>
      <button class="nav-item" aria-label="${state.theme === 'light' ? 'Dark' : 'Light'} appearance" data-action="theme" title="Switch to ${state.theme === 'light' ? 'dark' : 'light'} theme">${icon(state.theme === 'light' ? 'moon' : 'sun')}<span class="nav-text">${state.theme === 'light' ? 'Dark' : 'Light'} appearance</span></button>
      <div class="sidebar-divider"></div><button class="nav-item sidebar-toggle" data-action="sidebar" aria-expanded="${!state.collapsed}" aria-label="${state.collapsed ? 'Expand' : 'Collapse'} sidebar" title="${state.collapsed ? 'Expand' : 'Collapse'} sidebar">${icon('panel')}<span class="nav-text">Collapse sidebar</span></button>
      </div>
    </aside>`;
  }
  function header() {
    if(['trace','evidence'].includes(screen))return `<header class="app-header compact-run-header"><div class="compact-run-identity"><nav class="breadcrumbs" aria-label="Breadcrumb"><a href="${href('runs')}">Runs</a><span>/</span><span>${run.label}</span>${screen==='evidence'?'<span>/</span><span>Evidence</span>':''}</nav><h1>${escape(run.name)}</h1></div><div class="compact-run-actions"><button class="identity-copy mono" data-copy="${run.traceId}" aria-label="Copy trace ID ${run.traceId}">${run.traceId.slice(0,8)}…${run.traceId.slice(-4)} ${icon('copy')}</button>${screen==='trace'?investigationControl():`<a class="button small" href="${href('trace',run.number,'&restore=1&span='+state.selected)}">${icon('back')}Back to trace</a>`}<span class="sample-badge">Sample data</span></div></header>`;
    const tail = screen === 'runs' ? '' : `<span class="slash">/</span><a href="${href('trace')}">${run.label}</a>${screen === 'evidence' ? '<span class="slash">/</span><span>Evidence</span>' : ''}`;
    return `<header class="app-header"><div class="breadcrumbs"><a href="${href('runs')}">Runs</a>${tail}</div><div class="header-utilities"><span class="sample-badge">Sample data</span></div></header>`;
  }
  function investigationControl(){
    const positive=hasEvidence(run),count=params.get('variant')==='multiple-findings'&&positive?2:run.findings;
    const label=positive?count+' finding'+(count===1?'':'s'):run.analysis==='Completed'?'0 findings':run.analysis;
    const detail=`<div class="disclosure-surface" aria-label="Investigation details"><strong>Investigation ${escape(run.analysis.toLowerCase())}</strong>${run.analysis==='Completed'?`<p>Attempt 1 · ${run.attempt}</p><p>Analyzed input <code>${run.snapshot}</code></p><p class="secondary">${positive?'Source references are supplied by the authored finding.':'Zero findings does not establish correctness.'}</p>`:run.analysis==='Failed'?'<p>Trace data remains available. No retry is submitted by this preview.</p>':'<p>No investigation has been requested.</p>'}${positive?`<a class="button" href="${href('evidence')}">View evidence ${icon('arrow')}</a>`:`<button class="button" disabled>${run.analysis==='Failed'?'Retry':'Request'} investigation</button><p class="secondary">Unavailable in this static preview. No backend request is sent.</p>`}</div>`;
    return positive?`<div class="investigation-entry"><a class="investigation-result-link" href="${href('evidence')}">${icon('book')}Investigation · ${label}</a><details class="investigation-control compact-disclosure"><summary aria-label="Investigation details">${icon('down')}</summary>${detail}</details></div>`:`<details class="investigation-control compact-disclosure"><summary>${icon('book')}<span>Investigation · ${label}</span>${icon('down')}</summary>${detail}</details>`;
  }
  function footer() {
    if(params.get('review') !== '1') return '';
    return `<footer class="preview-footer" aria-label="Design review controls"><span>Design review only · Synthetic execution data</span><div class="review-controls"><label for="accent">Accent trial</label><select id="accent" aria-label="Accent candidate"><option value="steel" ${state.accent === 'steel'?'selected':''}>Steel</option><option value="blue" ${state.accent === 'blue'?'selected':''}>Cool blue</option></select><label for="scenario">Scenario</label><select id="scenario" aria-label="Review scenario"><option value="${screen}" selected>Current view</option><option value="reasoning">S1 · Incorrect reasoning</option><option value="retry">S2 · Recovered retry</option><option value="multi">S3 · Multiple sources</option><option value="long">Long model content</option><option value="login">Sign-in study</option><option value="register">Registration study</option><option value="expired">Expired-session study</option></select><a href="review-notes.md">Review notes ${icon('external')}</a></div></footer>`;
  }
  function runsPage() {
    const filtered = runs.filter(r => (`${r.name} ${r.label} ${r.traceId}`).toLowerCase().includes(state.search.toLowerCase()) && (state.outcome === 'All outcomes' || r.status === state.outcome) && (state.completeness === 'All completeness' || r.completeness === state.completeness));
    return `<section class="explorer"><div class="view-heading"><div><h1>Runs <span class="count">${filtered.length}</span></h1><p>Recorded executions in Agent examples</p></div><div class="actions">${button('SDK Setup', 'setup', '', 'setup', true)}${button('Refresh', 'refresh', '', 'refresh', true)}</div></div>
      <form class="query-toolbar" id="run-query"><div class="search-field">${icon('search')}<input aria-label="Search runs" placeholder="Search name or trace ID…" value="${escape(state.search)}"><kbd>↵</kbd></div>
      <span class="time-filter readonly-filter" title="Fixed sample-data window">${icon('clock')}15 Oct · 09:00–11:00 UTC</span>
      <select aria-label="Execution outcome" id="outcome"><option>All outcomes</option><option ${state.outcome === 'Completed' ? 'selected' : ''}>Completed</option><option ${state.outcome === 'Failed' ? 'selected' : ''}>Failed</option></select>
      <select aria-label="Telemetry completeness" id="completeness"><option>All completeness</option><option ${state.completeness === 'Complete' ? 'selected' : ''}>Complete</option><option ${state.completeness === 'Partial' ? 'selected' : ''}>Partial</option></select>
      </form>
      ${state.search || state.completeness !== 'All completeness' || state.outcome !== 'All outcomes' ? `<div class="active-filters"><span class="filter-chip">${escape([state.search,state.outcome!=='All outcomes'?state.outcome:'',state.completeness!=='All completeness'?state.completeness:''].filter(Boolean).join(' · '))}</span><span>${filtered.length} matching sample runs</span>${button('Clear filters', 'clear')}</div>` : ''}
      <div class="table-region" role="region" aria-label="Recorded runs" tabindex="0"><table class="runs-table"><colgroup><col class="col-run"><col class="col-start"><col class="col-status"><col class="col-duration"><col class="col-quality"><col class="col-errors"><col class="col-analysis"></colgroup>
      <thead><tr><th>Run</th><th>Started <span aria-label="descending">↓</span></th><th>Execution status</th><th class="numeric">Duration</th><th>Completeness</th><th class="numeric">Recorded errors</th><th>Investigation</th></tr></thead>
      <tbody>${filtered.map(r => `<tr><td><a class="run-link" href="${href('trace', r.number)}"><span>${escape(r.name)}</span>${icon('arrow')}</a><div class="row-secondary"><span>${r.label}</span><button class="identity-copy mono" data-copy="${r.traceId}" aria-label="Copy trace ID for ${r.label}" title="${r.traceId}">${r.traceId.slice(0,8)}…${r.traceId.slice(-4)} ${icon('copy')}</button></div></td><td><div class="tabular">${r.started}</div><div class="row-secondary">15 Oct 2026 · UTC</div></td><td>${badge(r.status, r.status === 'Failed' ? 'error-badge' : 'status-plain', r.status === 'Failed' ? 'error' : 'check')}</td><td class="numeric mono">${ms(r.duration)}</td><td>${badge(r.completeness, r.completeness === 'Partial' ? 'dashed' : 'status-plain', r.completeness === 'Partial' ? 'error' : '')}</td><td class="numeric">${r.recordedErrors ? `<span class="error-count">${icon('error')}${r.recordedErrors}</span>${r.recovered ? '<div class="row-secondary align-right">Recovered</div>' : ''}` : '<span class="mono muted">0</span>'}</td><td>${r.analysis === 'Failed' ? `<span class="analysis-error">${icon('error')}Failed</span><div class="row-secondary">Trace available</div>` : hasEvidence(r) ? `<a class="analysis-link" href="${href('evidence', r.number)}">${r.findings} finding ${icon('arrow')}</a><div class="row-secondary">Completed</div>` : `<span class="analysis-state">${r.analysis==='Not requested'?'Not requested':'0 findings'}</span><div class="row-secondary">${r.analysis==='Not requested'?'Trace available':'Completed'}</div>`}</td></tr>`).join('')}</tbody></table>${!filtered.length ? `<div class="empty"><h2>No matching runs</h2><p>The query covers these ${runs.length} sample runs only.</p><button class="button" data-action="clear">Clear filters</button></div>` : ''}</div>
      <div class="table-footer"><span>${filtered.length} runs · Sample data window</span><div><span>Page 1 of 1</span>${button('Previous', 'prev', 'small', '', true)}${button('Next', 'next', 'small', '', true)}</div></div></section>`;
  }
  function runHeading(evidence = false) {
    return `<section class="run-summary" aria-label="Execution metadata">${badge(run.status,run.status==='Failed'?'error-badge':'',run.status==='Failed'?'error':'check')}<span>${icon('clock')}<strong class="mono">${ms(run.duration)}</strong></span><span>Capture ${badge(run.completeness,run.completeness==='Partial'?'dashed':'')}</span><span>${fixtureDate} · ${run.started} UTC</span><span class="service-identity">${escape(run.service)}</span></section>`;
  }
  function code(value, options = {}) {
    if (value === null && options.reason) return `<div class="payload-unavailable">${icon('error')}<span>${escape(options.reason)}</span></div>`;
    const lines = JSON.stringify(value, null, 2).split('\n');
    return `<div class="code-block" aria-label="Captured JSON">${lines.map((line, i) => `<div class="code-line ${options.highlight && line.includes(options.highlight) ? 'cited-line' : ''}"><span class="line-number" aria-hidden="true">${i+1}</span><code>${escape(line)}</code></div>`).join('')}</div>`;
  }
  function attributes(span) {
    const entries=Object.entries(span.attributes).filter(([k,v])=>(k+' '+String(v)).toLowerCase().includes(state.attributeQuery.toLowerCase()));
    return `<table class="attribute-table"><tbody>${entries.map(([k,v]) => `<tr><th scope="row" class="mono">${escape(k)}</th><td class="mono">${escape(v)}</td></tr>`).join('')}</tbody></table>${!entries.length?'<p class="secondary">No matching recorded attributes.</p>':''}`;
  }
  function readable(value, selected, direction) {
    const prose = text => `<div class="readable-prose">${String(text).split(/\n\n/).map(p=>`<p>${escape(p)}</p>`).join('')}</div>`;
    const fields = object => `<dl class="readable-fields">${Object.entries(object).map(([key,item])=>`<div><dt class="mono">${escape(key)}</dt><dd>${item!==null&&typeof item==='object'?code(item):`<code>${escape(JSON.stringify(item))}</code>`}</dd></div>`).join('')}</dl>`;
    if(typeof value==='string') return prose(value);
    if(value===null || typeof value!=='object') return code(value);
    if(Array.isArray(value)) return code(value);
    if(Array.isArray(value.messages) && value.messages.every(m=>typeof m.role==='string'&&typeof m.content==='string')) {
      const {messages,...rest}=value;
      return `<div class="message-list">${messages.map(m=>`<section class="message"><h4>${escape(m.role)}</h4>${prose(m.content)}</section>`).join('')}</div>${Object.keys(rest).length?fields(rest):''}`;
    }
    if(typeof value.message==='string' && selected.type==='model') {
      const {message,...rest}=value;
      return `<div class="readable-response-label">Model response</div>${prose(message)}${Object.keys(rest).length?fields(rest):''}`;
    }
    if(selected.type==='retrieval' && Array.isArray(value.documents)) {
      return `<div class="retrieved-documents">${value.documents.map(document=>`<section><code>${escape(document.id)}</code><h4>${escape(document.title)}</h4>${prose(document.excerpt)}</section>`).join('')}</div>`;
    }
    if(selected.type==='retrieval' && typeof value.excerpt==='string') {
      const {excerpt,...rest}=value; return `${prose(excerpt)}${fields(rest)}`;
    }
    return fields(value);
  }
  function longModelContent(span) {
    if(span.type!=='model') return false;
    const strings = value => typeof value==='string'?[value]:value&&typeof value==='object'?Object.values(value).flatMap(strings):[];
    return [...strings(span.input),...strings(span.output)].some(text=>text.length>200)||JSON.stringify([span.input,span.output]).length>600;
  }
  function payloadPanel(selected, direction) {
    const redacted = direction==='input'&&state.redacted&&selected.key==='compose';
    const reason = direction==='output'?selected.outputReason:null;
    const label = direction==='input'?'Input':'Output';
    const typeDescription = selected.type==='tool' ? direction==='input'?'Arguments':'Result' : selected.type==='retrieval' ? direction==='input'?'Query':'Retrieved context' : selected.type==='model' ? direction==='input'?'Prompt':'Response' : 'Captured data';
    return `<section class="payload-panel" id="payload-${direction}"><div class="payload-heading"><h3 tabindex="-1">${label}<span class="payload-purpose">${typeDescription}</span></h3><div><span>${redacted?'Redacted':reason?'Unavailable':'Captured'}</span><button class="icon-button" data-copy-payload="${direction}" ${redacted||reason?'disabled':''} aria-label="Copy ${label.toLowerCase()}">${icon('copy')}</button></div></div>${redacted?'<div class="payload-unavailable">Input redacted at capture. No prompt reconstructed.</div>':reason?code(null,{reason}):state.payloadMode==='Captured JSON'?code(selected[direction]):readable(selected[direction],selected,direction)}</section>`;
  }
  function inspector(payloadReady = true) {
    const selected = run.spans.find(s => s.key === state.selected) || run.spans[0];
    const retry = retryFor(selected);
    const previous = run.spans.find(item=>item.id===selected.retryOf);
    const long = longModelContent(selected);
    const stacked = long || state.layout==='Stacked';
    return `<section class="inspector" aria-label="Selected span inspector"><div class="inspector-heading"><span class="type-icon">${operationIcon(selected.type)}</span><div class="span-heading-copy"><h2>${escape(selected.name)}</h2><div class="span-heading-meta"><span>${typeLabel(selected.type)} · <span class="mono">${ms(selected.duration)}</span></span>${badge(rawStatus(selected),selected.status==='ERROR'?'error-badge':'',selected.status==='ERROR'?'error':selected.status==='OK'?'check':'')}<details class="span-details compact-disclosure"><summary>Details</summary><div class="disclosure-surface"><strong>${escape(selected.name)}</strong><p class="mono">${selected.id}<button class="icon-button" data-copy="${selected.id}" aria-label="Copy span ID">${icon('copy')}</button></p><p>Start +${ms(selected.start)} from run start</p><p>Raw status: <code>${escape(selected.status??'Not recorded')}</code></p>${selected.retryOf?'<p>Explicit retry relationship recorded.</p>':''}</div></details></div></div><div class="span-panel-actions"><button class="icon-button" data-trace-action="focus-explorer" aria-label="Back to execution" title="Back to execution">${icon('back')}</button><button class="button small" data-trace-action="pin" aria-label="Pin inspector">Pin</button><details class="inspector-options compact-disclosure"><summary aria-label="Inspector options">⋯</summary><div class="disclosure-surface"><label class="trace-width-control">Width<input type="range" min="480" max="640" step="1" data-trace-width aria-label="Inspector width alternative"></label><p class="secondary">Pin to resize. Splitter also supports arrow keys, Home, End and Enter.</p></div></details><button class="icon-button" data-trace-action="close" aria-label="Close inspector">×</button></div></div>
      <div class="tabs" role="tablist" aria-label="Span information">${['Content','Attributes','Events','Errors'].map(t => `<button role="tab" aria-selected="${state.tab === t}" data-tab="${t}" class="${state.tab === t ? 'active' : ''}">${t}${t === 'Attributes' ? `<span>${Object.keys(selected.attributes).length}</span>` : (t === 'Events' || t === 'Errors') && selected.error ? '<span>1</span>' : ''}</button>`).join('')}</div>
      <div class="inspector-body ${state.wrap?'':'no-wrap'}" role="tabpanel" aria-label="${state.tab}" data-scroll="inspector-${selected.id}-${state.tab}" tabindex="0">
        ${selected.error ? `<div class="error-notice">${icon('error')}<div><strong>${selected.errorType||'Recorded error'}</strong><p>${escape(selected.error)}</p></div>${retry ? `<button class="text-button" data-select="${retry.key}">${run.recovered?'Recovered by':'Inspect retry'} attempt 2 ${icon('arrow')}</button>` : ''}</div>` : ''}
        ${previous ? `<div class="neutral-notice">${icon('retry')}<span>Recorded <code>retry_of</code> <code>${selected.retryOf}</code></span><button class="text-button" data-select="${previous.key}">Inspect attempt 1 ${icon('arrow')}</button></div>` : ''}
        ${!payloadReady ? '<div class="trace-payload-deferred"><h3>Payload not loaded</h3><p>Structure is available. Load this selected span’s captured content for inspection.</p><button class="button" data-trace-action="load-payload">Load captured payload</button></div>' : state.tab === 'Content' ? `<div class="content-toolbar"><div class="segmented" aria-label="Payload presentation">${['Readable','Captured JSON'].map(mode=>`<button data-payload-mode="${mode}" aria-pressed="${state.payloadMode===mode}" class="${state.payloadMode===mode?'selected':''}">${mode}</button>`).join('')}</div><div class="content-options">${!long?`<button class="text-button" data-action="layout">${stacked?'Pair panels':'Stack panels'}</button>`:'<span class="secondary">Long content · Stacked</span>'}${state.payloadMode==='Captured JSON'?`<button class="text-button" data-action="wrap" aria-pressed="${state.wrap}">Wrap ${state.wrap?'on':'off'}</button>`:'<span class="secondary">Wrapped</span>'}<button class="text-button" data-jump="input">Input</button><button class="text-button" data-jump="output">Output</button></div></div><div class="payload-grid ${stacked?'stacked':''}" data-layout="${stacked?'stacked':'paired'}">${payloadPanel(selected,'input')}${payloadPanel(selected,'output')}</div>
          ` : ''}
        ${payloadReady && state.tab === 'Attributes' ? `<label class="attribute-query">Search attributes<input aria-label="Search recorded attributes" value="${escape(state.attributeQuery)}" placeholder="Key or value…"></label><div data-attribute-results>${attributes(selected)}</div>` : ''}
        ${payloadReady && state.tab === 'Events' ? selected.error ? `<h3 class="section-heading">exception · +${ms(selected.duration)}</h3>${code({'exception.type':selected.errorType||'Not recorded','exception.message':selected.error})}` : '<div class="empty"><h3>No recorded events</h3><p>Absence of events is not proof of complete capture.</p></div>' : ''}
        ${payloadReady && state.tab === 'Errors' ? selected.error ? `<h3 class="section-heading error-text">Recorded operation error</h3><p>${escape(selected.error)}</p><p class="secondary">One recorded error group. Run outcome is independently reported as ${run.status}.</p>` : '<div class="empty"><h3>No explicit error recorded</h3><p>This does not establish semantic correctness.</p></div>' : ''}
      </div></section>`;
  }
  function tracePage() {
    return `${runHeading()}${run.quality ? `<div class="quality-notice compact-quality">${icon('error')}${run.quality}</div>` : ''}${traceStudy.shell()}`;
  }
  function finding() {
    const reasoning = run.scenario === 'reasoning';
    if(params.get('variant')==='multiple-findings'&&state.finding==='F-02')return {title:'Model input repeats the disputed policy window',category:'Context review',explanation:'The captured model input contains the retrieved 30-day window, while the fixed authoritative passage states 14 days.',limitation:'This authored review finding does not prove causality or policy applicability; verify exceptions and the source revision.'};
    return { title: reasoning ? 'Eligibility result is contradicted by the response' : 'Retrieved policy differs from the authoritative source', category: reasoning ? 'Reasoning inconsistency' : 'Context mismatch',
      explanation: reasoning ? state.redacted ? 'The tool returned false and the model approved the request. The model input is redacted, so the handoff cannot be inspected.' : 'The eligibility tool returned false. The model received that value, then returned true and approved the request.' : 'Retrieval supplied a 30-day window. The cited policy states 14 days; the 21-day order was approved using the retrieved value.',
      limitation: reasoning ? state.redacted ? 'Missing model input prevents verification of intermediate context. References do not establish business-rule correctness.' : 'Citations do not establish that the tool result or underlying business rule is correct.' : 'Policy applicability and any approved exception require confirmation. These references alone do not prove a causal root cause.' };
  }
  function sourceOptions() {
    return run.scenario === 'reasoning' ? [['tool','1 · Tool output'],['model','2 · Model input / output']] : [['retrieval','1 · Retrieval output'],['document','2 · Authoritative passage'],['model','3 · Model input']];
  }
  function sourcePayload(key) {
    if(key==='document') return authority.text+'\n\n'+authority.context;
    const span=run.spans.find(item=>item.key===(key==='tool'?'check':key==='model'?'compose':'retrieve'));
    return key==='model' ? run.scenario==='reasoning'?{input:span.input,output:span.output}:span.input : span.output;
  }
  function sourcePane(slot) {
    const key = slot === 'A' ? state.sourceA : state.sourceB;
    const sourceSpan = run.spans.find(s => s.key === (key === 'tool' ? 'check' : key === 'model' ? 'compose' : 'retrieve'));
    const isDocument = key === 'document';
    const heading = isDocument ? 'Refund policy' : key === 'model' ? 'compose-response' : key === 'tool' ? 'check-eligibility' : 'policy-search';
    const field = isDocument ? authority.passage : key === 'model' ? run.scenario === 'reasoning' ? 'input / output' : 'input.refund_window_days' : key === 'tool' ? 'output.eligible' : 'output.refund_window_days';
    const value = state.redacted && key === 'model' ? 'Input unavailable' : isDocument ? '14 days' : key === 'tool' ? 'false' : run.scenario === 'reasoning' ? 'false → true' : '30 days';
    return `<section class="source-pane" aria-label="Source ${slot}"><div class="source-slot"><strong>${slot==='A'?'Left · A':'Right · B'}</strong><select aria-label="Citation assigned to source ${slot}" data-source="${slot}">${sourceOptions().map(([v,t]) => `<option value="${v}" ${v === key ? 'selected' : ''}>${t}</option>`).join('')}</select><button class="icon-button" data-focus-source="${slot}" aria-label="${state.focusSource?'Compare sources':'Focus source '+slot}" title="${state.focusSource?'Restore source pair':'Show source '+slot+' at full width'}">${icon('expand')}</button></div>
      <div class="source-identity"><div class="source-name-row"><h3 tabindex="-1">${heading}</h3><span class="source-kind">${isDocument?'Revision 7':typeLabel(sourceSpan.type)}</span><details class="source-details compact-disclosure"><summary>Details</summary><div class="disclosure-surface"><p class="mono">${isDocument ? authority.id : sourceSpan.id}<button class="icon-button" data-copy="${isDocument ? authority.id : sourceSpan.id}" aria-label="Copy source ${slot} ID">${icon('copy')}</button></p><p>Analyzed input <code>${run.snapshot}</code></p><p>${isDocument?'Fixed authoritative revision 7.':'Historical span inspection requires approved snapshot resolution; this preview cannot resolve a historical backend snapshot.'}</p></div></details></div><div class="source-field mono">${field}</div></div>
      <div class="cited-value"><span>${state.evidenceUnavailable && slot === 'B' ? 'Reported value' : 'Cited value'}</span><strong class="mono">${value}</strong>${button('Copy source', 'copy-source-' + slot, 'small quiet', 'copy', (state.evidenceUnavailable && slot === 'B') || (state.redacted && key === 'model'))}</div>
      <div class="source-content" data-scroll="source-${slot}-${key}-${state.focusSource?'focus':'pair'}" tabindex="0" aria-label="Source ${slot} captured content">${state.evidenceUnavailable && slot === 'B' ? `<div class="empty"><h3>Analyzed source unavailable</h3><p>The fixed source revision cannot be resolved. Current content has not been substituted.</p></div>` : isDocument ? `<div class="document-passage"><p>Customers may request a refund <mark>within 14 days of delivery</mark>. Requests outside this window require a documented exception approved by the support lead.</p><details class="surrounding-context" data-surrounding="${slot}-${key}" ${state.sourceContexts.has(slot+'-'+key)?'open':''}><summary>Surrounding context</summary><p class="secondary">${authority.context}</p></details><div class="document-footnote">Effective 1 Oct 2026 · Fixed analyzed revision</div></div>` : state.redacted && key === 'model' ? '<div class="payload-unavailable">Model input redacted at capture. Evidence is unavailable.</div>' : code(sourcePayload(key), {highlight: key === 'tool' || run.scenario === 'reasoning' ? 'eligible' : 'refund_window_days'})}</div>
      <div class="source-footer">${!isDocument ? `<span class="secondary">Historical inspection unavailable</span><a class="text-button" href="${href('trace',run.number,'&restore=1&reveal=1&span='+sourceSpan.key)}">Open current span ${icon('arrow')}</a>` : '<span>Fixed document passage · read only</span>'}</div></section>`;
  }
  function evidencePage() {
    if (!hasEvidence(run)) return `${runHeading(true)}<div class="empty"><h2>No finding evidence to open</h2><p>${run.analysis==='Completed'?'This attempt returned zero grounded findings.':`Investigation ${run.analysis.toLowerCase()}.`} Trace data remains available through Back to trace.</p></div>`;
    const f = finding();
    if (run.scenario === 'reasoning' && !['tool','model'].includes(state.sourceA)) { state.sourceA = 'tool'; state.sourceB = 'model'; }
    const multiple=params.get('variant')==='multiple-findings';
    return `${runHeading(true)}<div class="evidence-attempt"><span><strong>Attempt 1</strong> · Completed</span><details class="attempt-details compact-disclosure"><summary class="mono">Analyzed ${run.snapshot}</summary><div class="disclosure-surface"><p>Attempt <code>${run.attempt}</code></p><p>Analyzed input <code>${run.snapshot}</code></p><p>Reference verification confirms resolution, not correctness or causality. Priority is supplied, not a confidence score.</p></div></details><span class="right secondary">${state.evidenceUnavailable || state.redacted ? 'Evidence incomplete' : 'References verified'}</span></div>
      <div class="evidence-workbench compact-evidence"><section class="evidence-main" aria-label="Finding evidence"><div class="finding-explanation"><div class="finding-kicker">${multiple?`<label>Finding <select aria-label="Finding selection" id="finding-selection"><option value="F-01" ${state.finding==='F-01'?'selected':''}>1 of 2 · Retrieved policy differs</option><option value="F-02" ${state.finding==='F-02'?'selected':''}>2 of 2 · Model input repeats policy</option></select></label>`:`<span>${state.finding} · 1 finding</span>`}<span>${f.category}</span>${badge(state.finding==='F-02'?'Medium priority':'High priority')}</div><h2>${f.title}</h2><p>${f.explanation}</p><div class="finding-limitation">${icon('error')}<span>${f.limitation}</span></div></div>
      <div class="citation-bar"><span>Citations</span>${sourceOptions().map(([key,label],i) => `<button class="citation-chip ${[state.sourceA,state.sourceB].includes(key) ? 'assigned' : ''}" data-citation="${key}" aria-label="Show citation ${i+1} in left source A${state.sourceB===key?'; exchange the existing pair':''}" title="Show in left source A${state.sourceB===key?' · exchanges pair':''}">${i+1}<span>${label.split(' · ')[1]}</span>${state.sourceA === key ? '<b>A</b>' : state.sourceB === key ? '<b>B</b>' : ''}</button>`).join('')}${state.focusSource?button('Compare sources','compare','small'):''}</div>
      <div class="sources-grid ${state.focusSource?'single-source':''}">${state.focusSource?sourcePane(state.focusSource):sourcePane('A')+sourcePane('B')}</div></section></div>`;
  }
  function authPage() {
    const expired = screen === 'expired', register = screen === 'register';
    return `<main class="auth-study"><div class="auth-brand"><span class="brand-mark">${icon('branch')}</span>Agent Debugger</div><section class="auth-card"><div class="eyebrow">DISCONNECTED FORM STUDY</div><h1>${expired ? 'Your session has expired' : register ? 'Create your account' : 'Sign in'}</h1><p class="secondary">${expired ? 'Sign in again to return to your authorized workspace.' : 'Access your projects and recorded executions.'}</p>${expired ? '<div class="neutral-notice">Protected content is obscured. FastAPI must reauthorize access before it is restored.</div>' : ''}<form><label>Email<input type="email" autocomplete="email" placeholder="you@example.com" disabled></label><label>Password<div class="password-study"><input type="password" autocomplete="' + (register ? 'new-password' : 'current-password') + '" placeholder="Enter your password" disabled><button type="button" disabled>Show</button></div></label><button class="button solid" type="button" disabled>${register ? 'Create account' : 'Sign in'}</button></form><p class="auth-note">Visual study only. Credential entry and submission are disabled. Authentication, password verification, sessions and authorization belong exclusively to FastAPI.</p><a href="${href(register ? 'login' : 'register')}">${register ? 'Already have an account? Sign in' : 'Need an account? Register'}</a></section><a class="secondary" href="${href('runs')}">Return to the synthetic design preview</a></main>`;
  }
  function render() {
    traceStudy?.beforeRender();
    app.querySelectorAll('[data-scroll]').forEach(element=>scrollMemory.set(element.dataset.scroll,[element.scrollLeft,element.scrollTop]));
    const active=document.activeElement;
    const focusAttribute=['data-action','data-tab','data-view','data-source','data-payload-mode','data-focus-source','data-expand','data-span','aria-label'].find(key=>active?.hasAttribute(key));
    const focusValue=focusAttribute?active.getAttribute(focusAttribute):null;
    document.documentElement.dataset.theme = state.theme;
    document.documentElement.dataset.screen = screen;
    document.documentElement.dataset.accent = state.accent;
    document.documentElement.dataset.sidebar = state.collapsed ? 'collapsed' : 'expanded';
    document.title = `${screen === 'runs' ? 'Runs' : screen === 'trace' ? 'Trace Detail' : screen === 'evidence' ? 'Evidence Focus' : 'Authentication study'} · Agent Debugger design`;
    app.innerHTML = ['login','register','expired'].includes(screen) ? authPage() : `<div class="app-shell">${sidebar()}<div class="workspace">${header()}<main class="page ${screen}-page">${screen === 'runs' ? runsPage() : screen === 'trace' ? tracePage() : evidencePage()}</main>${footer()}</div></div>`;
    if (state.notice) app.insertAdjacentHTML('beforeend', `<div class="toast" role="status">${escape(state.notice)}</div>`);
    app.querySelectorAll('[data-scroll]').forEach(element=>{const position=scrollMemory.get(element.dataset.scroll);if(position){element.scrollLeft=position[0];element.scrollTop=position[1];}});
    if(focusAttribute) [...app.querySelectorAll(`[${focusAttribute}]`)].find(element=>element.getAttribute(focusAttribute)===focusValue)?.focus({preventScroll:true});
    traceStudy?.mount();
  }
  async function copyCaptured(value, label) {
    try { await navigator.clipboard.writeText(typeof value==='string'?value:JSON.stringify(value,null,2)); state.notice=label+' copied'; }
    catch { state.notice='Clipboard unavailable. Select the captured text to copy it.'; }
  }
  function rememberTrace(context=traceStudy?.snapshot()) {
    if(!context)return;session.set(traceMemoryKey,context);
    app.querySelectorAll('a[href]').forEach(link=>{const url=new URL(link.href,location.href);if(url.origin===location.origin&&url.searchParams.get('screen')==='evidence'&&Number(url.searchParams.get('run'))===run.number){if(context.selected)url.searchParams.set('span',context.selected);url.searchParams.set('restore','1');url.searchParams.set('view',context.view.toLowerCase());link.href=url.href;}});
  }
  function rememberEvidence(){if(screen!=='evidence')return;app.querySelectorAll('[data-scroll]').forEach(e=>scrollMemory.set(e.dataset.scroll,[e.scrollLeft,e.scrollTop]));session.set(evidenceMemoryKey,{sourceA:state.sourceA,sourceB:state.sourceB,focusSource:state.focusSource,finding:state.finding,sourceContexts:[...state.sourceContexts],scroll:[...scrollMemory]});}
  app.addEventListener('toggle',event=>{const key=event.target.getAttribute('data-surrounding');if(key)event.target.open?state.sourceContexts.add(key):state.sourceContexts.delete(key);},true);
  app.addEventListener('click',event=>{
    app.querySelectorAll('.compact-disclosure[open]').forEach(details=>{if(!details.contains(event.target))details.open=false;});
    const link=event.target.closest('a[href]');if(!link)return;const url=new URL(link.href,location.href);if(url.origin!==location.origin)return;
    if(screen==='trace')rememberTrace();else rememberEvidence();
  },true);
  window.addEventListener('pagehide',()=>{if(screen==='trace')rememberTrace();else rememberEvidence();});
  app.addEventListener('input',event=>{if(event.target.getAttribute('aria-label')==='Search recorded attributes'){state.attributeQuery=event.target.value;const selected=run.spans.find(s=>s.key===state.selected);app.querySelector('[data-attribute-results]').innerHTML=attributes(selected);}});
  app.addEventListener('click', async event => {
    if(traceStudy?.click(event)) return;
    const target = event.target.closest('button, [data-span]');
    let focusSourceHeading=false;
    if (!target || target.disabled) return;
    if (target.dataset.action === 'sidebar') { state.collapsed = !state.collapsed; store.set('sidebar', state.collapsed ? 'collapsed' : 'expanded'); }
    else if (target.dataset.action === 'theme') { state.theme = state.theme === 'light' ? 'dark' : 'light'; store.set('theme', state.theme); const url = new URL(location.href); url.searchParams.set('theme', state.theme); history.replaceState(null, '', url); }
    else if (target.dataset.action === 'collapse') state.expanded.clear();
    else if (target.dataset.action === 'reveal') { let selected=run.spans.find(item=>item.key===state.selected); while(selected){state.expanded.add(selected.key);selected=run.spans.find(item=>item.key===selected.parent);} if(state.treeSearch)state.revealQuery=state.treeSearch;state.treeSearch=''; }
    else if (target.dataset.action === 'restore-query') {state.treeSearch=state.revealQuery||'';state.revealQuery=null;}
    else if (target.dataset.action === 'clear') { state.search = ''; state.outcome = 'All outcomes'; state.completeness = 'All completeness'; }
    else if (target.dataset.action === 'layout') state.layout=state.layout==='Stacked'?'Auto':'Stacked';
    else if (target.dataset.action === 'wrap') state.wrap=!state.wrap;
    else if (target.dataset.action === 'compare') state.focusSource=null;
    else if (target.dataset.expand) { const key = target.dataset.expand; state.expanded.has(key) ? state.expanded.delete(key) : state.expanded.add(key); }
    else if (target.dataset.span || target.dataset.select) { state.selected = target.dataset.span || target.dataset.select; state.tab = 'Content'; }
    else if (target.dataset.tab) state.tab = target.dataset.tab;
    else if (target.dataset.view) state.view = target.dataset.view;
    else if (target.dataset.payloadMode) state.payloadMode=target.dataset.payloadMode;
    else if (target.dataset.focusSource) state.focusSource=state.focusSource?null:target.dataset.focusSource;
    else if (target.dataset.jump) { const heading=app.querySelector(`#payload-${target.dataset.jump} h3`),region=app.querySelector('.inspector-body'),toolbar=app.querySelector('.content-toolbar');if(heading&&region){region.scrollTop+=heading.getBoundingClientRect().top-region.getBoundingClientRect().top-(toolbar?.offsetHeight||0)-12;heading.focus({preventScroll:true});}return; }
    else if (target.dataset.citation) { const next = target.dataset.citation; if (state.sourceB === next) state.sourceB = state.sourceA; state.sourceA = next; if(state.focusSource)state.focusSource='A';focusSourceHeading=true; }
    else if (target.dataset.copy) await copyCaptured(target.dataset.copy,'Identifier');
    else if (target.dataset.copyPayload) { const selected=run.spans.find(item=>item.key===state.selected); await copyCaptured(selected[target.dataset.copyPayload],target.dataset.copyPayload); }
    else if (target.dataset.action?.startsWith('copy-source-')) { const slot=target.dataset.action.endsWith('A')?'A':'B';await copyCaptured(sourcePayload(slot==='A'?state.sourceA:state.sourceB),'Source '+slot); }
    else return;
    if(traceStudy && target.closest('.inspector')) traceStudy.refreshInspector(); else render();
    if(focusSourceHeading) app.querySelector('[aria-label="Source A"] h3')?.focus({preventScroll:true});
    if (state.notice) setTimeout(() => { state.notice = ''; render(); }, 2000);
  });
  app.addEventListener('submit', event => {
    event.preventDefault();
    if(traceStudy?.submit(event)) return;
    if (event.target.id === 'run-query') state.search = event.target.querySelector('input').value.trim();
    if (event.target.id === 'tree-query') {state.treeSearch = event.target.querySelector('input').value.trim();state.revealQuery=null;}
    render();
  });
  app.addEventListener('change', event => {
    if(traceStudy?.change(event)) return;
    if (event.target.id === 'outcome') state.outcome = event.target.value;
    else if (event.target.id === 'completeness') state.completeness = event.target.value;
    else if (event.target.id === 'finding-selection') {state.finding=event.target.value;const url=new URL(location.href);url.searchParams.set('finding',state.finding);history.replaceState(null,'',url);}
    else if (event.target.id==='accent') {state.accent=event.target.value; const url=new URL(location.href);url.searchParams.set('accent',state.accent);history.replaceState(null,'',url);}
    else if (event.target.dataset.source) {
      const own = event.target.dataset.source === 'A' ? 'sourceA' : 'sourceB';
      const other = own === 'sourceA' ? 'sourceB' : 'sourceA';
      if (state[other] === event.target.value) state[other] = state[own];
      state[own] = event.target.value;
    } else if (event.target.id === 'scenario') {
      const choice = event.target.value;
      const number = { reasoning:1041, retry:1040, multi:1042, long:1036 }[choice];
      location.href = href(number ? choice === 'multi' ? 'evidence' : 'trace' : choice, number || run.number);
      return;
    } else return;
    render();
  });
  app.addEventListener('keydown', event => {if(event.key==='Escape'){const open=[...app.querySelectorAll('.compact-disclosure[open]')];if(open.length){const details=open.find(d=>d.contains(event.target))||open.at(-1);details.open=false;details.querySelector('summary').focus({preventScroll:true});event.preventDefault();return;}}traceStudy?.keydown(event);});
  if(screen==='trace') traceStudy=window.TRACE_DESIGN.create({run,state,params,app,escape,icon,ms,typeLabel,operationIcon,inspector,rawStatus,restored:restoredTrace,onContextChange:rememberTrace});
  render();
})();
