import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import './index.css'
import App from './app/App.jsx'
import { createApiAdapters } from './data/apiRepository.js'

const adapters = createApiAdapters()
if (!window.location.hash) window.location.hash = '#/projects/local/runs'
createRoot(document.getElementById('root')).render(<StrictMode><App {...adapters}/></StrictMode>)
