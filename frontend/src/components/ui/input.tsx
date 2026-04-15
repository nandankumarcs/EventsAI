import type { InputHTMLAttributes } from 'react'

import { cn } from '@/lib/utils'

export function Input({ className, ...props }: InputHTMLAttributes<HTMLInputElement>) {
  return (
    <input
      className={cn(
        'flex h-12 w-full rounded-md border border-border bg-background/80 px-4 py-3 text-sm text-foreground shadow-sm outline-none transition focus-visible:border-ring focus-visible:ring-2 focus-visible:ring-ring/20 placeholder:text-muted-foreground',
        className,
      )}
      {...props}
    />
  )
}

