// Frontend view adapters, NOT HTTP endpoints, wire schemas or authorization rules.
// The disconnected adapter neither verifies credentials nor fabricates a session.
export const disconnectedAccount = Object.freeze({
  async readSession() { return { state: 'unavailable' } },
  async signIn() { throw Object.assign(new Error('Authentication is not connected.'), { kind: 'disconnected' }) },
  async register() { throw Object.assign(new Error('Registration is not connected.'), { kind: 'disconnected' }) },
  async signOut() { throw Object.assign(new Error('Session revocation is not connected.'), { kind: 'disconnected' }) },
})

export function projectNameError(value) {
  if (!value.trim()) return 'Enter a project name.'
  if (value.trim().length > 100) return 'Use 100 characters or fewer for this sample project.'
  return ''
}

export function createFixtureProjects(seed) {
  let records = seed.map(project => ({ ...project }))
  let sequence = 1
  const read = () => records.map(project => ({ ...project }))
  return {
    mode: 'fixture', initialProjects: read(),
    async listProjects({ signal } = {}) { signal?.throwIfAborted(); return read() },
    async createProject({ name, signal }) {
      signal?.throwIfAborted()
      const error = projectNameError(name)
      if (error) throw Object.assign(new Error(error), { kind: 'validation' })
      let id
      do { id = `local-project-${sequence++}` } while (records.some(project => project.id === id))
      const project = { id, name: name.trim(), initial: name.trim()[0].toLocaleUpperCase(), environment: 'Development fixture' }
      records = [...records, project]
      return { ...project }
    },
    async updateProject({ projectId, name, signal }) {
      signal?.throwIfAborted()
      if (!records.some(project => project.id === projectId)) throw Object.assign(new Error('Unavailable'), { kind: 'unavailable' })
      const error = projectNameError(name)
      if (error) throw Object.assign(new Error(error), { kind: 'validation' })
      records = records.map(project => project.id === projectId ? { ...project, name: name.trim(), initial: name.trim()[0].toLocaleUpperCase() } : project)
      return { ...records.find(project => project.id === projectId) }
    },
  }
}

export function failureKind(error) {
  return ['forbidden', 'expired', 'unavailable', 'disconnected'].includes(error?.kind) ? error.kind : 'failure'
}
