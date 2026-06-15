/**
 * PnL / 帳戶 store:last-value-wins(只留最新 AccountState)。
 * equity = base_currency 餘額的 total。
 */
import { defineStore } from 'pinia'
import type { AccountStateData } from '@/types/contract'

interface State {
  latest: AccountStateData | null
}

export const usePnlStore = defineStore('pnl', {
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
