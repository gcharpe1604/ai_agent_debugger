import { useMemo } from 'react'
import App from '../app/App.jsx'
import { fixtureRepository } from './fixtureRepository.js'
import { traceRepository } from '../data/traceRepository.js'
import { investigationRepository } from '../data/investigationRepository.js'
import { createFixtureProjects } from './fixtureProjects.js'
import { selectRuns } from '../data/runRepository.js'

// Existing fixture regressions explicitly opt in; runtime App has no sample defaults.
export default function FixtureApp(props) {
  const repository = props.repository || fixtureRepository
  const adapter = useMemo(() => props.projectAdapter || createFixtureProjects(repository.projects), [props.projectAdapter, repository])
  const scoped = useMemo(() => ({ ...repository, listRuns: args => repository.projects.some(project => project.id === args.projectId) ? repository.listRuns(args) : Promise.resolve(selectRuns([], args.projectId, args.query)) }), [repository])
  return <App traceRepository={traceRepository} investigationRepository={investigationRepository} {...props} repository={scoped} projectAdapter={adapter}/>
}
