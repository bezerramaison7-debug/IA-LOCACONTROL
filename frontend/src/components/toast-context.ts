import { createContext, useContext } from 'react'
export const ToastContext = createContext<(message: string) => void>(() => {})
export const useToast = () => useContext(ToastContext)
