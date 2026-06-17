<script setup lang="ts">
/**
 * 卡 #21 (W2) + 回放播放器 — 歷史 backtest 重播 K 線圖(prop 驅動,非 live store)。
 *
 * 換 run / run 完成時,把該 run 的**全量 bars + markers + equity** 交給回放引擎
 * (useReplayPlayer)做**前端動畫回放**:逐根 K 線長出、進出場 marker 在對應 bar
 * 一個個跳出、PnL/權益曲線同步長出。控制列(ReplayControls)綁引擎狀態並轉接
 * 互動(▶/⏸、速度、scrub、↺ 重播、⏭ 跳結尾顯示完整)。預設自動從頭播放(可暫停)。
 *
 * 鐵律:ChartController(含 chart/series 實例)存於**非響應式**變數(普通 let),
 * 引擎以命令式 sink 介面驅動它(updateBar 逐根 append / setMarkers / setEquityLine
 * / reset / fit);chart 實例不進 Vue 響應式。SL/TP priceLine 不參與動畫,選 run
 * 時整體套用一次(回放主軸是 K 線 + marker + equity)。
 */
import { onMounted, onBeforeUnmount, ref, watch } from 'vue'
import { ChartController } from '@/lib/chartController'
import { useReplayPlayer, type ReplaySink } from '@/composables/useReplayPlayer'
import ReplayControls from '@/components/chart/ReplayControls.vue'
import type { BarDTO } from '@/types/contract'
import type { MarkerSpec, PriceLineSpec } from '@/lib/tradeMapping'
import type { EquityPoint } from '@/lib/equityCurve'

const props = defineProps<{
  bars: BarDTO[]
  markers: MarkerSpec[]
  priceLines: PriceLineSpec[]
  /** PnL/權益曲線(主圖下方獨立副圖);回放時同步長出,跳結尾顯示完整。 */
  equity?: EquityPoint[]
  /**
   * 回放模式:true=選定/完成的歷史 run → 用回放引擎逐根動畫回放 + 控制列。
   * false(預設)=live 串流(scope=backtest 邊跑邊長出)→ 一次性命令式畫法,
   * 不動畫、不顯控制列(串流本身已是即時長出,不應被引擎重播)。
   */
  replay?: boolean
}>()

const containerRef = ref<HTMLDivElement | null>(null)
// 非響應式:chart/series 實例不進 Vue 響應式。
let controller: ChartController | null = null

// 回放引擎需要的命令式 sink(ChartController 子集)。priceLine 不參與動畫,
// 故在 reset 時一併清掉、load 後由 applyPriceLines 重套。
const sink: ReplaySink = {
  updateBar: (b) => controller?.updateBar(b),
  setHistory: (bars) => controller?.setHistory(bars),
  setMarkers: (specs) => controller?.setMarkers(specs),
  setEquityLine: (points) => controller?.setEquityLine(points),
  clearEquityLine: () => controller?.clearEquityLine(),
  reset: () => controller?.reset(),
  fit: () => controller?.fit(),
  applyDefaultWindow: () => controller?.applyDefaultWindow(),
}

const player = useReplayPlayer(sink)

function applyPriceLines() {
  if (!controller) return
  controller.clearPriceLines()
  for (const spec of props.priceLines) controller.addPriceLine(spec)
}

/** live 串流(非回放):一次性命令式畫法(setHistory + setMarkers + equity)。
 *  串流本身已即時長出,不交給回放引擎(否則會把已長出的歷史重新動畫一遍)。 */
function drawLive() {
  if (!controller) return
  player.pause()
  controller.setHistory(props.bars)
  controller.setMarkers(props.markers)
  applyPriceLines()
  const equity = props.equity ?? []
  if (equity.length) controller.setEquityLine(equity)
  else controller.clearEquityLine()
}

/** 回放模式(選定/完成的歷史 run):全量交給引擎並自動從頭播放(可暫停)。 */
function loadAndPlay() {
  if (!controller) return
  player.load({
    bars: props.bars,
    markers: props.markers,
    equity: props.equity ?? [],
  })
  // SL/TP 線非動畫,選 run 時整體套用一次(reset 已清掉,故在 load 之後重套)。
  applyPriceLines()
  if (props.bars.length > 1) player.play()
}

/** 依模式重畫:回放 run → 動畫;live 串流 → 一次性畫。 */
function refresh() {
  if (props.replay) loadAndPlay()
  else drawLive()
}

onMounted(() => {
  if (!containerRef.value) return
  controller = new ChartController(containerRef.value)
  refresh()
  // bars / markers / equity / priceLines / replay 任一變(換 run、載完成、模式切換)→ 重畫。
  watch(
    () => [props.bars, props.markers, props.priceLines, props.equity, props.replay],
    () => refresh(),
  )
})

onBeforeUnmount(() => {
  player.dispose()
  controller?.destroy()
  controller = null
})
</script>

<template>
  <div class="replay-chart-wrap">
    <div ref="containerRef" class="replay-chart" data-testid="replay-chart"></div>
    <ReplayControls
      v-if="replay"
      :playing="player.playing.value"
      :current-index="player.currentIndex.value"
      :total="player.total.value"
      :speed="player.speed.value"
      @play="player.play()"
      @pause="player.pause()"
      @set-speed="player.setSpeed($event)"
      @scrub="player.scrub($event)"
      @replay="player.replay()"
      @to-end="player.toEnd()"
    />
  </div>
</template>

<style scoped>
.replay-chart-wrap {
  display: flex;
  flex-direction: column;
  height: 100%;
  gap: calc(var(--spacing) * 1.5);
}
.replay-chart {
  flex: 1;
  width: 100%;
  min-height: 320px;
}
</style>
