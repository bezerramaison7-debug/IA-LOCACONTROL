import { Slot } from '@radix-ui/react-slot'
import type { ButtonHTMLAttributes } from 'react'

type ButtonProps = ButtonHTMLAttributes<HTMLButtonElement> & {
  asChild?: boolean
  variant?: 'primary' | 'secondary' | 'ghost' | 'danger'
  iconOnly?: boolean
}

export function Button({
  asChild = false,
  className = '',
  variant = 'primary',
  iconOnly = false,
  type = 'button',
  ...props
}: ButtonProps) {
  const Component = asChild ? Slot : 'button'
  return (
    <Component
      {...(!asChild ? { type } : {})}
      className={`button button-${variant} ${iconOnly ? 'icon-button' : ''} ${className}`}
      {...props}
    />
  )
}
