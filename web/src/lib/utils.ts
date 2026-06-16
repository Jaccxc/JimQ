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
