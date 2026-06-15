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
import { fillToMarker, orderToPriceLines } from '@/lib/tradeMapping'

const containerRef = ref<HTMLDivElement | null>(null)
// 非響應式:chart/series 實例不進 Vue 響應式。
let controller: ChartController | null = null
let historyLoaded = false

const market = useMarketStore()
const fills = useFillsStore()
const orders = useOrdersStore()

onMounted(() => {
  if (!containerRef.value) return
  controller = new ChartController(containerRef.value)

  // 初始:若 store 已有歷史,先畫。
  if (market.bars.length) {
    controller.setHistory(market.bars)
    historyLoaded = true
  }

  // bars:length 變化 → 首批 setHistory,之後逐根 update。
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
    },
  )
  // 同 time 更新最後一根(length 不變但內容變)。
  watch(
    () => (market.bars.length ? market.bars[market.bars.length - 1].close : null),
    () => {
      if (controller && historyLoaded && market.bars.length) {
        controller.updateBar(market.bars[market.bars.length - 1])
      }
    },
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
