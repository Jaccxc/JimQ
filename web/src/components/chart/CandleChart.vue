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

const containerRef = ref<HTMLDivElement | null>(null)
// 非響應式:chart/series 實例不進 Vue 響應式。
let controller: ChartController | null = null
let historyLoaded = false

const market = useMarketStore()
const fills = useFillsStore()
const orders = useOrdersStore()
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
  <div ref="containerRef" class="candle-chart" data-testid="candle-chart"></div>
</template>

<style scoped>
.candle-chart {
  width: 100%;
  height: 100%;
  min-height: 360px;
}
</style>
