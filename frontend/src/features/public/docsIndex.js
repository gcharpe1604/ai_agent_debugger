// Docs navigation: groups, titles and order. Page bodies are in docsContent.jsx.
import { Api, Concepts, Instrumenting, Introduction, Limits, Quickstart, SelfHosting, UsingTheUi } from './docsContent.jsx'

export const docGroups = [
  ['Get started', ['introduction', 'quickstart']],
  ['Guides', ['instrumenting', 'using-the-ui']],
  ['Reference', ['concepts', 'api']],
  ['Operate', ['self-hosting', 'limits']],
]

export const docPages = {
  introduction: { title: 'Introduction', Body: Introduction },
  quickstart: { title: 'Quickstart', Body: Quickstart },
  instrumenting: { title: 'Instrument your agent', Body: Instrumenting },
  'using-the-ui': { title: 'Using the UI', Body: UsingTheUi },
  concepts: { title: 'Concepts', Body: Concepts },
  api: { title: 'HTTP API', Body: Api },
  'self-hosting': { title: 'Self-hosting', Body: SelfHosting },
  limits: { title: 'Limits and roadmap', Body: Limits },
}
export const docOrder = docGroups.flatMap(([, slugs]) => slugs)
