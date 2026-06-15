/**
 * 行情 store:K 線資料(供圖表命令式消費)。
 *
 * 注意:bars 陣列本身是響應式狀態(供 panel/debug),但 **chart/series 實例**
 * 不放這裡(置於 useChart 的非響應式變數),元件在 watcher/socket handler 內
 * 命令式 series.update。store 只持資料來源真相。
 */
import { defineStore } from 'pinia'
import type { BarDTO } from '@/types/contract'

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
    /** WS 串流:同 time 更新最後一根,新 time 新增(對齊 LWC series.update 語意)。 */
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
  },
})
