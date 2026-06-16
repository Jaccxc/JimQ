/**
 * 卡 #27 (P2-S1) — app 模式 store(mode badge 來源)。
 *
 * mode 依**資料來源**:
 * - ``BACKTEST``:看歷史 backtest 串流(預設)。
 * - ``LIVE-TESTNET``:live 資料節點在跑(Binance testnet 真即時來源)。
 *
 * Live 頁掛載時 ``setLive()``;Backtest 頁掛載時 ``setBacktest()``。
 * badge 文字直接由 ``mode`` 字面值決定(大寫契約字面值)。
 */
import { defineStore } from 'pinia'

export type AppMode = 'BACKTEST' | 'LIVE-TESTNET'

interface State {
  mode: AppMode
}

export const useAppModeStore = defineStore('appMode', {
  state: (): State => ({
    mode: 'BACKTEST',
  }),
  getters: {
    badgeLabel: (s): AppMode => s.mode,
    isLive: (s): boolean => s.mode === 'LIVE-TESTNET',
  },
  actions: {
    setLive() {
      this.mode = 'LIVE-TESTNET'
    },
    setBacktest() {
      this.mode = 'BACKTEST'
    },
  },
})
