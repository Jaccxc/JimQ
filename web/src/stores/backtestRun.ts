/**
 * 卡 #20 (W1) — 目前 backtest run 狀態 store。
 *
 * launcher 觸發後追蹤目前 run 的身份(run_id / correlation_id)與狀態流轉
 * (IDLE → PENDING → RUNNING → COMPLETED / FAILED)。Dashboard 據此顯示 run
 * 狀態,並在 active 時訂 WS 看 K 線/進出場長出來。
 */
import { defineStore } from 'pinia'
import type { RunBacktestAccepted } from '@/api/backtests'

/** run 狀態(對齊後端 BacktestStatus + 前端 IDLE 初始)。 */
export type RunStatus = 'IDLE' | 'PENDING' | 'RUNNING' | 'COMPLETED' | 'FAILED'

interface State {
  runId: number | null
  correlationId: string | null
  status: RunStatus
  error: string | null
}

export const useBacktestRunStore = defineStore('backtestRun', {
  state: (): State => ({
    runId: null,
    correlationId: null,
    status: 'IDLE',
    error: null,
  }),
  getters: {
    /** run 進行中(PENDING/RUNNING):前端應訂 WS、輪詢狀態。 */
    isActive: (s): boolean => s.status === 'PENDING' || s.status === 'RUNNING',
  },
  actions: {
    /** launcher 接受回應後啟動追蹤。 */
    startRun(accepted: RunBacktestAccepted) {
      this.runId = accepted.run_id
      this.correlationId = accepted.correlation_id
      this.status = (accepted.status as RunStatus) ?? 'PENDING'
      this.error = null
    },
    setStatus(status: RunStatus) {
      this.status = status
    },
    fail(message: string) {
      this.status = 'FAILED'
      this.error = message
    },
    reset() {
      this.runId = null
      this.correlationId = null
      this.status = 'IDLE'
      this.error = null
    },
  },
})
