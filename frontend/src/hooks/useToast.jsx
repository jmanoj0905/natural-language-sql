import { createContext, useContext, useState, useCallback } from 'react'
import Toast from '../components/Toast'

const ToastContext = createContext(null)

export const ToastProvider = ({ children }) => {
  const [toasts, setToasts] = useState([])

  const showToast = useCallback((message, type = 'info', duration = 5000) => {
    const id = Date.now() + Math.random()

    setToasts(prev => {
      // Limit to 3 toasts at a time
      const newToasts = [...prev, { id, message, type, duration }]
      return newToasts.slice(-3)
    })
  }, [])

  const removeToast = useCallback((id) => {
    setToasts(prev => prev.filter(toast => toast.id !== id))
  }, [])

  const showSuccess = useCallback((message, duration) => {
    showToast(message, 'success', duration)
  }, [showToast])

  const showError = useCallback((message, duration) => {
    showToast(message, 'error', duration)
  }, [showToast])

  const showWarning = useCallback((message, duration) => {
    showToast(message, 'warning', duration)
  }, [showToast])

  const showInfo = useCallback((message, duration) => {
    showToast(message, 'info', duration)
  }, [showToast])

  return (
    <ToastContext.Provider value={{ showToast, showSuccess, showError, showWarning, showInfo }}>
      {children}

      {/* Toast Container */}
      <div
        className="fixed top-4 right-4 z-50 w-full max-w-sm space-y-3 pointer-events-none"
        aria-live="polite"
        aria-atomic="true"
      >
        <div className="pointer-events-auto">
          {toasts.map(toast => (
            <Toast
              key={toast.id}
              id={toast.id}
              message={toast.message}
              type={toast.type}
              duration={toast.duration}
              onClose={removeToast}
            />
          ))}
        </div>
      </div>
    </ToastContext.Provider>
  )
}

export const useToast = () => {
  const context = useContext(ToastContext)
  if (!context) {
    throw new Error('useToast must be used within ToastProvider')
  }
  return context
}
