import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import './index.css'
import App from './app/App.jsx'
import { createApiAdapters, resolveSource } from './data/apiRepository.js'
import { expireSession } from './app/routes.jsx'

const source = resolveSource(window.location.search)
const adapters = createApiAdapters(fetch, { source, onUnauthorized: () => expireSession() })
if (!window.location.hash) window.location.hash = source === 'durable' ? '#/projects/default' : '#/projects/local'
createRoot(document.getElementById('root')).render(<StrictMode><App {...adapters}/></StrictMode>)
