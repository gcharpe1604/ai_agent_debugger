# Milestone 3.1 — focused correctness repairs

Scope: frontend presentation and fixture adapters only. Existing uncommitted work was preserved; no backend, SDK, authentication, API contracts, packages or investigator logic changed.

## Repairs

- **Non-modal inspector focus:** overlay-mode toolbar/context/footer controls use the unobscured explorer area. Focusing any remaining occluded explorer control dismisses the overlay without redirecting focus. The full-width tree remains navigable; no modal focus trap was added.
- **Stale attempt recovery:** the recovery action explicitly opens the latest attempt supplied by the adapter, including its finding and initial citation pair. It no longer reuses a cached earlier attempt.
- **Lifecycle/history:** Running has an explicit presentation. Earlier supplied completed attempts with findings remain reachable when a newer attempt fails, runs or waits. This does not simulate investigation requests.
- **Zero projects:** an empty project list renders a useful empty state and disabled project selection instead of dereferencing the first project.
- **Captured empty values:** readable `{}` and `[]` remain visible captured values. An unresolved citation cannot accidentally highlight a property named like the former internal sentinel.
- **Unknown counts:** missing/unknown child and trace totals remain unknown. Known but unloaded children remain distinct from loaded children; activation explains that additional child reads are not connected.
- **Unexpected shapes:** malformed message entries fall back to inert structured rendering. A route read boundary provides a focused, generic failure state with retry and return navigation instead of exposing an exception or crashing the entire shell.

## Verification

The regression run before repair reproduced **12 failures**, with the existing Pending presentation already passing. The focused repaired run passed. A subsequent regression also confirmed that the existing Running query filter works; no filter implementation change was needed.

| Check | Result |
| --- | --- |
| Full frontend suite | **118 passed, 0 failed; 13 test files** |
| `npm.cmd run lint` | Exit 0 |
| `npm.cmd run build` | Exit 0; final JS bundle `index-DvXfee7j.js` |
| Scoped `git diff --check -- frontend` | Exit 0; existing LF/CRLF notices only |

The full suite was followed only by adding the stable `dispatch` callback dependency required by lint. Lint and production build ran after that adjustment. No dependencies were installed.

### Browser checks

At **1280×800** and **1440×900**, native keyboard traversal exercised explorer controls and inspector controls with the overlay open. Forward traversal covered 11 focus steps at each size; reverse traversal covered five steps at 1440×900. Toolbar/filter focus remained visible. No modal trap was introduced.

The background tree intentionally remains full-width: its client width was **1031 px** at 1280 and **1191 px** at 1440. Its geometric center can lie beneath the overlay; its left-side operation/focus area remains available. The repair moves compact controls, not execution rows or the timing axis.

Direct span switching, Tree→Timeline switching, Pin and Unpin preserved selection and context. Final-bundle checks confirmed visible filter focus at both sizes. Both screenshots below were inspected at native resolution.

- [1440×900 overlay keyboard focus](overlay-keyboard-1440x900.png)
- [1280×800 overlay keyboard focus](overlay-keyboard-1280x800.png)
- [Keyboard observations](keyboard.json)

On the final production bundle, navigating from earlier `analysis-1042-0` to a deleted attempt and choosing **Open latest supplied attempt** opened `analysis-1042-1` and finding `F-01` with retrieval/document citations. See [recovery observations](recovery.json).

Test evidence: [before repair](before-tests.json), [focused repaired run](focused-tests.json), [full suite](tests.json).

## Files changed for this repair

- `src/app/App.jsx`
- `src/app/Repairs.test.jsx` (new; 14 regression cases)
- `src/components/AppShell.jsx`
- `src/components/ReadBoundary.jsx` (new)
- `src/features/trace/TraceWorkspace.jsx`
- `src/features/trace/ExecutionTree.jsx`
- `src/features/trace/treeModel.js`
- `src/features/trace/Payload.jsx`
- `src/features/trace/trace.css`
- `src/features/evidence/InvestigationControl.jsx`
- `src/features/evidence/EvidencePage.jsx`
- `src/features/evidence/CapturedEvidence.jsx`
- This verification directory.

## Remaining limitations

- Data remains fixture-backed. Latest-attempt order comes from the adapter; the UI does not infer it from timestamps or identifiers.
- Unknown/unloaded children are not fetched. No backend pagination or lifecycle guarantee was invented.
- The read boundary and structured fallback contain unexpected shapes; they are not comprehensive external-schema validation or payload-size enforcement.
- Browser focus checks are targeted evidence, not screen-reader, zoom/reflow or full accessibility conformance certification.
- Existing frontend features retain their previous integration boundaries. No extra product features were added during this repair.
