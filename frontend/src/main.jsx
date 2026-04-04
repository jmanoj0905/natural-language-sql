import React from 'react'
import ReactDOM from 'react-dom/client'
import App from './App'
import './index.css'
import { ToastProvider } from './hooks/useToast.jsx'
import { ClerkProvider } from '@clerk/react'

const publishableKey = import.meta.env.VITE_CLERK_PUBLISHABLE_KEY

ReactDOM.createRoot(document.getElementById('root')).render(
  <React.StrictMode>
    <ClerkProvider publishableKey={publishableKey}>
      <ToastProvider>
        <App />
      </ToastProvider>
    </ClerkProvider>
  </React.StrictMode>,
)
