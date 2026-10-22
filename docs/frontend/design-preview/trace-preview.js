/* Trace Detail interaction study. Local authored data only; no product APIs. */
(() => {
  const ROW=32, OVERSCAN=5;
  function create({run,state,params,app,escape:e,icon,ms,typeLabel,operationIcon,inspector,rawStatus,restored,onContextChange}) {
    const total=params.get('total')==='unknown'?null:run.spans.length;
    let loaded=Math.min(run.spans.length,restored?.loaded||run.initialLoaded||run.spans.length), rows=[], byKey=new Map(), children=new Map(), matches=new Set();
    let open=params.has('panel')?params.get('panel')!=='closed':restored?restored.open:!!params.get('span'), mode=['overlay','pinned'].includes(params.get('panel'))?params.get('panel'):restored?.mode||'overlay';
    let query=params.get('q')??restored?.query??'', kind=params.get('type')??restored?.kind??'', status=params.get('status')??restored?.status??'', savedQuery=restored?.savedQuery||null;
    let focused=restored?.focused||null, explorerTop=restored?.explorerTop||0, width=0, requestedWidth=restored?.width||0, root, explorer, viewport, observer, rangeKey='';
    let showIds=restored?.showIds??false;try{if(!restored)showIds=localStorage.getItem('debugger-design.trace-id-column')==='visible';}catch{/* optional preference */}if(params.has('ids'))showIds=params.get('ids')==='1';
    let notice='', draftQuery=query, jumpDraft='', resizeDrag=null, typeAhead='', lastTyped=0, mountedOnce=false;
    let from=Math.max(0,Number(params.get('from')??restored?.from)||0), to=Math.min(run.duration,Number(params.get('to')??restored?.to)||run.duration);
    if(to<=from) {from=0;to=run.duration;}
    const payloads=new Set(restored?.payloads||[]), paneScroll=new Map(restored?.paneScroll||[]), coveredControls=new Map();
    state.selected=params.get('span')||restored?.selected||null;
    function index() {
      byKey=new Map(run.spans.slice(0,loaded).map(s=>[s.key,s])); children=new Map();
      byKey.forEach(s=>{const parent=byKey.has(s.parent)?s.parent:null;if(!children.has(parent))children.set(parent,[]);children.get(parent).push(s);});
    }
    index();
    if(state.selected) {const initial=byKey.get(state.selected)||[...byKey.values()].find(s=>s.id===state.selected);if(initial)state.selected=initial.key;else {notice='Requested span is not available in the loaded structure.';open=false;}}
    focused=byKey.has(focused)?focused:byKey.has(state.selected)?state.selected:run.spans[0].key;
    function ancestors(key) {const list=[],seen=new Set();let s=byKey.get(key);while(s&&!seen.has(s.key)){seen.add(s.key);list.unshift(s);s=byKey.get(s.parent);}return list;}
    function flatten() {
      matches=new Set();const keep=new Set(), filtered=!!(query||kind||status);
      if(filtered) byKey.forEach(s=>{if((!query||`${s.name} ${s.id}`.toLowerCase().includes(query.toLowerCase()))&&(!kind||s.type===kind)&&(!status||(status==='__UNKNOWN__'?!['OK','ERROR','UNSET'].includes(s.status):s.status===status))){matches.add(s.key);ancestors(s.key).forEach(a=>keep.add(a.key));}});
      const result=[];
      function visit(s,depth){if(filtered&&!keep.has(s.key))return;result.push({span:s,depth,context:filtered&&!matches.has(s.key)});if(filtered||state.expanded.has(s.key))(children.get(s.key)||[]).forEach(child=>visit(child,depth+1));}
      (children.get(null)||[]).forEach(s=>visit(s,0));return result;
    }
    rows=flatten();
    function b(label,action,extra='',disabled=false){return `<button class="button small" data-trace-action="${action}" ${disabled?'disabled':''} ${extra}>${label}</button>`;}
    function shell() {
      return `<section class="trace-study" id="trace-study" data-mode="${mode}" data-view="${state.view.toLowerCase()}" data-show-ids="${showIds}" aria-label="Trace execution workspace">
        <section class="trace-explorer" id="trace-explorer" aria-label="Execution explorer">
          <div class="trace-toolbar"><div class="segmented" aria-label="Execution view">${['Tree','Timeline'].map(v=>`<button data-trace-view="${v}" aria-pressed="${state.view===v}">${v}</button>`).join('')}</div>
            <form class="trace-search" id="trace-search">${icon('search')}<input aria-label="Search loaded spans" placeholder="Search loaded names / IDs…" value="${e(draftQuery)}"><kbd>↵</kbd></form>
            <details class="trace-filter-menu compact-disclosure"><summary aria-label="Execution filters">${icon('filter')}<span data-filter-count></span></summary><div class="disclosure-surface"><strong>Loaded-span filters</strong><label>Operation type<select aria-label="Operation type" data-trace-filter="type"><option value="">All types</option>${['run','agent','model','tool','retrieval','api','state','custom'].map(t=>`<option value="${t}" ${kind===t?'selected':''}>${typeLabel(t)}</option>`).join('')}</select></label><label>Raw status<select aria-label="Recorded span status" data-trace-filter="status"><option value="">All statuses</option>${['OK','ERROR','UNSET'].map(s=>`<option ${status===s?'selected':''}>${s}</option>`).join('')}<option value="__UNKNOWN__" ${status==='__UNKNOWN__'?'selected':''}>Unknown / unrecognized</option></select></label>${b('Clear filters','clear-filters')}<p class="secondary">Only loaded structure is searched. Payload text is excluded.</p></div></details>
            <details class="trace-options compact-disclosure"><summary aria-label="Execution options">⋯</summary><div class="disclosure-surface"><strong>Execution options</strong>${b('Expand loaded branches','expand')}${b('Collapse loaded branches','collapse')}<label class="trace-column-choice"><input type="checkbox" data-trace-ids ${showIds?'checked':''}>Span ID column (wide view)</label><form id="trace-jump"><label>Jump to loaded ID<input aria-label="Jump to loaded span ID" placeholder="Exact span ID…" value="${e(jumpDraft)}"></label><button class="button small" type="submit">Go</button></form>${b('Fit selected','fit-selected','',!state.selected)}</div></details></div>
          <div class="trace-scope"><strong data-structure-count></strong><span class="scope-label">Loaded only</span>${b(icon('panel'),'focus-inspector','aria-label="Focus inspector"',!open)}${b('Reveal','reveal','aria-label="Reveal hidden selection"',!state.selected)}<span class="trace-match-nav" hidden>${b('‹','previous-match','aria-label="Previous matching operation"')}<span data-match-count></span>${b('›','next-match','aria-label="Next matching operation"')}</span><details class="trace-ancestor-menu compact-disclosure"><summary aria-label="Ancestor path"><span data-ancestor-path></span></summary><div class="disclosure-surface"><strong>Recorded ancestor path</strong><ol data-ancestor-links></ol></div></details></div>
          <div class="trace-notice" role="status" hidden></div>
          <div class="trace-time-controls" hidden>${b('−','zoom-out','aria-label="Zoom out"')}${b('+','zoom-in','aria-label="Zoom in"')}${b('Fit','fit','aria-label="Fit run"')}<span class="trace-time-label mono"></span><div class="trace-overview-track"><div class="trace-overview-window"></div><div class="trace-overview-selected"></div><input type="range" min="0" max="${run.duration}" step="1" aria-label="Time window center" data-trace-center></div></div>
          <div class="trace-columns"></div>
          <div class="trace-viewport" id="trace-viewport" role="tree" tabindex="0" aria-label="Loaded execution operations" aria-describedby="trace-keyboard-help"><div class="trace-canvas" role="presentation"><div class="trace-window" role="presentation"></div></div></div>
          <div class="trace-explorer-footer"><span data-window-count></span><div class="trace-load-row" hidden></div><span data-inspector-state class="sr-only"></span></div>
        </section>
        <div class="trace-resizer" role="separator" tabindex="0" aria-label="Inspector width" aria-orientation="vertical" aria-controls="trace-explorer trace-inspector" hidden></div>
        <aside class="trace-inspector-dock" id="trace-inspector" role="region" aria-labelledby="trace-inspector-title" hidden></aside>
        <p class="sr-only" id="trace-keyboard-help">Arrow keys navigate the loaded hierarchy. Enter inspects. F6 switches between execution and inspector. Escape closes an unpinned overlay.</p>
        <div class="sr-only" role="status" aria-live="polite" data-trace-announcement></div>
      </section>`;
    }
    function announce(text){const region=root?.querySelector('[data-trace-announcement]');if(region)region.textContent=text;}
    function syncUrl(){const url=new URL(location.href);url.searchParams.delete('reveal');url.searchParams.set('view',state.view.toLowerCase());url.searchParams.set('panel',open?mode:'closed');if(state.selected)url.searchParams.set('span',state.selected);else url.searchParams.delete('span');url.searchParams.set('from',from);url.searchParams.set('to',to);for(const [key,value] of [['q',query],['type',kind],['status',status]])value?url.searchParams.set(key,value):url.searchParams.delete(key);history.replaceState(null,'',url);onContextChange?.(snapshot());}
    function beforeRender(){if(!root?.isConnected)return;explorerTop=viewport.scrollTop;draftQuery=root.querySelector('#trace-search input').value;jumpDraft=root.querySelector('#trace-jump input').value;rememberPayload();observer?.disconnect();}
    function mount(){
      const restoreTop=explorerTop;root=app.querySelector('.trace-study');explorer=root.querySelector('.trace-explorer');viewport=root.querySelector('.trace-viewport');
      viewport.addEventListener('scroll',()=>{explorerTop=viewport.scrollTop;renderWindow();updateContext();});
      root.querySelector('[data-trace-center]').addEventListener('input',event=>{const length=to-from,center=Number(event.target.value);from=Math.max(0,Math.min(run.duration-length,center-length/2));to=from+length;updateTime();renderWindow(true);syncUrl();});
      const separator=root.querySelector('.trace-resizer');separator.addEventListener('pointerdown',event=>{if(!open||mode!=='pinned')return;resizeDrag={x:event.clientX,width};separator.setPointerCapture(event.pointerId);event.preventDefault();});
      separator.addEventListener('pointermove',event=>{if(!resizeDrag)return;requestedWidth=resizeDrag.width+resizeDrag.x-event.clientX;layout();});
      separator.addEventListener('pointerup',()=>resizeDrag=null);separator.addEventListener('pointercancel',()=>resizeDrag=null);
      observer=new ResizeObserver(()=>{layout();renderWindow(true);});observer.observe(root);
      updateExplorer();layout();refreshInspector();viewport.scrollTop=restoreTop;explorerTop=viewport.scrollTop;renderWindow(true);updateContext();if(params.get('reveal')==='1'){params.delete('reveal');select(state.selected,{reveal:true});}if(restored&&!mountedOnce){viewport.focus({preventScroll:true});announce('Trace context restored. Selection '+(byKey.get(state.selected)?.name||'retained')+'.');}mountedOnce=true;syncUrl();
    }
    function layout(){
      if(!root)return;const narrow=root.clientWidth<928, max=Math.max(480,Math.min(640,root.clientWidth-448));
      width=narrow?root.clientWidth:mode==='pinned'?Math.max(480,Math.min(max,requestedWidth||Math.min(600,root.clientWidth/2))):Math.max(480,Math.min(640,root.clientWidth/2,600));
      root.style.setProperty('--inspector-width',width+'px');root.dataset.mode=open?mode:'explore';root.dataset.narrow=String(narrow);root.dataset.showIds=String(showIds);
      root.style.setProperty('--row-scrollbar',(viewport.getBoundingClientRect().width-viewport.querySelector('.trace-canvas').getBoundingClientRect().width)+'px');
      const covered=narrow&&open;explorer.inert=covered;if(covered)explorer.setAttribute('aria-hidden','true');else explorer.removeAttribute('aria-hidden');
      root.querySelector('.trace-inspector-dock').hidden=!open;
      const sep=root.querySelector('.trace-resizer');sep.hidden=!open||mode!=='pinned'||narrow;sep.setAttribute('aria-valuemin','480');sep.setAttribute('aria-valuemax',String(Math.round(max)));sep.setAttribute('aria-valuenow',String(Math.round(width)));
      const pin=root.querySelector('[data-trace-action="pin"]');if(pin){pin.disabled=narrow;pin.textContent=mode==='pinned'?'Unpin':'Pin';pin.setAttribute('aria-label',mode==='pinned'?'Unpin inspector':'Pin inspector');pin.setAttribute('aria-pressed',String(mode==='pinned'));if(narrow)pin.title='Split mode requires more workspace width';}
      const preset=root.querySelector('[data-trace-width]');if(preset){preset.disabled=mode!=='pinned'||narrow;preset.max=String(max);preset.value=String(Math.round(width));}
      const caption=root.querySelector('[data-inspector-mode]');if(caption)caption.textContent=narrow?'Single pane':mode==='pinned'?'Pinned split':'Overlay';
      const payloadGrid=root.querySelector('.payload-grid');if(payloadGrid)payloadGrid.dataset.layout=getComputedStyle(payloadGrid).gridTemplateColumns.split(' ').length>1?'paired':'stacked';
      const idChoice=root.querySelector('[data-trace-ids]');if(idChoice){idChoice.disabled=explorer.clientWidth<840;idChoice.title=idChoice.disabled?'ID column requires wider exploration; IDs remain searchable and available in span Details.':'';}
      coveredControls.forEach((values,element)=>{for(const [key,value] of Object.entries(values))value===null?element.removeAttribute(key):element.setAttribute(key,value);});coveredControls.clear();
      if(open&&mode==='overlay'&&!narrow){const dock=root.querySelector('.trace-inspector-dock').getBoundingClientRect();explorer.querySelectorAll('button,input,select,a[href],summary').forEach(element=>{const rect=element.getBoundingClientRect();if(rect.width&&rect.right>dock.left&&rect.left<dock.right&&rect.bottom>dock.top&&rect.top<dock.bottom){coveredControls.set(element,{tabindex:element.getAttribute('tabindex'),'aria-hidden':element.getAttribute('aria-hidden')});element.setAttribute('tabindex','-1');element.setAttribute('aria-hidden','true');if(document.activeElement===element)viewport.focus({preventScroll:true});}});}
      updateContext();
    }
    function updateExplorer(){
      root.dataset.view=state.view.toLowerCase();root.querySelectorAll('[data-trace-view]').forEach(b=>{const selected=b.dataset.traceView===state.view;b.setAttribute('aria-pressed',String(selected));b.classList.toggle('selected',selected);});
      root.querySelector('[data-structure-count]').textContent=`${loaded.toLocaleString()} loaded${total!==null?' · '+total.toLocaleString()+' known':' · total unknown'}`;
      const filterCount=Number(!!kind)+Number(!!status);root.querySelector('[data-filter-count]').textContent=filterCount||'';root.querySelector('.trace-filter-menu summary').setAttribute('aria-label','Execution filters'+(filterCount?', '+filterCount+' active':''));
      root.querySelector('.trace-time-controls').hidden=state.view!=='Timeline';
      root.querySelector('.trace-columns').innerHTML=state.view==='Timeline'?`<div class="trace-grid timeline-grid-new"><span>Operation / recorded hierarchy</span><div class="trace-axis"></div><span class="numeric">Duration</span></div>`:`<div class="trace-grid tree-grid-new"><span>Operation / recorded hierarchy</span><span class="trace-id-column">Span ID</span><span class="trace-status-column">Status</span><span class="trace-start-column numeric">Start</span><span class="numeric">Duration</span></div>`;
      const loadRow=root.querySelector('.trace-load-row');loadRow.hidden=loaded===run.spans.length;
      loadRow.innerHTML=`<span>${total!==null?(total-loaded).toLocaleString()+' not loaded':'Total unknown'}</span>${b('Load '+Math.min(420,run.spans.length-loaded),'load-more','aria-label="Load next '+Math.min(420,run.spans.length-loaded)+' local spans"')}`;
      updateNotice();updateTime();updateContext();renderWindow(true);
    }
    function updateNotice(){const n=root.querySelector('.trace-notice');const labels=[savedQuery?'Filters relaxed for selected span.':'',notice];n.hidden=!labels.some(Boolean);n.innerHTML=(savedQuery?b('Restore filters','restore'):'')+labels.filter(Boolean).map(e).join(' ');}
    function updateContext(){if(!root)return;const selected=byKey.get(state.selected),path=ancestors(focused||state.selected);const node=root.querySelector('[data-ancestor-path]');node.textContent=path.length?path.map(s=>s.name).join(' / '):'Select an operation to inspect captured data';node.title=node.textContent;
      root.querySelector('[data-ancestor-links]').innerHTML=path.map(s=>`<li><button class="text-button" data-trace-action="ancestor" data-ancestor-key="${s.key}">${e(s.name)}</button></li>`).join('');
      const i=rows.findIndex(r=>r.span.key===state.selected),hidden=i<0||i*ROW<viewport.scrollTop||(i+1)*ROW>viewport.scrollTop+viewport.clientHeight;root.querySelector('[data-trace-action="reveal"]').hidden=!selected||!hidden;root.querySelector('[data-trace-action="reveal"]').disabled=!selected;root.querySelector('[data-trace-action="focus-inspector"]').disabled=!open;root.querySelector('[data-trace-action="focus-inspector"]').hidden=!open;
      const filtered=!!(query||kind||status),nav=root.querySelector('.trace-match-nav');nav.hidden=!filtered;root.querySelector('[data-match-count]').textContent=matches.size+' matches';nav.querySelectorAll('button').forEach(b=>b.disabled=matches.size===0);
      root.querySelector('[data-inspector-state]').innerHTML=selected?`${open?(mode==='pinned'?'Pinned':'Inspecting'):'Selected'} <strong>${e(selected.name)}</strong>${!open?' · Inspector closed':''}`:'Explore · Select a span to inspect';
    }
    function updateTime(){if(!root)return;const length=to-from;const axis=root.querySelector('.trace-axis');if(axis)axis.innerHTML=Array.from({length:5},(_,i)=>`<span>${((from+length*i/4)/1000).toFixed(length<10000?2:1)} s</span>`).join('');
      root.querySelector('.trace-time-label').textContent=`${(run.duration/length).toFixed(0)}× · ${ms(from)}–${ms(to)}`;
      const center=root.querySelector('[data-trace-center]');center.value=String((from+to)/2);center.disabled=length>=run.duration;
      const windowMark=root.querySelector('.trace-overview-window');windowMark.style.left=from/run.duration*100+'%';windowMark.style.width=length/run.duration*100+'%';
      const selected=byKey.get(state.selected),selectedMark=root.querySelector('.trace-overview-selected');selectedMark.hidden=!selected;if(selected){selectedMark.style.left=selected.start/run.duration*100+'%';selectedMark.style.width=Math.max(.3,selected.duration/run.duration*100)+'%';}
      root.querySelector('[data-trace-action="fit-selected"]').disabled=!selected;root.querySelector('[data-trace-action="fit-selected"]').hidden=!selected||state.view!=='Timeline';
      root.querySelector('[data-trace-action="zoom-out"]').disabled=length>=run.duration;root.querySelector('[data-trace-action="zoom-in"]').disabled=length<=run.duration/64;
    }
    function rowHTML(item,index){const s=item.span, childRows=children.get(s.key)||[],known=s.childTotal??childRows.length,hasChildren=known>0;
      const type=typeLabel(s.type),context=item.context?' · Ancestor context':'',orphan=s.parent&&!byKey.has(s.parent)?' · Parent unavailable':'';
      const meta=`${type}${s.status==='ERROR'?` <span class="error-text">${icon('error')} ERROR</span>${run.recovered&&run.spans.some(x=>x.retryOf===s.id)?' · Recovered':''}`:s.status!=='OK'?' · '+e(rawStatus(s)):''}${s.retryOf?` ${icon('retry')} Retry`:''}${known?` · ${childRows.length<known?childRows.length+'/'+known:known} ${known===1?'child':'children'}`:''}${context}${orphan}<span class="trace-inline-start"> · +${ms(s.start)}</span>`;
      const label=`<div class="trace-operation" style="--depth:${item.depth}">${Array.from({length:item.depth},(_,i)=>`<span class="trace-guide" style="left:${18+i*16}px" aria-hidden="true"></span>`).join('')}${hasChildren?`<button class="disclosure ${state.expanded.has(s.key)?'open':''}" tabindex="-1" data-trace-expand="${s.key}" aria-label="${state.expanded.has(s.key)?'Collapse':'Expand'} ${e(s.name)}">${icon('chevron')}</button>`:'<span class="disclosure leaf"></span>'}<span class="operation-glyph">${operationIcon(s.type)}</span><span class="operation-copy"><span class="operation-name">${e(s.name)}</span><span class="operation-meta">${meta}</span></span></div>`;
      let timing='';if(state.view==='Timeline'){const end=s.start+s.duration,length=to-from,valid=Number.isFinite(s.start)&&Number.isFinite(s.duration)&&s.duration>=0;
        timing=`<div class="trace-time-track" aria-label="Start ${ms(s.start)}, end ${ms(end)} from run start">${[25,50,75].map(position=>`<span class="trace-time-grid" style="left:${position}%" aria-hidden="true"></span>`).join('')}${!valid?'<span>Timing unavailable</span>':end<from||s.start>to?'<span class="trace-outside-time">Outside window</span>':`<span class="trace-time-bar ${s.status==='ERROR'?'error-bar':''} ${s.duration===0?'time-point':''}" data-start="${s.start}" data-duration="${s.duration}" style="left:${Math.max(0,(s.start-from)/length*100)}%;width:${Math.max(0,(Math.min(end,to)-Math.max(s.start,from))/length*100)}%" title="Recorded start ${ms(s.start)}, end ${ms(end)}"></span>`}</div>`;}
      return `<div id="trace-row-${s.key}" class="trace-data-row trace-grid ${state.view==='Timeline'?'timeline-grid-new':'tree-grid-new'} ${state.selected===s.key?'selected':''} ${focused===s.key?'keyboard-active':''} ${item.context?'ancestor-row':''}" data-trace-span="${s.key}" data-row-index="${index}" role="treeitem" aria-label="${e(s.name)} · ${type} · ${e(rawStatus(s))} · Start ${ms(s.start)} · Duration ${ms(s.duration)}${context}${orphan}" aria-selected="${state.selected===s.key}" aria-level="${item.depth+1}" aria-posinset="${s.siblingPosition||(children.get(s.parent)||children.get(null)||[]).indexOf(s)+1}" aria-setsize="${s.siblingTotal||(children.get(s.parent)||children.get(null)||[]).length}" ${hasChildren?`aria-expanded="${state.expanded.has(s.key)}"`:''} style="top:${index*ROW}px">${label}${state.view==='Timeline'?timing:`<code class="trace-id-column">${s.id}</code><span class="trace-status-column ${s.status==='ERROR'?'error-text':''}">${e(rawStatus(s))}</span><span class="trace-start-column mono numeric">+${ms(s.start)}</span>`}<span class="mono numeric">${ms(s.duration)}</span></div>`;
    }
    function renderWindow(force=false){if(!viewport)return;const top=viewport.scrollTop, height=viewport.clientHeight, start=Math.max(0,Math.floor(top/ROW)-OVERSCAN),end=Math.min(rows.length,Math.ceil((top+height)/ROW)+OVERSCAN),activeIndex=rows.findIndex(r=>r.span.key===focused);
      const key=[start,end,state.view,state.selected,focused,from,to,rows.length].join('|');if(!force&&key===rangeKey)return;rangeKey=key;
      const canvas=viewport.querySelector('.trace-canvas');canvas.style.height=(rows.length?rows.length*ROW:viewport.clientHeight)+'px';
      let visible=rows.slice(start,end).map((r,i)=>rowHTML(r,start+i)).join('');if(activeIndex>=0&&(activeIndex<start||activeIndex>=end))visible+=rowHTML(rows[activeIndex],activeIndex);
      canvas.querySelector('.trace-window').innerHTML=visible||'<div class="empty"><h3>No matches in loaded structure</h3><p>Unloaded spans have not been searched. Clear filters or load more structure when available.</p></div>';
      if(activeIndex>=0)viewport.setAttribute('aria-activedescendant','trace-row-'+focused);else viewport.removeAttribute('aria-activedescendant');
      const first=Math.min(rows.length,Math.floor(top/ROW)+1),last=Math.min(rows.length,Math.ceil((top+height)/ROW));root.querySelector('[data-window-count]').textContent=`${first}–${last} / ${rows.length.toLocaleString()} ${query||kind||status?'filtered':'expanded'} rows`;
    }
    function rebuild(){const anchor=rows[Math.floor(viewport.scrollTop/ROW)]?.span.key,offset=viewport.scrollTop%ROW;rows=flatten();let key=anchor,index=-1;while(key&&index<0){index=rows.findIndex(r=>r.span.key===key);key=byKey.get(key)?.parent;}viewport.scrollTop=index<0?0:index*ROW+offset;explorerTop=viewport.scrollTop;updateExplorer();}
    function rememberPayload(){const body=root?.querySelector('.inspector-body');if(body&&!root.querySelector('.trace-inspector-dock').hidden)paneScroll.set(body.dataset.scroll,[body.scrollLeft,body.scrollTop]);}
    function refreshInspector(){if(!root)return;rememberPayload();const host=root.querySelector('.trace-inspector-dock');if(!open){host.hidden=true;return;}const selected=byKey.get(state.selected);if(!selected){open=false;layout();return;}
      payloads.add(selected.id);host.innerHTML=inspector(true);
      host.querySelector('h2').id='trace-inspector-title';host.querySelector('h2').tabIndex=-1;host.querySelector('.inspector').removeAttribute('aria-label');
      layout();
      const body=host.querySelector('.inspector-body'),position=paneScroll.get(body.dataset.scroll);if(position){body.scrollLeft=position[0];body.scrollTop=position[1];}
      updateTime();
    }
    function close(restore=true){rememberPayload();open=false;layout();renderWindow(true);syncUrl();if(restore)viewport.focus({preventScroll:true});announce('Inspector closed. Selection retained.');}
    function select(key,{reveal=false,locate=false}={}){const s=byKey.get(key);if(!s){notice='Span not found in loaded structure. Unloaded spans are not searched.';updateNotice();return;}
      rememberPayload();if(state.selected!==key)state.tab='Content';state.selected=key;focused=key;open=true;notice='';if(reveal||locate){if(reveal&&(query||kind||status)){savedQuery={query,kind,status};query='';kind='';status='';root.querySelector('#trace-search input').value='';root.querySelectorAll('[data-trace-filter]').forEach(el=>el.value='');}ancestors(key).forEach(a=>state.expanded.add(a.key));rows=flatten();const i=rows.findIndex(r=>r.span.key===key);viewport.scrollTop=Math.max(0,i*ROW-ROW*2);explorerTop=viewport.scrollTop;updateExplorer();}
      refreshInspector();renderWindow(true);syncUrl();if(root.dataset.narrow==='true')root.querySelector('#trace-inspector-title').focus({preventScroll:true});else viewport.focus({preventScroll:true});announce('Inspector open for '+s.name+'. F6 moves to the inspector.');
    }
    function zoom(action){const length=to-from;let next=action==='zoom-in'?length/2:Math.min(run.duration,length*2),center=(from+to)/2;
      if(action==='fit'){from=0;to=run.duration;}else if(action==='fit-selected'){const s=byKey.get(state.selected);if(!s)return;next=Math.max(run.duration/64,s.duration*1.5);center=s.start+s.duration/2;from=Math.max(0,Math.min(run.duration-next,center-next/2));to=from+next;}else {next=Math.max(run.duration/64,Math.min(run.duration,next));from=Math.max(0,Math.min(run.duration-next,center-next/2));to=from+next;}updateTime();renderWindow(true);syncUrl();}
    function click(event){if(!root)return false;const t=event.target,action=t.closest('[data-trace-action]'),row=t.closest('[data-trace-span]'),expand=t.closest('[data-trace-expand]'),view=t.closest('[data-trace-view]');
      if(!root.contains(t)&&t.closest('a[href]'))return false;
      if(action?.disabled)return true;
      if(expand){if(open&&mode==='overlay')close(false);const key=expand.dataset.traceExpand;state.expanded.has(key)?state.expanded.delete(key):state.expanded.add(key);focused=key;rebuild();viewport.focus({preventScroll:true});return true;}
      if(row){select(row.dataset.traceSpan);return true;}
      if(open&&mode==='overlay'&&!t.closest('.trace-inspector-dock')&&action?.dataset.traceAction!=='focus-inspector')close(false);
      if(view){state.view=view.dataset.traceView;updateExplorer();syncUrl();return true;}
      if(t.closest('[data-select]')){select(t.closest('[data-select]').dataset.select,{reveal:true});return true;}
      if(!action)return false;
      const disclosure=action.closest('details');if(disclosure){disclosure.open=false;disclosure.querySelector('summary')?.focus({preventScroll:true});}
      const a=action.dataset.traceAction;
      if(a==='close')close();
      else if(a==='pin'){rememberPayload();mode=mode==='pinned'?'overlay':'pinned';requestedWidth=width;layout();refreshInspector();renderWindow(true);syncUrl();root.querySelector('[data-trace-action="pin"]').focus({preventScroll:true});}
      else if(a==='focus-explorer'){if(root.dataset.narrow==='true')close();else viewport.focus({preventScroll:true});}
      else if(a==='focus-inspector')root.querySelector('#trace-inspector-title')?.focus({preventScroll:true});
      else if(a==='load-payload'){const s=byKey.get(state.selected);if(s){payloads.add(s.id);refreshInspector();root.querySelector('.tabs button.active').focus({preventScroll:true});announce('Captured sample payload loaded for '+s.name);}}
      else if(a==='collapse'){state.expanded.clear();rebuild();}
      else if(a==='expand'){byKey.forEach(s=>state.expanded.add(s.key));rebuild();}
      else if(a==='reveal')select(state.selected,{reveal:true});
      else if(a==='ancestor')select(action.dataset.ancestorKey,{locate:true});
      else if(a==='previous-match'||a==='next-match'){const found=rows.filter(r=>matches.has(r.span.key)).map(r=>r.span.key),current=found.indexOf(state.selected),next=current<0?(a==='next-match'?0:found.length-1):(current+(a==='next-match'?1:-1)+found.length)%found.length;if(found[next])select(found[next],{locate:true});}
      else if(a==='restore'){({query,kind,status}=savedQuery);draftQuery=query;savedQuery=null;root.querySelector('#trace-search input').value=query;root.querySelector('[data-trace-filter="type"]').value=kind;root.querySelector('[data-trace-filter="status"]').value=status;rebuild();syncUrl();}
      else if(a==='clear-filters'){query='';kind='';status='';draftQuery='';savedQuery=null;notice='';root.querySelector('#trace-search input').value='';root.querySelectorAll('[data-trace-filter]').forEach(el=>el.value='');rebuild();syncUrl();}
      else if(a==='load-more'){const before=loaded;loaded=Math.min(run.spans.length,loaded+420);run.spans.slice(before,loaded).forEach(s=>state.expanded.add(s.key));index();rebuild();announce((loaded-before)+' additional sample spans available. Capture quality is unchanged.');}
      else if(['zoom-in','zoom-out','fit','fit-selected'].includes(a))zoom(a);
      syncUrl();return true;
    }
    function submit(event){if(event.target.id==='trace-search'){query=event.target.querySelector('input').value.trim();draftQuery=query;savedQuery=null;notice='';rebuild();syncUrl();return true;}if(event.target.id==='trace-jump'){jumpDraft=event.target.querySelector('input').value.trim();const s=[...byKey.values()].find(s=>s.id===jumpDraft||s.key===jumpDraft);if(s)select(s.key,{reveal:true});else {notice='Span not found in loaded structure. Unloaded spans are not searched.';updateNotice();}return true;}return false;}
    function change(event){if(event.target.hasAttribute('data-trace-ids')){showIds=event.target.checked;try{localStorage.setItem('debugger-design.trace-id-column',showIds?'visible':'hidden');}catch{/* optional preference */}layout();renderWindow(true);return true;}if(event.target.dataset.traceFilter){if(event.target.dataset.traceFilter==='type')kind=event.target.value;else status=event.target.value;savedQuery=null;notice='';rebuild();syncUrl();return true;}if(event.target.hasAttribute('data-trace-width')){requestedWidth=Number(event.target.value);layout();return true;}return false;}
    function keydown(event){const t=event.target;
      if(event.key==='F6'&&open){event.preventDefault();if(t.closest('.trace-inspector-dock'))viewport.focus({preventScroll:true});else root.querySelector('#trace-inspector-title')?.focus({preventScroll:true});return true;}
      if(event.key==='Escape'&&open&&(mode==='overlay'||root.dataset.narrow==='true')&&!event.defaultPrevented&&!t.matches('select')){event.preventDefault();close();return true;}
      if(t.classList.contains('trace-resizer')){if(['ArrowLeft','ArrowRight','Home','End','Enter'].includes(event.key)){event.preventDefault();requestedWidth=event.key==='Home'?480:event.key==='End'?640:event.key==='Enter'?Math.min(600,root.clientWidth/2):width+(event.key==='ArrowLeft'?16:-16);layout();return true;}return false;}
      if(t!==viewport)return false;let i=rows.findIndex(r=>r.span.key===focused),next=i,s=rows[i]?.span;if(!s&&rows.length){i=0;s=rows[0].span;}
      if(event.key==='ArrowDown')next=Math.min(rows.length-1,i+1);else if(event.key==='ArrowUp')next=Math.max(0,i-1);else if(event.key==='Home')next=0;else if(event.key==='End')next=rows.length-1;
      else if(event.key==='PageDown')next=Math.min(rows.length-1,i+Math.max(1,Math.floor(viewport.clientHeight/ROW)-1));else if(event.key==='PageUp')next=Math.max(0,i-Math.max(1,Math.floor(viewport.clientHeight/ROW)-1));
      else if(event.key==='Enter'||event.key===' '){event.preventDefault();if(s)select(s.key);return true;}
      else if(event.key==='ArrowRight'&&s){if((s.childTotal||(children.get(s.key)||[]).length)&&!state.expanded.has(s.key)){state.expanded.add(s.key);rebuild();}else if(rows[i+1]?.span.parent===s.key)next=i+1;}
      else if(event.key==='ArrowLeft'&&s){if((s.childTotal||(children.get(s.key)||[]).length)&&state.expanded.has(s.key)){state.expanded.delete(s.key);rebuild();}else next=rows.findIndex(r=>r.span.key===s.parent);}
      else if(event.key.length===1&&!event.ctrlKey&&!event.metaKey){const now=Date.now();typeAhead=now-lastTyped<700?typeAhead+event.key:event.key;lastTyped=now;const offset=rows.slice(i+1).concat(rows.slice(0,i+1)).find(r=>r.span.name.toLowerCase().startsWith(typeAhead.toLowerCase()));if(offset)next=rows.indexOf(offset);}
      else return false;
      event.preventDefault();if(rows[next]){focused=rows[next].span.key;const top=next*ROW;if(top<viewport.scrollTop)viewport.scrollTop=top;else if(top+ROW>viewport.scrollTop+viewport.clientHeight)viewport.scrollTop=top+ROW-viewport.clientHeight;explorerTop=viewport.scrollTop;}renderWindow(true);updateContext();return true;
    }
    function snapshot(){rememberPayload();return {selected:state.selected,focused,view:state.view,expanded:[...state.expanded],query,kind,status,savedQuery,open,mode,width:requestedWidth||width,explorerTop:viewport?.scrollTop??explorerTop,from,to,loaded,showIds,payloads:[...payloads],paneScroll:[...paneScroll],tab:state.tab,payloadMode:state.payloadMode,layout:state.layout,wrap:state.wrap};}
    return {shell,beforeRender,mount,refreshInspector,click,submit,change,keydown,snapshot};
  }
  window.TRACE_DESIGN={create};
})();
