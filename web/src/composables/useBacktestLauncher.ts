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
import type { BarRange } from '@/api/bars'
import { useBacktestRunStore } from '@/stores/backtestRun'

/** datetime-local input 值(YYYY-MM-DDTHH:mm,UTC 解讀)。 */
export interface DefaultRange {
  start: string
  end: string
  /** catalog 有資料(動態填)還是 fallback(空 catalog)。 */
  hasData: boolean
}

const _NS_PER_MS = 1_000_000

/** epoch 奈秒 → datetime-local 字串(UTC,分鐘精度)。 */
function nsToLocalInput(ns: number): string {
  return new Date(ns / _NS_PER_MS).toISOString().slice(0, 16)
}

/**
 * 把 catalog range 轉成 launcher 預設 start/end(datetime-local 字串)。
 *
 * - catalog 有資料(count>0、start/end 非 null):取**最後一段足夠長**的範圍
 *   (上限 1 天;資料更短時取整段),確保夠 EMA 交叉產生成交。end = 資料末端。
 * - 空 catalog:回 hasData=false 的合理 fallback(2024-01-01 一天),呼叫端可提示。
 */
export function defaultRange(range: BarRange): DefaultRange {
  const FALLBACK_START = '2024-01-01T00:00'
  const FALLBACK_END = '2024-01-02T00:00'
  if (range.count <= 0 || range.start == null || range.end == null) {
    return { start: FALLBACK_START, end: FALLBACK_END, hasData: false }
  }
  const endNs = range.end
  // 取最後 1 天(86_400_000 ms);資料更短時退回資料起點。
  const ONE_DAY_NS = 24 * 60 * 60 * 1000 * _NS_PER_MS
  const startNs = Math.max(range.start, endNs - ONE_DAY_NS)
  return { start: nsToLocalInput(startNs), end: nsToLocalInput(endNs), hasData: true }
}

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
