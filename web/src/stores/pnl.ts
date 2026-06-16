/**
 * PnL / 帳戶 store:last-value-wins(只留最新 AccountState)。
 * equity = base_currency 餘額的 total。
 *
 * scope 命名空間:`usePnlStore('live'|'backtest')` 各拿獨立 state
 * (`defineStore('pnl:'+scope)`,Map memoize)。預設 scope='live' 相容。
 */
import { defineStore } from 'pinia'
import type { AccountStateData } from '@/types/contract'

interface State {
  latest: AccountStateData | null
}

function definePnlStore(scope: string) {
  return defineStore(`pnl:${scope}`, {
      state: (): State => ({ latest: null }),
      getters: {
        /** base_currency 的 total 餘額(權益);無資料回 null。 */
        equity: (s): number | null => {
          if (!s.latest) return null
          const base = s.latest.balances.find(
            (b) => b.currency === s.latest!.base_currency,
          )
          const pick = base ?? s.latest.balances[0]
          return pick ? Number(pick.total) : null
        },
      },
      actions: {
        set(a: AccountStateData) {
          this.latest = a
        },
      },
    })
}

const cache = new Map<string, ReturnType<typeof definePnlStore>>()

export function usePnlStore(scope = 'live') {
  let def = cache.get(scope)
  if (!def) {
    def = definePnlStore(scope)
    cache.set(scope, def)
  }
  return def()
}
