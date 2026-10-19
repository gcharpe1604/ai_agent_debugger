# Milestone 4A — account/access presentation and projects

## Signup usability refinement — 17 October 2026

Added a compact two-step indicator with current/completed semantics, step-aware document titles and the selected email on the credentials step. Removed ambiguous sign-in-method wording and disabled email capitalization/spellcheck. Registration now keeps its heading in a fixed position across steps and uses less vertical padding; other account/project compositions are unchanged. The user-requested checkbox and backend-only authentication boundaries remain intact.

Focused verification: all **13 access/project tests passed** (including added title, step semantics and selected-email assertions); scoped ESLint passed. Browser inspection of Light 1280 × 800 and Dark 390 × 844 confirmed legible fields/actions, visible disclosure and no document overflow in the ordinary credentials state. At 1280 × 800 both registration headings measured **96 px** from the viewport top after Back/Continue. Error messages and unusually long text may require vertical scrolling. This is visual inspection and component coverage, not screen-reader certification or backend integration.

New captures: [Light desktop](verification/milestone-4A-polish/signup-refined-light-desktop.png), [Dark mobile](verification/milestone-4A-polish/signup-refined-dark-mobile.png). Changes are limited to `AccountPage.jsx`, shared account CSS (registration selectors and email handling), existing `Access.test.jsx`, this report, the existing [research record](verification/milestone-4A-polish/research.md) and design-spec clarification. No project/debugger logic changed. The production build passed after the final padding adjustment (64 modules). A repository-wide whitespace check also surfaced pre-existing trailing whitespace in `sdk/python/src/ai_agent_debugger_sdk/models.py:1`; it was left untouched.

## Signup flow update — 17 October 2026

At the user's request, registration now starts with **Name and Email**, followed by **Continue**. Step two shows **Username, Password, Confirm password**, a required **Terms and Conditions** checkbox, **Back**, and **Create account**. The same polished form, coordinated themes, explicit labels, keyboard focus and password visibility controls are retained. The two password controls have independent visibility states.

Continue performs only presentation validation and never calls registration. Step two checks required values, password confirmation and the checkbox before calling the disconnected/injected form adapter. Back retains name/email/username and clears passwords, visibility and agreement. Submission clears both password fields; no fulfilled adapter response is trusted as a session. Username availability, account creation and password verification remain backend-owned. Added name/username values are transient in-process form inputs, not an approved FastAPI schema.

The user explicitly requested a plain checkbox because terms content does not yet exist. No terms link or legal text was invented, and the footer discloses unpublished terms. This is a preview control, not a record of published terms acceptance.

Changed: `src/features/access/AccountPage.jsx`, `access.css`, existing `src/app/Access.test.jsx`, and the design-spec clarification. Focused verification: 12/13 access/project cases passed on the first repaired run; one older cancellation test assumed registration still displayed Password immediately. After changing that assertion to confirm its absence in step one, that case passed on its own. All 13 cases therefore have passing results across those runs. Scoped lint and production build passed; no full debugger-suite rerun was needed for the isolated form change. Final build: `index-DqrAJZ7S.js`.

Browser review: [step one, light desktop](verification/milestone-4A-polish/signup-step1-light-desktop.png), [step two, dark mobile](verification/milestone-4A-polish/signup-step2-dark-mobile.png). Verified focus transfer to Username and no horizontal overflow at 390 px. Desktop form remains 384 px at a 1280 px viewport. Registration captures below predate this two-step update.

---

**17 October visual refinement:** the research, presentation changes and checks below supersede the earlier visual captures. Functional/backend boundaries remain unchanged. [Research with exact sources and reference captures](verification/milestone-4A-polish/research.md).

## Visual refinement — 17 October 2026

- Login/Register now use a shared, centered 384 px column with a quiet header, 28 px desktop heading, aligned 42 px fields/actions and 44 px mobile form targets. Password visibility is an inset icon with an explicit accessible name, controlled-field association, pressed state and visible focus; it is disabled during submission.
- Removed backend implementation explanations from descriptions and normal action labels. A small footer still states authentication is disconnected. Disconnected submission remains an explicit failure and never creates a session. Project notices still say changes reset and confer no ownership/access.
- Expired/denied views share account proportions and a small status glyph, concise explanation, one primary recovery action and secondary sample navigation.
- Project creation/settings use a bounded General/details section, separated read-only ID, local action footer and reserved status line. Empty project entries share the same first-project experience instead of diverging between routes. No new settings capabilities or account methods were added.
- Existing semantic colors, sidebar, scoped caches and debugging workspaces were preserved. Decorative branding panels, region/provider choices, recovery flows and competitor settings inventories were not adopted.

Research: current public Login/Sign Up screens for Langfuse, LangSmith, Linear and Vercel; live Langfuse General settings; an official Linear settings image; official LangSmith/Vercel settings documentation. Observation, documentation and synthesis are distinguished in the linked research. Authenticated settings in the other products were not accessed.

Representative actual-browser captures (1280×800 desktop; 390×844 mobile): [light Login](verification/milestone-4A-polish/login-light-desktop.png), [dark Register](verification/milestone-4A-polish/register-dark-desktop.png), [mobile Register validation](verification/milestone-4A-polish/register-dark-mobile.png), [dark Settings](verification/milestone-4A-polish/settings-dark-desktop.png), [mobile Create Project](verification/milestone-4A-polish/create-light-mobile.png), [light Empty Workspace](verification/milestone-4A-polish/empty-light-desktop.png), [mobile Access Denied](verification/milestone-4A-polish/denied-dark-mobile.png). All seven screen types were reviewed in both themes; remaining opposite-theme views were inspected without saving another matrix. [Browser observations](verification/milestone-4A-polish/browser-review.json) record viewport overflow checks, including 320 px account reflow. These do not establish screen-reader or full accessibility conformance.

Verification was proportionate to the shared App change: one full frontend run produced **129 passing tests and one failing test** whose synchronous lookup assumed the zero-project action preceded loading. That test now awaits the action. The focused account/project rerun passed **12/12**; the other **118 tests** passed in the full run and their implementation was not subsequently changed. See [full run](verification/milestone-4A-polish/tests.json) and [focused rerun](verification/milestone-4A-polish/access-tests.json). Lint and production build each passed once; final build `index-DEltAsYL.js`, 337.02 kB / 102.63 kB gzip, CSS 48.16 kB. Only the asynchronous test lookup changed afterward; no production-code repair or repeated full-suite/build was needed.

Changed production files for this refinement: `src/app/App.jsx`, `src/features/access/AccountPage.jsx`, `AccessState.jsx`, `ProjectsPage.jsx`, `access.css`, and `src/components/Icon.jsx`. Updated existing assertions in `src/app/Access.test.jsx` and `Repairs.test.jsx`; no new test suite/dependency. Documentation: this report, the targeted design-spec clarification, and `verification/milestone-4A-polish/`. The isolated `empty-workspace.html`/`.jsx` harness mounts the actual App with an empty fixture project list; it is outside the production entry and does not introduce an access/route flag.

Remaining integration limits: FastAPI authentication/session/authorization and durable project ownership remain disconnected. No backend routes, password policy, recovery, provider login, registration completion or new project-access contract is implied. No backend/SDK/investigator changes, installs, commits or pushes.

---

## Earlier implementation record — 16 October 2026

Reviewed and completed 16 October 2026. The account/project implementation was already present in the working tree at the start of this continuation and was preserved. This milestone provides presentation and local project workflows. It does **not** provide authentication, authorization or persistent project ownership.

## Delivered

- `#/account/login` and `#/account/register`: compact 384 px forms using existing semantic themes; visible labels, autocomplete, password visibility, required/email-format assistance, focused invalid fields, duplicate-submit protection, busy announcements and safe request-failure feedback. Passwords are cleared after submission and requests can be cancelled on unmount. Switching forms unmounts their transient state.
- `#/account/session-expired` and `#/account/access-denied`: distinct, focused explanations and safe navigation. Project reads/mutations can present equivalent expired/forbidden states. Private exception messages are not displayed.
- `#/projects`: project chooser with loading, zero-project, failed, forbidden and expired states. Zero-project entry also works at the existing Runs URL.
- `#/projects/new`: fixture creation with project-name validation, busy/error state and automatic navigation to the new project's empty Runs view.
- `#/projects/:id/settings`: sample name editing and stable, readable project identity; ownership is explicitly disconnected. No deletion, roles, credential management or SDK setup is introduced.
- Request failures use a general alert separate from project-name validation. Valid names remain editable and the same action can retry without marking the field invalid. Busy messages distinguish creation from saving.
- Account pages reuse the debugger operation mark, semantic tokens and theme utility, with a keyboard skip link. Mobile form controls use 44 px targets; project forms retain horizontal padding and the account header wraps at 320 px. Primary solid buttons retain readable foreground/background colors on hover.
- Sidebar project selection, Projects and Settings navigation; unsupported SDK Setup control removed. Changing projects opens that project's Runs without prior span/filter parameters. Project workspaces own their trace/evidence caches, retaining them during Trace↔Evidence navigation and discarding them on project/access transitions.

Project creation uses a dedicated compact page rather than the specification's suggested dialog. This supports direct navigation and small screens without introducing another modal interaction. Existing debugging workspaces and their layout are unchanged.

## Implemented versus simulated

Account forms call an injectable **in-process view adapter**. The default `disconnectedAccount` rejects sign-in/registration without a network request. A fulfilled injected call is deliberately **not** interpreted as sign-in or registration completion: the interface reports that session confirmation is not connected. No successful session, account or token is synthesized.

Project list/create/update use `createFixtureProjects(seed)`, an in-memory adapter initialized per App. Changes survive workspace navigation in that app, and reset on reload. A newly created fixture project returns an empty local run query; it does not emit or fabricate telemetry. Existing fixture run/trace/evidence repositories remain intact.

Fixture identity and project selectors are not access control. React does not persist passwords, tokens, API keys, sessions or project ownership. Only existing non-sensitive appearance/layout preferences use browser storage. Sample debugging routes remain usable without authentication.

## Adapter and integration boundary

These methods are frontend dependencies, **not endpoint definitions or approved wire schemas**:

| Adapter | Local seam | Current behavior |
| --- | --- | --- |
| Account | `signIn`, `register` | Receive transient form values and cancellation signal; disconnected by default. Responses grant no access. |
| Account | `readSession`, `signOut` | Reserved disconnected seams: session unavailable, revocation rejected. No polling, authenticated navigation or sign-out control is enabled yet. |
| Projects | `listProjects`, `createProject`, `updateProject` | Fixture list/identity mutations; cancellation and stale-read protection. |

The optional adapter failure categories `expired`, `forbidden`, `unavailable` and `disconnected` are local presentation classifications. A future integration must map approved FastAPI results to them. Raw exception text is not a user-facing contract. The 100-character name limit is explicitly sample-form validation, not a backend project rule.

FastAPI still needs to settle and implement authentication endpoints, password policy, registration completion, session transport/validation/expiry, logout/revocation, safe validation responses and authorized return navigation. Session confirmation cannot be completed merely by replacing the two form methods. Project creation/update permissions, persistent ownership, server validation, identifiers and authorized reads also require approved integration.

Protected production reads must be withheld and caches invalidated on backend-confirmed expiry or denial. Account/access routes currently unmount rendered project workspaces, but that fixture presentation is not a complete connected-session lifecycle. Sample adapters contain public authored data and remain deliberately independent of account availability.

## Verification in this continuation

- The focused access/project run reproduced **one request-failure defect**: a transport failure marked a valid project name `aria-invalid=true`. The added retry regression passed after separating field and general errors. A second added test confirmed pending account cancellation, dropped credentials and no stale success on switching forms; that behavior already worked.
- Full frontend suite: **130 passed, 0 failed, 14 files** ([JSON result](verification/milestone-4A/tests.json)). The access/project file has 12 cases covering validation/password visibility, safe failures, duplicate-submit state, no automatic sign-in, expiry/external-return rejection, zero-project creation, editing/switching, distinct project-read failures, stale-read cancellation, request retry and account cancellation. Existing Runs/Tree/Timeline/Inspector/Evidence tests passed.
- `npm.cmd run lint`: exit 0, no warnings.
- `npm.cmd run build`: exit 0; 64 modules, final JS `index-C9_vFCPt.js` (336.36 kB; 102.37 kB gzip), CSS 44.54 kB. The full suite and lint preceded only mobile/hover CSS corrections; the production build ran after those corrections. No redundant behavioral-suite rerun was needed.
- Browser: production preview at `127.0.0.1:5174`. Created a local project, opened its empty Runs, edited its name and observed fixture-save feedback. Switching projects opened Sandbox Runs without previous selection parameters. Sample Runs remained available from Session Expired; validation focused Email and expiry focused its heading. Temporary viewport overrides were reset. See [observations](verification/milestone-4A/browser-review.json).

Each core new screen was visually inspected in both themes, distributing desktop/mobile coverage rather than taking a full size/theme matrix:

| Screen | Light | Dark |
| --- | --- | --- |
| Login | [1440×900, validation/focus](verification/milestone-4A/login-light-final-1440x900.png) | [390×844, validation/focus](verification/milestone-4A/login-dark-final-390x844.png) |
| Register | [390×844](verification/milestone-4A/register-light-final-390x844.png) | [1440×900](verification/milestone-4A/register-dark-final-1440x900.png) |
| Create project | [1280×800](verification/milestone-4A/create-light-final-1280x800.png) | [390×844](verification/milestone-4A/create-dark-final-390x844.png) |
| Settings | [390×844, saved fixture](verification/milestone-4A/settings-light-final-390x844.png) | [1280×800, saved/hover](verification/milestone-4A/settings-dark-final-1280x800.png) |

All sampled document widths fit their viewport. The 320 px account-header check initially found 328 px of content width; the corrected header fits 320 px. The dark Settings hover originally inherited a dark background with dark text; the corrected sampled colors are `rgb(232,232,232)` background and `rgb(17,17,17)` foreground. Native CDP viewport captures replaced panel-clipped screenshot output. Earlier screenshots are retained as history; the final mobile-padding and hover corrections were checked with targeted captures, not a repeated matrix.

Browser checks establish representative presentation, not full screen-reader or connected-auth conformance. Failure/denial simulations use injected adapters in regression tests; no server authorization was exercised.

## Files changed in this milestone

Updated: `src/app/App.jsx`, `src/app/routes.jsx`, `src/components/AppShell.jsx`.

Added by the milestone: `src/app/Access.test.jsx`, `src/data/accessAdapters.js`, `src/features/access/AccountPage.jsx`, `AccessState.jsx`, `ProjectsPage.jsx`, `useProjects.js`, `access.css`, this report and verification artifacts.

This continuation changed only `src/app/Access.test.jsx`, `src/features/access/AccountPage.jsx`, `src/features/access/ProjectsPage.jsx`, `src/features/access/access.css`, this report and `verification/milestone-4A/`. It reused the existing route, adapter, project-cache and app-shell implementation rather than replacing it.

No backend/SDK/investigator or package changes, installations, commits or pushes were made for this milestone. Earlier uncommitted work was retained.
