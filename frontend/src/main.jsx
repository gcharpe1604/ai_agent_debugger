import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import '@fontsource-variable/inter/wght.css'
import '@fontsource/jetbrains-mono/400.css'
import './styles/tokens.css'
import './index.css'
import App from './app/App.jsx'
import { createApiAdapters, resolveSource } from './data/apiRepository.js'
import { expireSession } from './app/routes.jsx'

const source = resolveSource(window.location.search)
const adapters = createApiAdapters(fetch, { source, onUnauthorized: () => expireSession() })
// Durable: an empty hash opens the landing page. Local development opens the workspace.
if (!window.location.hash) window.location.hash = source === 'durable' ? '#/' : '#/projects/local'
createRoot(document.getElementById('root')).render(<StrictMode><App {...adapters}/></StrictMode>)
