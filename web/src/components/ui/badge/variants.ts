import { cva, type VariantProps } from 'class-variance-authority'

/** 改版 S1b — Badge 變體(mode badge / 狀態標)。吃 theme.css token。 */
export const badgeVariants = cva(
  'inline-flex items-center rounded-[var(--radius-xs)] border px-2 py-0.5 text-xs font-medium tracking-[-0.01em] transition-colors',
  {
    variants: {
      variant: {
        default:
          'border-transparent bg-[var(--color-accent)]/15 text-[var(--color-accent)]',
        secondary:
          'border-[var(--glass-l1-border)] bg-white/[0.04] text-[var(--color-text-muted)]',
        outline: 'border-[var(--glass-l1-border)] text-[var(--color-text)]',
        up: 'border-transparent bg-[var(--color-up-pill)] text-[var(--color-up)]',
        down: 'border-transparent bg-[var(--color-down-pill)] text-[var(--color-down)]',
      },
    },
    defaultVariants: {
      variant: 'default',
    },
  },
)

export type BadgeVariants = VariantProps<typeof badgeVariants>
