/**
 * 委託 store:累積 OrderInitialized 事件(供 panel + priceLine 驅動)。
 *
 * scope 命名空間:`useOrdersStore('live'|'backtest')` 各拿獨立 state
 * (`defineStore('orders:'+scope)`,Map memoize)。預設 scope='live' 相容。
 */
import { defineStore } from 'pinia'
import type { OrderInitializedData } from '@/types/contract'

const MAX = 500

interface State {
  orders: OrderInitializedData[]
}

function defineOrdersStore(scope: string) {
  return defineStore(`orders:${scope}`, {
      state: (): State => ({ orders: [] }),
      actions: {
        add(o: OrderInitializedData) {
          this.orders.push(o)
          if (this.orders.length > MAX) this.orders.splice(0, this.orders.length - MAX)
        },
      },
    })
}

const cache = new Map<string, ReturnType<typeof defineOrdersStore>>()

export function useOrdersStore(scope = 'live') {
  let def = cache.get(scope)
  if (!def) {
    def = defineOrdersStore(scope)
    cache.set(scope, def)
  }
  return def()
}
