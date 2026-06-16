<script setup lang="ts">
/**
 * K 線圖元件(LWC v5 薄包裝)。
 *
 * 鐵律:ChartController(含 chart/series 實例)存於**非響應式**變數(普通 let,
 * 不 ref/reactive),命令式餵更新。元件訂 stores,在 watcher/$subscribe 內以
 * controller 方法推資料。
 *
 * 資料流:
 * - market.bars 首批(REST 歷史)→ controller.setHistory
 * - market.bars 新增/更新(WS)→ controller.updateBar(最後一根)
 * - fills(新成交)→ fillToMarker → controller.addMarker
 * - orders(SL/TP 委託)→ orderToPriceLines → controller.addPriceLine
 */
import { onMounted, onBeforeUnmount, ref, watch } from 'vue'
import { ChartController } from '@/lib/chartController'
import { useMarketStore } from '@/stores/market'
import { useFillsStore } from '@/stores/fills'
import { useOrdersStore } from '@/stores/orders'
import { useChartSettingsStore } from '@/stores/chartSettings'
import { fillToMarker, orderToPriceLines } from '@/lib/tradeMapping'
import { emaLineData } from '@/lib/ema'

/**
 * scope:讀哪個命名空間的串流 state(真 bug 修復)。Live 圖用 'live'(預設),
 * Backtest 串流主圖用 'backtest' → 兩圖讀不同 market/fills/orders store,互不污染。
 * chartSettings/EMA 是全域 UI 設定,不分 scope。
 */
const props = withDefaults(defineProps<{ scope?: string }>(), { scope: 'live' })

const containerRef = ref<HTMLDivElement | null>(null)
// 非響應式:chart/series 實例不進 Vue 響應式。
let controller: ChartController | null = null
let historyLoaded = false

/** Auto Fit 按鈕:fit 時間軸 + 重開價格軸 autoScale(TradingView 式對齊)。
 *  手動拖曳/縮放不受影響,按一下即重新貼合當前資料。 */
function fitChart() {
  controller?.fit()
}

const market = useMarketStore(props.scope)
const fills = useFillsStore(props.scope)
const orders = useOrdersStore(props.scope)
const settings = useChartSettingsStore()

/** 依目前設定重算並命令式套用 EMA fast/slow 疊圖(開→set、關→remove)。 */
function syncEma() {
  if (!controller) return
  const bars = market.bars
  if (settings.emaFast.enabled) {
    controller.setEmaLine('fast', emaLineData(bars, settings.emaFast.period))
  } else {
    controller.removeEmaLine('fast')
  }
  if (settings.emaSlow.enabled) {
    controller.setEmaLine('slow', emaLineData(bars, settings.emaSlow.period))
  } else {
    controller.removeEmaLine('slow')
  }
}

onMounted(() => {
  if (!containerRef.value) return
  controller = new ChartController(containerRef.value)

  // 初始:若 store 已有歷史,先畫。
  if (market.bars.length) {
    controller.setHistory(market.bars)
    historyLoaded = true
  }

  // 初次若已有歷史,套一次 EMA。
  syncEma()

  // bars:length 變化 → 首批 setHistory,之後逐根 update;每次同步 EMA。
  watch(
    () => market.bars.length,
    (len, prev) => {
      if (!controller || len === 0) return
      if (!historyLoaded) {
        controller.setHistory(market.bars)
        historyLoaded = true
      } else if (len > (prev ?? 0)) {
        controller.updateBar(market.bars[len - 1])
      }
      syncEma()
    },
  )
  // 同 time 更新最後一根(length 不變但內容變)。
  watch(
    () => (market.bars.length ? market.bars[market.bars.length - 1].close : null),
    () => {
      if (controller && historyLoaded && market.bars.length) {
        controller.updateBar(market.bars[market.bars.length - 1])
        syncEma()
      }
    },
  )

  // 切換標的 / 週期:reset 重用 chart 實例(不重建 series/不洩漏),
  // 待新歷史進來時由 bars watcher 重畫。
  watch(
    () => [settings.symbol, settings.timeframe].join('|'),
    () => {
      if (!controller) return
      controller.reset()
      historyLoaded = false
    },
  )

  // EMA 開關 / 週期變更:即時重算疊圖。
  watch(
    () => [
      settings.emaFast.enabled,
      settings.emaFast.period,
      settings.emaSlow.enabled,
      settings.emaSlow.period,
    ].join('|'),
    () => syncEma(),
  )

  // fills → markers。
  watch(
    () => fills.fills.length,
    (len, prev) => {
      if (!controller) return
      for (let i = prev ?? 0; i < len; i++) {
        controller.addMarker(fillToMarker(fills.fills[i]))
      }
    },
    { immediate: true },
  )

  // orders → SL/TP priceLines。
  watch(
    () => orders.orders.length,
    (len, prev) => {
      if (!controller) return
      for (let i = prev ?? 0; i < len; i++) {
        for (const spec of orderToPriceLines(orders.orders[i])) {
          controller.addPriceLine(spec)
        }
      }
    },
    { immediate: true },
  )
})

onBeforeUnmount(() => {
  controller?.destroy()
  controller = null
})
</script>

<template>
  <div class="candle-wrap">
    <button
      type="button"
      class="fit-btn"
      title="自動對齊(fit + auto-scale)"
      data-testid="chart-fit-btn"
      @click="fitChart"
    >
      ⤢ Fit
    </button>
    <div ref="containerRef" class="candle-chart" data-testid="candle-chart"></div>
  </div>
</template>

<style scoped>
.candle-wrap {
  position: relative;
  width: 100%;
  height: 100%;
  min-height: 360px;
}
.candle-chart {
  width: 100%;
  height: 100%;
  min-height: 360px;
}
/* 浮在圖右上角的玻璃小按鈕;不擋拖曳(只佔右上一角)。 */
.fit-btn {
  position: absolute;
  top: 8px;
  right: 8px;
  z-index: 3;
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 4px 10px;
  font-size: 12px;
  font-weight: 600;
  color: var(--color-text);
  background: var(--surface-2);
  border: 1px solid var(--surface-hover-border);
  border-radius: var(--radius-sm);
  backdrop-filter: blur(12px);
  cursor: pointer;
  transition:
    background var(--duration-fast) var(--ease-glass),
    border-color var(--duration-fast) var(--ease-glass);
}
.fit-btn:hover {
  background: var(--accent-tint);
  border-color: var(--accent-border);
  color: var(--color-accent);
}
.fit-btn:focus-visible {
  outline: 2px solid var(--color-accent);
  outline-offset: 2px;
}
</style>
