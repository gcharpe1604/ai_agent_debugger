import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import './index.css'
import App from './app/App.jsx'
import { createApiAdapters, resolveSource } from './data/apiRepository.js'

const adapters = createApiAdapters(fetch, { source: resolveSource(window.location.search, import.meta.env.VITE_DATA_SOURCE) })
if (!window.location.hash) window.location.hash = '#/projects/local'
createRoot(document.getElementById('root')).render(<StrictMode><App {...adapters}/></StrictMode>)
