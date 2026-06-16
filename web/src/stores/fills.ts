/**
 * 成交 store:累積 OrderFilled 事件(供 panel + marker 驅動)。
 *
 * scope 命名空間:`useFillsStore('live')` / `useFillsStore('backtest')` 各拿一份
 * 獨立 state(`defineStore('fills:'+scope)`,以 Map memoize 避免重複定義)。
 * Live 與 Backtest 串流寫進不同命名空間 → 互不污染。預設 scope='live' 相容。
 */
import { defineStore } from 'pinia'
import type { OrderFilledData } from '@/types/contract'

const MAX = 500

interface State {
  fills: OrderFilledData[]
}

function defineFillsStore(scope: string) {
  return defineStore(`fills:${scope}`, {
      state: (): State => ({ fills: [] }),
      actions: {
        add(f: OrderFilledData) {
          this.fills.push(f)
          if (this.fills.length > MAX) this.fills.splice(0, this.fills.length - MAX)
        },
      },
    })
}

const cache = new Map<string, ReturnType<typeof defineFillsStore>>()

export function useFillsStore(scope = 'live') {
  let def = cache.get(scope)
  if (!def) {
    def = defineFillsStore(scope)
    cache.set(scope, def)
  }
  return def()
}
