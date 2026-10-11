import { useState, type ReactNode } from 'react'
import { CircleCheck, X } from 'lucide-react'
import { ToastContext } from './toast-context'
import { Button } from './Button'

export function ToastProvider({ children }: { children: ReactNode }) {
  const [toast, setToast] = useState<{ message: string; id: number } | null>(null)
  return (
    <ToastContext.Provider value={(message) => setToast({ message, id: Date.now() })}>
      {children}
      <div className="toast-region" aria-live="polite" aria-atomic="true">
        {toast && (
          <div className="toast" key={toast.id}>
            <CircleCheck size={20} aria-hidden="true" />
            <p>{toast.message}</p>
            <Button
              variant="ghost"
              iconOnly
              aria-label="Fechar notificação"
              onClick={() => setToast(null)}
            >
              <X size={18} aria-hidden="true" />
            </Button>
          </div>
        )}
      </div>
    </ToastContext.Provider>
  )
}
