# Competitive UX evidence register

Research date: 14 October 2026 (Asia/Calcutta).
Scope: frontend research only for the original AI Agent Debugger repository. No implementation or competitor account changes.

Legend: O = live UI interaction observed; V = official static image visually inspected; D = official documentation claim; I = researcher interpretation. A screenshot of documentation is V, not proof of a working interaction. Historical articles do not establish current product behavior.

## Sources and captures

| Reference | Exact source | Capture files | Evidence |
|---|---|---|---|
| LangSmith requested walkthrough | https://blog.langchain.com/debugging-deep-agents-with-langsmith/ redirects to https://www.langchain.com/blog/debugging-deep-agents-with-langsmith | Read article; no live trace in this source | D |
| LangSmith current view docs | https://docs.langchain.com/langsmith/view-traces | Trajectory, Turns, Details claims read | D |
| LangSmith official trace image | https://docs.langchain.com/langsmith/observability-quickstart | [LS-02-official-trace.jpg](LS-02-official-trace.jpg) | V |
| LangSmith image asset | https://mintcdn.com/langchain-5e9cc07a/EKYgNtnIIDPnseTv/langsmith/images/trace-quickstart-app-dark.png?w=1100&fit=max&auto=format&n=EKYgNtnIIDPnseTv&q=85&s=edffd1edd338957519ccc4e423bf0945 | [LS-02-official-trace.jpg](LS-02-official-trace.jpg) | V |
| LangSmith signed-in empty workspace | https://apac.smith.langchain.com/o/e4ef9935-0519-49dc-9fdc-6344b5d44569/a/-/projects | [LS-01-empty-onboarding.jpg](LS-01-empty-onboarding.jpg) | O: Tracing showed no agents; Connect an agent opened a creation modal, cancelled without creating |
| Langfuse requested changelog | https://langfuse.com/changelog/2025-03-19-new-trace-view | Historical tree/timeline, customization and search claims | D |
| Langfuse demo entry | https://langfuse.com/docs/demo | Shared read-only project accessed; no requests generated | D + O |
| Langfuse explorer | https://cloud.langfuse.com/project/clkpwwm0m000gmm094odg11gi/traces | LF-01-explorer.jpg (capture removed during cleanup) | O |
| Langfuse selected trace | https://cloud.langfuse.com/project/clkpwwm0m000gmm094odg11gi/traces/8f9d29585229f964c312543def6f88fc | LF-02-tree.jpg (capture removed during cleanup), LF-03-timeline.jpg (capture removed during cleanup), LF-04-model-inspector.jpg (capture removed during cleanup), LF-05-search-raw.jpg (capture removed during cleanup) | O: tree/timeline switching, child selection, formatted/raw switching, name search |
| Phoenix requested tracing entry | https://arize.com/docs/phoenix/tracing redirects to https://arize.com/docs/phoenix/tracing/tutorial | Tutorial read | D |
| Phoenix first-traces tutorial | https://arize.com/docs/phoenix/tracing/tutorial/your-first-traces | Model, tool, retrieval inspection claims read | D |
| Phoenix demo broken deep link | https://phoenix-demo.arize.com/playground/spans/U3Bhbjo3MTUz | PX-00-demo-error.jpg (capture removed during cleanup) | O: application error at a stale deep link, not an agent execution error |
| Phoenix empty time-filtered project | https://phoenix-demo.arize.com/projects/UHJvamVjdDoy/spans?timeRangeKey=7d | PX-01-empty-filter.jpg (capture removed during cleanup) | O: no matching traces; widening to Last Month revealed data |
| Phoenix trace | https://phoenix-demo.arize.com/projects/UHJvamVjdDoy/spans/614db9582566a1036c626deb534959b8?timeRangeKey=30d&selectedSpanNodeId=U3Bhbjo0MzcwOA%3D%3D | PX-02-trace-inspector.jpg (capture removed during cleanup) | O |
| Phoenix selected child | https://phoenix-demo.arize.com/projects/UHJvamVjdDoy/spans/614db9582566a1036c626deb534959b8?timeRangeKey=30d | PX-03-attributes.jpg (capture removed during cleanup), PX-04-no-events.jpg (capture removed during cleanup) | O: router_call selection, Attributes table, Events 0 and No events for this span |
| Sentry requested agent documentation | https://docs.sentry.io/product/dashboards/sentry-dashboards/ai/agents/ | [SE-01-ai-spans-official.jpg](SE-01-ai-spans-official.jpg), [SE-02-full-waterfall-official.jpg](SE-02-full-waterfall-official.jpg) | D + V; read in browser because web text fetch failed |
| Sentry AI Spans image | https://docs.sentry.io/mdx-images/agent-ai-spans-view-IZSKOKCY.png | [SE-01-ai-spans-official.jpg](SE-01-ai-spans-official.jpg) | V |
| Sentry full waterfall image | https://docs.sentry.io/mdx-images/agent-detailed-trace-view-LLY3AZUS.png | [SE-02-full-waterfall-official.jpg](SE-02-full-waterfall-official.jpg) | V |
| Sentry sandbox | https://sandbox.sentry.io/ | No saved capture | O: email and terms gate; not submitted |
| Linear requested redesign | https://linear.app/now/how-we-redesigned-the-linear-ui | [LI-01-official-ui.jpg](LI-01-official-ui.jpg), [LI-02-inverted-l-official.jpg](LI-02-inverted-l-official.jpg) | D + V; March 2024 reference, not a live account |
| Linear hero asset | https://webassets.linear.app/images/ornj730p/production/900ab5bbf41d4245dcd32122b80ed523c5a00e2f-2352x1344.png?auto=format&dpr=2&q=95 | [LI-01-official-ui.jpg](LI-01-official-ui.jpg) | V: perspective/fade illustration, unsuitable for contrast measurement |
| Linear chrome diagram | https://webassets.linear.app/images/ornj730p/production/73b5bcd3d1d73d0b15322d5cbb57c0aae7ff7b5f-2352x1380.png?auto=format&dpr=2&q=95 | [LI-02-inverted-l-official.jpg](LI-02-inverted-l-official.jpg) | V: annotated navigation image; tinted overlays are explanatory |
| Vercel requested redesign | https://vercel.com/changelog/dashboard-navigation-redesign-rollout | [VE-01-official-navigation.jpg](VE-01-official-navigation.jpg) | D + V; February 2026 reference, not a live account |
| Vercel screenshot asset | https://assets.vercel.com/image/upload/contentful/image/e5382hct74si/2Y43YuHnMCvnuYMC3VCvWX/9a16131f4a4a06532246b10258b43cff/Dash_-_Light__2_.png | [VE-01-official-navigation.jpg](VE-01-official-navigation.jpg) | V |

## Measurements and limitations

- Langfuse sampled viewport: 870 x 668 CSS pixels. Navigation panel: 268 x 503; preview: 418 x 503. This is one current panel configuration, not a universal default. Sampled Preview tab: system sans-serif, 13px, 13px line-height.
- Phoenix sampled screenshot viewport: 1280 x 720. Detail drawer measured 512 x 674 CSS pixels (40 percent of width); inner tree splitter reported 30 percent. Sampled Info tab: Geist sans-serif, 14px, 20px line-height.
- Official screenshots support placement and visual hierarchy, not CSS dimensions or live interaction behavior.
- A temporary browser viewport override was reset after research. Screenshots were captured at different viewport sizes and are not a controlled performance comparison.
- No large-trace benchmark, keyboard accessibility audit, screen-reader audit, partial-trace experiment, ingestion failure test, recovered retry evaluation, or analysis workflow was run in competitors.
- LangSmith signed-in workspace had no recorded traces. Populated trace layout was inspected only in its official image.
- Phoenix widening the time range revealed 120 traces in the project. This is an explorer result count, not 120 spans in the selected trace.

## Local project evidence

Read current docs/HLD.md, docs/PRD.md, docs/LLD.md and docs/trace-protocol.md; inspected docs/analysis-engine.md for frontend-relevant evidence/snapshot states. Frontend App, routes, pages and API helper files are empty. main.jsx imports absent src/index.css and src/App.jsx. Relevant backend read/reconstruction/analysis scaffold files are empty. SDK README and public constructor inspection confirm console export; endpoint/api_key parameters, HTTP export and batching are not currently implemented. These are source-review findings; no application run or build was performed.

All JPG files are actual browser captures, preserved alongside this register under `docs/frontend/research/` on 15 October for portability. Capture filenames in the table resolve within this directory. This is the historical 14 October research record, not a claim of new live verification. Recommendations are proposals, not observed product requirements; the current design requirements are in [design-spec.md](../design-spec.md).

## Independent Langfuse recheck — 15 October 2026

| Exact reference | Verified evidence / boundary |
|---|---|
| https://langfuse.com/images/docs/tracing-overview.png | V: selected-operation identity and stacked input/output in the official 2048×1270 image; visible browser capture (capture removed during cleanup). The browser fitted the image to its viewport. Exact image release/version marker not independently verified; no CSS measurements inferred. |
| https://langfuse.com/docs/observability/overview | D: nested observations, timing, input/output and metadata. Reopened through web access. |
| https://langfuse.com/changelog/2025-03-19-new-trace-view | D: tree/timeline parity, search and display settings; historical announcement, not proof of present implementation. |
| https://langfuse.com/changelog/2026-08-28-responsive-timeline | D: overview/zoom/Fit; article accessible and dated 28 August 2026. No large-trace performance benchmark performed. |
| https://langfuse.com/docs/observability/features/agent-graphs | D: aggregated/expanded modes; the page also describes inferred graphs from timing/nesting. That inference is not compatible with our recorded-only relationship rule and is not adopted. No live graph interaction tested. |
| https://langfuse.com/docs/demo | D: accessible shared-project entry. No chat, voice, image or other demo generation was invoked. |
| https://cloud.langfuse.com/project/clkpwwm0m000gmm094odg11gi/traces/8f9d29585229f964c312543def6f88fc | O: workspace showed v4.59.0 before collapsing navigation; selected `chat`, switched Formatted → Raw → Timeline, with the same generation still selected. Formatted model (capture removed during cleanup), Timeline/Raw (capture removed during cleanup). Navigation restored afterward. One Raw tab measured 12 px font / 12 px line height, system sans-serif; not a full type audit. |

Three captures above supplement the original 17. Official-image and live-demo evidence were compared with the prior local mockups before the P0/P1 refinement. No competitor accessibility, retry-correctness or scale claims are established by this check.
