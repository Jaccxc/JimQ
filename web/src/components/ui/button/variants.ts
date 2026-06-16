import { cva, type VariantProps } from 'class-variance-authority'

/**
 * 改版 S1b — Button 變體。深色玻璃感，吃 theme.css token。
 * default = Apple 藍實心;outline/ghost = 玻璃描邊;destructive = 跌色。
 */
export const buttonVariants = cva(
  'inline-flex items-center justify-center gap-2 whitespace-nowrap rounded-[var(--radius-sm)] text-sm font-medium tracking-[-0.01em] transition-[transform,opacity,background-color] duration-[var(--duration-fast)] ease-[var(--ease-glass)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--color-accent)] focus-visible:ring-offset-1 focus-visible:ring-offset-[var(--color-bg)] disabled:pointer-events-none disabled:opacity-50 active:scale-[0.98]',
  {
    variants: {
      variant: {
        default:
          'bg-[var(--color-accent)] text-white hover:opacity-90 shadow-[0_2px_8px_rgba(10,132,255,0.35)]',
        destructive:
          'bg-[var(--color-down)] text-white hover:opacity-90 shadow-[0_2px_8px_rgba(255,92,92,0.3)]',
        outline:
          'border border-[var(--glass-l1-border)] bg-white/[0.03] text-[var(--color-text)] hover:bg-white/[0.07]',
        ghost:
          'text-[var(--color-text-muted)] hover:bg-white/[0.06] hover:text-[var(--color-text)]',
        link: 'text-[var(--color-accent)] underline-offset-4 hover:underline',
      },
      size: {
        default: 'h-9 px-4 py-2',
        sm: 'h-8 px-3 text-xs',
        lg: 'h-10 px-6',
        icon: 'h-9 w-9',
      },
    },
    defaultVariants: {
      variant: 'default',
      size: 'default',
    },
  },
)

export type ButtonVariants = VariantProps<typeof buttonVariants>
