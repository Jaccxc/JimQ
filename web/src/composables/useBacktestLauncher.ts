/**
 * 卡 #20 (W1) — backtest launcher 觸發邏輯。
 *
 * launch(form):POST /backtests/run → 寫 backtestRun store(startRun)→ 回 run_id。
 * 失敗時 store 標 FAILED 並 rethrow,讓呼叫端(表單元件)顯示錯誤。
 *
 * runImpl 可注入(測試決定論);預設用 api/backtests.runBacktest。
 */
import {
  runBacktest as defaultRunBacktest,
  type RunBacktestRequest,
  type RunBacktestAccepted,
} from '@/api/backtests'
import { useBacktestRunStore } from '@/stores/backtestRun'

export interface LauncherOptions {
  /** 注入 runBacktest(測試用)。 */
  runImpl?: (req: RunBacktestRequest) => Promise<RunBacktestAccepted>
}

export interface BacktestLauncher {
  launch: (form: RunBacktestRequest) => Promise<number>
}

export function useBacktestLauncher(opts: LauncherOptions = {}): BacktestLauncher {
  const run = opts.runImpl ?? ((req) => defaultRunBacktest(req))

  async function launch(form: RunBacktestRequest): Promise<number> {
    const store = useBacktestRunStore()
    try {
      const accepted = await run(form)
      store.startRun(accepted)
      return accepted.run_id
    } catch (err) {
      store.fail(err instanceof Error ? err.message : String(err))
      throw err
    }
  }

  return { launch }
}
