import { useState } from 'react'
import Icon from '../components/Icon.jsx'
import { useAccount } from '../features/access/session.js'
import { settingsHref } from '../app/routes.jsx'
import './settings.css'

// Profile: everything the signed-in account knows about the user, read-only.
// Settings holds only project settings and the API key.
export default function ProfilePage({ project }) {
  const account = useAccount()
  const user = project.storage === 'durable' ? account?.user : null
  const [notice, setNotice] = useState('')
  async function copy() {
    try { await navigator.clipboard.writeText(user.id); setNotice('User ID copied') } catch { setNotice('Clipboard unavailable. Select and copy the user ID.') }
  }
  return <section className="settings-page" aria-labelledby="profile-heading">
    <header className="view-heading"><h1 id="profile-heading">Profile</h1></header>
    <div className="settings-tabs">
      <div className="settings-panel">
        {user ? <>
          <div className="profile-identity">
            <span className="user-avatar profile-avatar" aria-hidden="true">{user.name.trim().charAt(0).toUpperCase()}</span>
            <div><p className="profile-name">{user.name}</p><p className="settings-note">{user.email}</p></div>
          </div>
          <dl className="settings-facts">
            <div><dt>Name</dt><dd>{user.name}</dd></div>
            <div><dt>Email</dt><dd>{user.email}<span className="secondary"> · read-only</span></dd></div>
            {user.id && <div><dt>User ID</dt><dd><button type="button" className="trace-copy mono" onClick={copy} title={user.id} aria-label="Copy user ID">{user.id}<Icon name="copy"/></button></dd></div>}
            <div><dt>Project</dt><dd>{project.name}</dd></div>
            <div><dt>API key</dt><dd><code>{user.keyPrefix}…</code> <a className="profile-link" href={`${settingsHref(project.id)}?tab=api-key`}>Manage in Settings</a></dd></div>
          </dl>
          <p className="settings-note">Name and email cannot be changed here yet.</p>
        </> : <p className="settings-note">Local mode has no accounts: the backend accepts traces only from this computer and nobody signs in.</p>}
      </div>
    </div>
    <span className="sr-only" aria-live="polite">{notice}</span>
  </section>
}
