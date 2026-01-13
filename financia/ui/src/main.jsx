import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import './index.css'
import App from './App.jsx'
import { WebSocketProvider } from './contexts/WebSocketContext.jsx'
import { ToastProvider } from './contexts/ToastContext.jsx'

createRoot(document.getElementById('root')).render(
  <StrictMode>
    <WebSocketProvider>
      <ToastProvider>
        <App />
      </ToastProvider>
    </WebSocketProvider>
  </StrictMode>,
)
