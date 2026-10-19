/* Local scale studies only. Not emitted telemetry, API schemas or performance data. */
(() => {
  function create(size) {
    const spans = [], prefix = 'a100' + size.toString(16).padStart(4, '0');
    const groups = Math.ceil((size - 3) / 26), duration = groups * 8600 + 1000;
    const add = (key,parent,name,type,start,length,input,output,extra={}) => {
      if (spans.length >= size) return null;
      const item = {key,parent,name,type,start,duration:length,input,output,status:'OK',...extra,
        id:prefix+(spans.length+1).toString(16).padStart(8,'0'),
        attributes:{'service.name':'fulfillment-agent','deployment.environment':'development','debugger.operation.type':type,...extra.attributes}};
      spans.push(item); return item;
    };
    add('root',null,'reconcile-fulfillment-batch','run',0,duration,{batch_id:'BATCH-1026-15'},{status:'completed'});
    add('agent','root','fulfillment-orchestrator','agent',8,duration-32,{batch_id:'BATCH-1026-15'},{completed:true});
    add('plan','agent','plan-reconciliation','model',40,720,{messages:[{role:'user',content:'Review the captured orders and return a fulfillment decision for each.'}]},{steps:['load_order','check_policy','verify_shipping','record_decision']});
    let group = 0;
    while (spans.length < size) {
      const n=++group, order='ORD-'+(8400+n), start=900+(n-1)*8600, root='order-'+n;
      const key = label => n===1 && ['a1','a2','compose'].includes(label)?label:root+'-'+label;
      const attributes={'order.id':order}, retry=n===1||n%7===0;
      const put=(label,parent,name,type,offset,length,input,output,extra={})=>add(key(label),parent,name,type,start+offset,length,input,output,{...extra,attributes:{...attributes,...extra.attributes}});
      add(root,'agent','reconcile-order · '+order,'agent',start,8000,{order_id:order},{decision:'ready_for_review'},{attributes});
      put('load',root,'load-order','tool',16,260,{order_id:order},{age_days:21,payment_recorded:true});
      put('load-api',key('load'),'GET /orders/'+order,'api',22,234,{method:'GET',path:'/orders/'+order},{status_code:200});
      put('policy',root,'resolve-fulfillment-policy','agent',300,2100,{order_id:order},{policy:'shipping-policy-v7'});
      put('retrieve',key('policy'),'search-shipping-policy','retrieval',316,540,{query:'Standard delivery and fulfillment preconditions'},{documents:[{id:'shipping-policy-v7',title:'Standard shipping',excerpt:'Reserve inventory and verify payment before requesting a shipping label.'}]});
      put('cache',key('retrieve'),'load-policy-passage','tool',330,190,{document_id:'shipping-policy-v7'},{revision:7});
      put('cache-api',key('cache'),'GET /policies/shipping/v7','api',340,160,{method:'GET'},{status_code:200});
      put('normalize',key('policy'),'normalize-order-context','tool',540,210,{order_id:order},{normalized:true});
      put('validate',key('normalize'),'validate-order-fields','state',548,188,{required_fields:['address','payment','items']},{valid:true});
      put('context',key('validate'),'resolve-delivery-context','agent',552,175,{region:'domestic'},{region:'domestic'});
      put('source',key('context'),'select-applicable-policy-source','retrieval',556,150,{policy_id:'shipping-policy-v7'},{document_id:'shipping-policy-v7'});
      put('index',key('source'),'POST /policy-index/query','api',560,120,{collection:'shipping-policies'},{status_code:200});
      const a1=put('a1',key('policy'),retry?'shipping-quote · attempt 1':'fetch-shipping-quote','tool',880,600,{order_id:order,timeout_ms:600},retry?null:{carrier:'standard',available:true},retry?{status:'ERROR',errorType:'TimeoutError',error:'Shipping quote was not returned within 600 ms.',outputReason:'Not produced — operation timed out',attributes:{'retry.attempt':1}}:{});
      put('a1-api',key('a1'),'GET /shipping/quote','api',888,580,{order_id:order},retry?null:{status_code:200},retry?{status:'ERROR',errorType:'TimeoutError',error:'Shipping source timed out.',errorOwner:key('a1'),outputReason:'Not produced — request timed out'}:{});
      put('a2',key('policy'),retry?'shipping-quote · attempt 2':'validate-shipping-quote','tool',1550,260,{order_id:order,attempt:retry?2:1},{carrier:'standard',available:true},retry&&a1?{retryOf:a1.id,attributes:{'retry.attempt':2,retry_of:a1.id}}:{});
      put('a2-api',key('a2'),'GET /shipping/quote','api',1560,240,{order_id:order},{status_code:200});
      put('eligibility',key('policy'),'check-fulfillment-preconditions','tool',1830,190,{payment_recorded:true,inventory_reserved:true},{ready_for_review:true});
      put('eligibility-state',key('eligibility'),'validate-precondition-result','state',1840,100,{ready_for_review:true},{valid:true});
      const long = [
        'Recorded decision\nThe order is ready for a fulfillment review. The captured order has a recorded payment, a reserved inventory allocation and an applicable standard-shipping policy. These checks support preparing the next shipping step; they do not prove that a package has been dispatched or delivered.',
        retry?'Recovered operation\nThe first shipping-quote request timed out after 600 ms. A separate second attempt returned an available standard carrier. Its recorded retry_of relationship links it to the failed attempt. The original timeout remains part of the execution history and must remain visible when reviewing this result.':'Recorded shipping quote\nThe shipping-quote lookup returned an available standard carrier and the separate validation step retained that result. No retry_of relationship is included in this order branch. The response must not infer a failed attempt or a recovery from nearby operation names or timestamps.',
        'Evidence boundaries\nThe conclusion uses the captured order, inventory and quote responses. The policy passage requires inventory reservation and payment verification before a label request. A successful quote is not proof of label purchase, carrier acceptance or delivery. No later state should be substituted for the values used here.',
        'Next check\nPreserve the review decision with its source identifiers. Review any captured label-preparation operation separately before proceeding. If a source is unavailable, retain that limitation. Do not invent a successful shipment, a missing document revision or a relationship based only on nearby timestamps.'
      ].join('\n\n');
      put('compose',root,'compose-fulfillment-decision','model',2600,4600,{messages:[{role:'system',content:'Summarize only the captured fulfillment checks. Preserve operation failures and explicitly recorded retries.'},{role:'user',content:'Review '+order+' and explain the evidence and remaining delivery limitations.'}],policy_id:'shipping-policy-v7'},{message:long});
      put('response-check',root,'validate-decision-fields','state',7250,100,{order_id:order},{valid:true});
      put('persist',root,'persist-fulfillment-decision','tool',7380,210,{order_id:order,decision:'ready_for_review'},{recorded:true});
      put('persist-api',key('persist'),'POST /audit/decisions','api',7385,190,{order_id:order},{status_code:201});
      put('shipping',root,'prepare-shipping-step','agent',7620,320,{order_id:order},{prepared:true});
      put('label',key('shipping'),'prepare-label-request','tool',7630,180,{order_id:order},{prepared:true});
      put('label-api',key('label'),'POST /shipping/validate','api',7640,160,{order_id:order},{status_code:200,validation_only:true});
      put('final',key('shipping'),'record-next-action','state',7860,60,{action:'await_fulfillment_review'},{recorded:true});
    }
    // The partial fixture has one missing recorded parent, independent of local load limits.
    if(size===2100) spans[53].parent='parent-not-captured';
    const children=new Map();
    spans.forEach(s=>{if(!children.has(s.parent))children.set(s.parent,[]);children.get(s.parent).push(s);});
    spans.forEach(s=>{s.childTotal=(children.get(s.key)||[]).length;const siblings=children.get(s.parent);s.siblingTotal=siblings.length;s.siblingPosition=siblings.indexOf(s)+1;});
    return {number:6000+size,label:'R-'+(6000+size),traceId:prefix+'7b3d4e519cfa81d20e347a65',name:'reconcile-fulfillment-batch',service:'fulfillment-agent',started:'11:12:06',duration,spans,status:'Completed',completeness:size===2100?'Partial':'Complete',analysis:'Not requested',findings:null,recordedErrors:spans.filter(s=>s.error&&!s.errorOwner).length,recovered:true,selected:'a1',initialLoaded:size===2100?840:size,quality:size===2100?'Partial capture: one recorded parent is missing. Loading more structure does not repair that gap.':null};
  }
  window.TRACE_SCALE_FIXTURES = {create};
})();
