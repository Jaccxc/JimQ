<script setup lang="ts">
/**
 * 卡 #21 (W2) — 歷史 backtest 重播 K 線圖(prop 驅動,非 live store)。
 *
 * 與 live ``CandleChart`` 不同:本圖一次性顯示某歷史 run 的整段 bars + 該次
 * 進出場 marker / SL/TP priceLine(由 props 傳入),選不同 run 時整體重畫。
 *
 * 鐵律:ChartController(含 chart/series 實例)存於**非響應式**變數(普通 let),
 * 命令式套用;watch props 變化時 setHistory + setMarkers + 重建 priceLines。
 */
import { onMounted, onBeforeUnmount, ref, watch } from 'vue'
import { ChartController } from '@/lib/chartController'
import type { BarDTO } from '@/types/contract'
import type { MarkerSpec, PriceLineSpec } from '@/lib/tradeMapping'

const props = defineProps<{
  bars: BarDTO[]
  markers: MarkerSpec[]
  priceLines: PriceLineSpec[]
}>()

const containerRef = ref<HTMLDivElement | null>(null)
// 非響應式:chart/series 實例不進 Vue 響應式。
let controller: ChartController | null = null

/** 以目前 props 整體重畫(換 run 時呼叫)。 */
function redraw() {
  if (!controller) return
  controller.setHistory(props.bars)
  controller.setMarkers(props.markers)
  controller.clearPriceLines()
  for (const spec of props.priceLines) controller.addPriceLine(spec)
}

onMounted(() => {
  if (!containerRef.value) return
  controller = new ChartController(containerRef.value)
  redraw()
  // bars / markers / priceLines 任一變(換 run 或載完成)→ 重畫。
  watch(
    () => [props.bars, props.markers, props.priceLines],
    () => redraw(),
  )
})

onBeforeUnmount(() => {
  controller?.destroy()
  controller = null
})
</script>

<template>
  <div ref="containerRef" class="replay-chart" data-testid="replay-chart"></div>
</template>

<style scoped>
.replay-chart {
  width: 100%;
  height: 100%;
  min-height: 360px;
}
</style>
