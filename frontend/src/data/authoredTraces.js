// Fixture data adapted from the approved static study; no UI or server contract.
/* Authored UI fixtures only. These objects are NOT proposed API schemas. */

  const traceIds = {
    1042:'7b83c2d94e1a4f0e9a6710c24d86b519', 1041:'c4168f27a9534b1e86d0fa320b57ec14',
    1040:'a9e5d271604b4c8fb38a16d20c79e543', 1039:'5d20f89c731a4e62b14c0958e7a306df',
    1038:'ef398a6027d14b9c85a60d319c47e2b1', 1037:'2a6e970bd4184c83b0917d63fe25a940',
    1036:'94d21fa608b34e97ac165b20d873cf49', 1035:'b8064c13e2594f0d97a1346c50eb28d7'
  };
  const traceId = run => traceIds[run];
  const id = (run, n) => traceId(run).slice(0,8) + n.toString(16).padStart(8, '0');
  function build(number, scenario, started, variant = '') {
    const order = `ORD-${number + 7370}`;
    const spans = [];
    function span(key, parent, name, type, start, duration, input, output, extras = {}) {
      const item = { key, parent, name, type, start, duration, input, output, status: 'OK', ...extras };
      item.id = id(number, spans.length + 1);
      item.attributes = {
        'service.name': 'refund-agent',
        'deployment.environment': 'development',
        'debugger.operation.type': type,
        'order.id': order,
        ...(extras.attributes || {})
      };
      spans.push(item);
      return item;
    }
    const duration = scenario === 'retry' ? 2418 : scenario === 'reasoning' ? 3176 : 4284;
    span('root', null, 'refund-eligibility-review', 'run', 0, duration,
      { order_id: order, request: 'Can I return this order?', order_age_days: 21 },
      { decision: scenario === 'reasoning' || scenario === 'multi' ? 'approved' : 'reviewed', order_id: order });
    span('agent', 'root', 'support-agent', 'agent', 5, duration - 14,
      { task: 'Review refund eligibility', order_id: order }, { completed: true },
      { attributes: { 'agent.name': 'support-agent' } });
    span('triage', 'agent', 'classify-request', 'model', 18, scenario === 'retry' ? 162 : 310,
      { message: 'Can I return this order?' }, { intent: 'refund_request' });
    if (scenario === 'retry') {
      span('lookup', 'agent', 'lookup-order', 'tool', 200, 1590,
        { order_id: order }, { fulfillment_status: 'shipped', attempts: 2 });
      const a1 = span('a1', 'lookup', 'lookup-order · attempt 1', 'tool', 220, 1200,
        { order_id: order, attempt: 1, timeout_ms: 1200 }, null,
        { status: 'ERROR', errorType:'TimeoutError', error: 'Order service did not respond within 1,200 ms.', outputReason: 'Not produced — operation failed',
          attributes: { 'retry.attempt': 1, 'timeout.ms': 1200 } });
      span('api1', 'a1', `GET /orders/${order}`, 'api', 225, 1190,
        { method: 'GET', path: `/orders/${order}` }, null,
        { status: 'ERROR', errorType:'TimeoutError', outputReason: 'Not produced — request timed out', error: 'TimeoutError', errorOwner: 'a1' });
      span('a2', 'lookup', 'lookup-order · attempt 2', 'tool', 1460, 320,
        { order_id: order, attempt: 2 }, { order_id: order, fulfillment_status: 'shipped', order_age_days: 21 },
        { retryOf: a1.id, attributes: { 'retry.attempt': 2, 'retry_of': a1.id } });
      span('api2', 'a2', `GET /orders/${order}`, 'api', 1465, 302,
        { method: 'GET', path: `/orders/${order}` }, { status_code: 200, fulfillment_status: 'shipped' });
      span('compose', 'agent', 'compose-response', 'model', 1820, 500,
        { order_status: 'shipped', order_age_days: 21 }, { message: 'Your order has shipped. I have reviewed your request.' });
      span('record', 'agent', 'record-decision', 'state', 2360, 35,
        { order_id: order }, { recorded: true });
    } else {
      span('load', 'agent', 'load-order', 'tool', 340, 486,
        { order_id: order }, { order_age_days: 21, fulfillment_status: 'delivered' });
      span('api', 'load', `GET /orders/${order}`, 'api', 350, 462,
        { method: 'GET', path: `/orders/${order}` }, { status_code: 200, order_age_days: 21 });
      span('evaluate', 'agent', 'evaluate-refund-policy', 'agent', 850, duration - 938,
        { order_id: order, order_age_days: 21 }, { decision: 'approved' });
      span('retrieve', 'evaluate', 'policy-search', 'retrieval', 862, scenario === 'multi' ? 748 : 320,
        { query: 'refund window for delivered orders', collection: 'support-policies' },
        { policy_id: 'refund-standard', refund_window_days: scenario === 'multi' ? 30 : 14,
          order_age_days: 21, cache_revision: scenario === 'multi' ? 'r18' : 'r21',
          excerpt: `Refunds are accepted within ${scenario === 'multi' ? 30 : 14} days of delivery.` });
      if (scenario === 'multi') {
        span('vector', 'retrieve', 'query-policy-index', 'api', 872, 214,
          { collection: 'support-policies', policy_id: 'refund-standard' }, { matched_policy: 'refund-standard' });
        span('cache', 'retrieve', 'load-cached-policy', 'tool', 1168, 390,
          { cache_key: 'refund-standard:r18' }, { refund_window_days: 30, cache_revision: 'r18' });
      } else {
        span('check', 'evaluate', 'check-eligibility', 'tool', 1200, 146,
          { order_age_days: 21, refund_window_days: 14 }, { eligible: false, reason: 'outside_refund_window' });
        span('check-api', 'check', 'POST /eligibility/check', 'api', 1205, 120,
          { order_age_days: 21, refund_window_days: 14 }, { eligible: false });
      }
      span('compose', 'evaluate', 'compose-response', 'model', scenario === 'multi' ? 1664 : 1398,
        scenario === 'multi' ? 2360 : 1684,
        scenario === 'multi'
          ? { order_age_days: 21, refund_window_days: 30, policy_id: 'refund-standard', instruction: 'Explain the refund decision.' }
          : { order_age_days: 21, refund_window_days: 14, eligible: false, instruction: 'Explain the eligibility result.' },
        { eligible: true, decision: 'approved', message: 'Your refund request is eligible and has been approved.' });
      span('record', 'agent', 'record-decision', 'state', scenario === 'multi' ? 4140 : 3090, 54,
        { order_id: order, decision: 'approved' }, { recorded: true });
    }
    const name = scenario === 'multi' ? 'refund-policy-review' : scenario === 'reasoning' ? 'refund-eligibility-check' : 'order-status-lookup';
    spans[0].name = name;
    const run = { number, name, service:'refund-agent', label: `R-${number}`, traceId: traceId(number), scenario, order, started, duration, spans,
      status: 'Completed', completeness: variant === 'partial' ? 'Partial' : 'Complete',
      analysis: variant === 'analysis-failed' ? 'Failed' : 'Completed',
      findings: scenario === 'retry' ? 0 : 1, recordedErrors: scenario === 'retry' ? 1 : 0, recovered:scenario === 'retry',
      attempt: `analysis-${number}-1`, snapshot: `snap-${number}-a`,
      selected: scenario === 'retry' ? 'a1' : 'compose', variant };
    if (variant === 'partial') {
      run.quality = 'Parent span unavailable for load-cached-policy. Hierarchy is incomplete.';
      spans.find(s => s.key === 'cache').parent = 'unavailable-parent';
    }
    if (variant === 'analysis-failed') { run.findings = null; run.analysisError = 'Investigation could not be completed. Trace data remains available.'; }
    if (variant === 'failed-run') {
      run.status = 'Failed'; run.duration = 1428; run.findings = null; run.analysis = 'Failed';
      run.spans = spans.filter(s => !['a2','api2','compose','record'].includes(s.key));
      Object.assign(run.spans[0], {duration:1428, status:'ERROR', output:null, outputReason:'Run ended after an unrecovered timeout', errorOwner:'a1'});
      run.spans.find(s => s.key === 'agent').duration = 1419;
      run.spans.find(s => s.key === 'lookup').duration = 1220;
      run.spans.find(s => s.key === 'lookup').output = null;
      run.spans.find(s => s.key === 'lookup').outputReason = 'Not produced — lookup failed';
    }
    return run;
  }
  // These authored shapes borrow workload domains from examples/* README files.
  // They are not emitted traces, scenario test results, or SDK integration claims.
  function workload(number, kind, started, variant = '') {
    const service = {rag:'novacloud-rag',research:'meridian-research',tool:'fulfillment-agent'}[kind];
    const name = kind === 'rag' ? number === 1039 ? 'workspace-recovery-answer' : 'plan-change-policy-answer' : kind === 'research' ? 'field-station-research-brief' : variant === 'failed' ? 'inventory-availability-check' : 'order-fulfillment-validation';
    const duration = kind === 'research' ? 8440 : kind === 'rag' ? number === 1039 ? 6812 : 5106 : variant === 'failed' ? 1428 : 3872;
    const spans = [];
    const add = (key,parent,name,type,start,duration,input,output,extra={}) => {
      const item={key,parent,name,type,start,duration,input,output,status:'OK',...extra,id:id(number,spans.length+1),
        attributes:{'service.name':service,'deployment.environment':'development','debugger.operation.type':type,...extra.attributes}};
      spans.push(item); return item;
    };
    const question = kind === 'research' ? 'Compare Ridge and Vale for 40 people, 10 kW, a daily budget of 1,000 credits, open access and an approved permit as of 2026-06-01.' : kind === 'rag' ? number === 1039 ? 'How long can a deleted workspace be restored?' : 'When does a downgrade take effect?' : `Check order ORD-${number} before fulfillment.`;
    add('root',null,name,'run',0,duration,{request:question},{status:variant==='failed'?'failed':'completed'},variant==='failed'?{status:'ERROR'}:{});
    add('agent','root',service,'agent',8,duration-24,{task:question},{completed:variant!=='failed'});
    add('plan','agent','plan-request','model',24,kind==='research'?810:310,{messages:[{role:'user',content:question}]},{steps:kind==='tool'?['check_inventory','validate_state']:['retrieve_evidence','assess','respond']});
    if(kind==='rag') {
      const content=number===1039?'Deleted workspaces can be restored during the documented retention period.':'A downgrade takes effect at the start of the next billing cycle.';
      add('retrieve','agent','retrieve-knowledge','retrieval',380,1024,{query:question},{documents:[{id:number===1039?'KB-01':'KB-05',title:number===1039?'Workspace deletion':'Plan changes',excerpt:content}]});
      add('cache',variant==='partial'?'unavailable-parent':'retrieve','load-local-passage','tool',412,276,{document_id:number===1039?'KB-01':'KB-05'},{excerpt:content});
      add('compose','agent','generate-answer','model',1460,duration-1630,{messages:[{role:'system',content:'Answer only from the supplied knowledge passage.'},{role:'user',content:question}],context:content},{message:content});
      add('record','agent','validate-citations','state',duration-120,64,{document_ids:[number===1039?'KB-01':'KB-05']},{recorded:true});
    } else if(kind==='research') {
      add('collect','agent','collect-station-evidence','retrieval',880,1180,{stations:['Ridge','Vale'],as_of:'2026-06-01'},{documents:[{id:'RIDGE-CURRENT',title:'Ridge station',excerpt:'Capacity 48; power 12 kW; daily cost 960 credits; open access; approved permit.'},{id:'VALE-CURRENT',title:'Vale station',excerpt:'Capacity 52; power 14 kW; daily cost 1,080 credits; open access; approved permit.'}]});
      add('load','collect','load-evidence-records','tool',912,620,{record_ids:['RIDGE-CURRENT','VALE-CURRENT']},{loaded:2});
      const paragraphs=[
        'Recommendation\nRidge is the eligible choice in this captured comparison. It supports the requested group of 40, meets the 10 kW power requirement, permits open access and has an approved permit as of 1 June 2026. Its recorded daily cost is 960 credits, within the requested 1,000-credit limit. Vale meets the capacity and power constraints but exceeds that daily budget.',
        'Evidence used\nRIDGE-CURRENT records a capacity of 48 people and 12 kW of power. VALE-CURRENT records 52 people and 14 kW. Both records identify open access and an approved permit. The recommendation uses these supplied records; it does not assume that a missing constraint is satisfied or infer a permit from a station name.',
        'Budget comparison\nRidge leaves 40 credits of daily budget headroom. Vale costs 1,080 credits per day, exceeding the stated limit by 80 credits. The comparison is limited to the recorded daily station charge. Transport, equipment rental, meals and any one-time fees are not present in these records and are not included in that headroom.',
        'Capacity and power\nThe requested group is smaller than each recorded capacity. Ridge has room for eight additional people and two additional kilowatts relative to the minimum request. These differences are descriptive checks against the supplied constraints; they are not a prediction of actual operational load or a substitute for checking equipment requirements.',
        'Date and access scope\nThe request asks for a decision as of 1 June 2026. The supplied records are marked current for that comparison and both list approved permits. No later policy revision, reservation calendar or access exception is included. Before booking, the operator should obtain the applicable current records and confirm that the intended activity is covered.',
        'Decision boundaries\nThis recommendation is conditional on the supplied evidence and the stated constraints. If the budget changes, if additional fees apply, or if a station record is superseded, repeat the comparison against the relevant records. Do not silently replace the analyzed values while reviewing this captured response.',
        'Suggested next check\nConfirm availability for the intended dates and request an itemized quote. Keep the quote and the applicable permit record with the eventual decision. Those sources were not supplied to this execution; the response cannot confirm their contents or treat an unrecorded check as completed.'
      ];
      add('compose','agent','synthesize-research-brief','model',2180,5880,{messages:[{role:'system',content:'Compare only the supplied station records. State missing information and preserve the requested as-of date. Do not infer access, permits or prices.'},{role:'user',content:question+' Explain the budget, capacity, power and evidence limitations in a detailed report.'}],evidence_ids:['RIDGE-CURRENT','VALE-CURRENT']},{message:paragraphs.join('\n\n')});
      add('record','agent','validate-support','state',8120,204,{source_ids:['RIDGE-CURRENT','VALE-CURRENT']},{supported:true});
    } else {
      add('lookup','agent','check-inventory','tool',380,variant==='failed'?1000:480,{order_id:`ORD-${number}`,sku:'KIT-04',quantity:2},variant==='failed'?null:{available:12,reserved:2},variant==='failed'?{status:'ERROR',errorType:'TimeoutError',error:'Inventory source did not respond within 1,000 ms.',outputReason:'Not produced — lookup timed out'}:{});
      if(variant!=='failed') {
        add('validate','agent','validate-fulfillment-state','state',940,184,{inventory_reserved:true,payment_recorded:true},{ready_to_ship:true});
        add('compose','agent','compose-fulfillment-summary','model',1180,2520,{order_id:`ORD-${number}`,ready_to_ship:true},{message:'Inventory and payment preconditions are recorded. The order is ready for the shipping step; no shipment is claimed here.'});
      }
    }
    return {number,label:`R-${number}`,name,service,traceId:traceId(number),scenario:kind,started,duration,spans,status:variant==='failed'?'Failed':'Completed',completeness:variant==='partial'?'Partial':'Complete',analysis:variant==='failed'?'Failed':kind==='research'?'Not requested':'Completed',findings:variant==='failed'||kind==='research'?null:0,recordedErrors:variant==='failed'?1:0,attempt:`analysis-${number}-1`,snapshot:`snap-${number}-a`,selected:variant==='failed'?'lookup':'compose',variant,quality:variant==='partial'?'Parent span unavailable for load-local-passage. Hierarchy is incomplete.':null};
  }
  const runs = [
    build(1042, 'multi', '10:42:18'), build(1041, 'reasoning', '10:39:04'),
    build(1040, 'retry', '10:36:52'), workload(1039,'rag','10:31:27','partial'),
    workload(1038,'tool','10:26:10','failed'), workload(1037,'rag','10:20:43'),
    workload(1036,'research','10:14:06'), workload(1035,'tool','10:09:11')
  ];
  const authority = {
    id: 'policy-refunds-v7', title: 'Refund policy', version: 'Revision 7', effective: '2026-10-01',
    passage: '§ 2.1 · Standard refund window',
    text: 'Customers may request a refund within 14 days of delivery. Requests outside this window require a documented exception approved by the support lead.',
    context: 'Applies to standard retail orders. Subscription renewals and damaged goods are covered by separate policies.'
  };
  export { runs as authoredTraces, authority };
