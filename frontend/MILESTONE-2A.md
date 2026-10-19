# Milestone 2A · execution tree and inspector

Approved scope: implement the current compact Trace Detail in React, retaining Milestone 1. No Timeline, Evidence Focus, investigation actions, authentication, HTTP contracts or dependency additions.

- [x] Test and implement normalized fixture reads, recorded hierarchy, ancestor-preserving filters, stable visible-row windows and anchor restoration. Reuse the study's authored execution data; keep payloads outside structural records.
- [x] Connect scoped Run routes and return query context. Implement a full-width, keyboard-navigable, windowed tree, loaded-only search/filters, explicit reveal/restore and progressive local structure loading.
- [x] Test and implement non-modal overlay, explicit persistent pin/width preference, pointer/keyboard/range resizing and responsive single-pane fallback. Keep the explorer mounted and stable.
- [x] Add bounded asynchronous span detail reads, stale-response isolation, Content/Attributes/Events/Errors, captured-value markers and recorded-only retry navigation.
- [x] Run the complete frontend tests, lint and build. Inspect both themes at 1440×900 / 1280×800, exercise 100/1,000/2,100 fixtures, record local measurements and preserve protected work.

UI context is scoped by project and Run, cached separately from fixture records during navigation. URLs retain Run Explorer query context and identify selected spans. Presentation preferences contain mode/width only, with no payloads or authorization state. Synthetic large traces and local loading are explicitly fixture studies, not server pagination or production-performance evidence.
