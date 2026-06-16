/**
 * 行情 store:K 線資料(供圖表命令式消費)。
 *
 * 注意:bars 陣列本身是響應式狀態(供 panel/debug),但 **chart/series 實例**
 * 不放這裡(置於 useChart 的非響應式變數),元件在 watcher/socket handler 內
 * 命令式 series.update。store 只持資料來源真相。
 */
import { defineStore } from 'pinia'
import type { BarDTO } from '@/types/contract'
import { aggregateTick, type TradePoint } from '@/lib/tradeAggregator'

interface State {
  bars: BarDTO[]
}

export const useMarketStore = defineStore('market', {
  state: (): State => ({ bars: [] }),
  getters: {
    lastBarTime: (s): number | null =>
      s.bars.length ? s.bars[s.bars.length - 1].time : null,
  },
  actions: {
    /** REST 歷史載入:整批設定(去重保序,以 time 為鍵)。 */
    setHistory(bars: BarDTO[]) {
      const seen = new Map<number, BarDTO>()
      for (const b of bars) seen.set(b.time, b)
      this.bars = [...seen.values()].sort((a, b) => a.time - b.time)
    },
    /** WS 串流:同 time 更新最後一根,新 time 新增(對齊 LWC series.update 語意)。
     *
     * ⛔ 收線權威:正式 1m bar(bars channel)以此覆蓋同 time 那根 ——
     * 即使 tick 視覺聚合(applyTick)先把該根改過,收線時 bar 為準(圖與策略對齊)。
     */
    applyBar(bar: BarDTO) {
      const n = this.bars.length
      if (n && this.bars[n - 1].time === bar.time) {
        this.bars[n - 1] = bar
      } else if (n && bar.time < this.bars[n - 1].time) {
        // 亂序/補洞:就地替換或忽略過舊(保守:同 time 覆寫,否則略過)。
        const idx = this.bars.findIndex((b) => b.time === bar.time)
        if (idx >= 0) this.bars[idx] = bar
      } else {
        this.bars.push(bar)
      }
    },

    /**
     * 卡 B(Live 次秒 tick):把一筆逐筆成交聚合到「形成中、尚未收線」那根 K 線。
     *
     * 同分鐘 bucket → 就地更新最後一根 high/low/close(open 維持);新分鐘 → 新增
     * 一根形成中 candle。讓 Live 圖當前 K 線隨成交即時跳動,不必等 1m 收線。
     *
     * ⛔ 純視覺:tick 只動「形成中」那根的視覺 OHLC;策略決策走 bars channel
     * (applyBar),收線時以正式 bar 覆蓋 → 圖與策略對齊。比現有 bucket 舊的
     * tick 由 aggregateTick 略過(不回退)。
     */
    applyTick(trade: TradePoint, bucketSeconds?: number) {
      const n = this.bars.length
      const last = n ? this.bars[n - 1] : null
      const next = aggregateTick(last, trade, bucketSeconds)
      if (last && next.time === last.time) {
        this.bars[n - 1] = next // 同 bucket:更新形成中那根。
      } else if (!last || next.time > last.time) {
        this.bars.push(next) // 新分鐘:新增形成中 candle。
      }
      // next.time < last.time(亂序)→ aggregateTick 已回原物件,無動作。
    },
  },
})
