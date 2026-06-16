/**
 * 改版 S1b — shadcn-vue 共用工具。
 * cn():clsx 處理條件式 class，tailwind-merge 解 Tailwind 衝突(後者勝、去重)。
 * 全套 ui/* 元件靠它合併傳入的 :class 與內建變體 class。
 */
import { clsx, type ClassValue } from 'clsx'
import { twMerge } from 'tailwind-merge'

export function cn(...inputs: ClassValue[]): string {
  return twMerge(clsx(inputs))
}

/** 數字方向:正→up、負→down、0/NaN→flat。StatPill 等數字色塊據此上色。 */
export type StatDirection = 'up' | 'down' | 'flat'

export function statSign(value: number): StatDirection {
  if (!Number.isFinite(value) || value === 0) return 'flat'
  return value > 0 ? 'up' : 'down'
}
