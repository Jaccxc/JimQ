/**
 * Backtest 前端回放播放器 — 回放引擎(可測純邏輯)。
 *
 * 用某 run 的**全量 bars + markers + equity** 做**前端動畫回放**:逐根 K 線長出、
 * 進出場 marker 在對應 bar 一個個跳出、PnL/權益曲線同步長出。控制:▶/⏸、速度
 * (根/秒)、進度 scrub(可往回/往前拖)、↺ 重播、⏭ 跳到結尾(顯示完整)。
 *
 * 設計(deep module):本 composable 只管狀態(currentIndex / playing / speed)+
 * 推進排程,並把「到 currentIndex(對應 bar.time)為止」的切片增量餵進 ``sink``
 * (ChartController 的命令式子集)。chart/series 實例不進此處(留在元件層的
 * 非響應式 controller),故引擎可用 fake sink + fake timer 做決定論行為測試。
 *
 * 效能:逐根用 ``sink.updateBar``(append 一根)而非每 tick 重 setHistory 全量;
 * marker/equity 用累積到當前 bar.time(setMarkers/setEquityLine 帶切片)。
 *  - 往前推進(play / scrub 往前):只 append 新增的那幾根 + 更新累積切片。
 *  - 往回(scrub 往回):無法「收回」已 append 的 bar,故 reset sink 後重建到
 *    目標 index(順的實作:reset → setHistory 切片 → setMarkers/equity 切片)。
 *  - toEnd:一次性畫完整(setHistory 全量 + 全部 marker + 全部 equity)。
 */
import { ref } from 'vue'
import type { Ref } from 'vue'
import type { BarDTO } from '@/types/contract'
import type { MarkerSpec } from '@/lib/tradeMapping'
import type { EquityPoint } from '@/lib/equityCurve'

/** 回放引擎需要的 chart 命令式介面(ChartController 子集;測試用 fake)。 */
export interface ReplaySink {
  /** append 一根(逐根長出;LWC series.update 語意)。 */
  updateBar(bar: BarDTO): void
  /** 整批設定 K 線(往回重建 / 跳結尾用)。 */
  setHistory(bars: BarDTO[]): void
  /** 全量替換 marker 累積切片。 */
  setMarkers(specs: MarkerSpec[]): void
  /** 全量替換權益曲線切片。 */
  setEquityLine(points: EquityPoint[]): void
  /** 清空權益曲線(切片為空時)。 */
  clearEquityLine(): void
  /** 清空 K 線/marker/equity(往回 / 重播用)。 */
  reset(): void
  /** 時間軸/價格軸自動貼合。 */
  fit(): void
}

export interface ReplayData {
  bars: BarDTO[]
  markers: MarkerSpec[]
  equity: EquityPoint[]
}

const DEFAULT_SPEED = 5
const MIN_SPEED = 1
const MAX_SPEED = 50
/** 推進 tick 間隔(毫秒);每 tick 推進 round(speed/ticksPerSec) 根。 */
const TICK_MS = 100
const TICKS_PER_SEC = 1000 / TICK_MS

function clamp(n: number, lo: number, hi: number): number {
  return Math.max(lo, Math.min(hi, n))
}

export function useReplayPlayer(sink: ReplaySink) {
  const currentIndex = ref(0)
  const total = ref(0)
  const playing = ref(false)
  const speed = ref(DEFAULT_SPEED)

  let data: ReplayData = { bars: [], markers: [], equity: [] }
  let timer: ReturnType<typeof setInterval> | null = null
  /** 本段播放已過的 tick 數;target = baseIndex + floor(ticks * speed / TICKS_PER_SEC)。
   *  以整數 tick 計推進量,避免浮點累加漂移(0.1*10 ≠ 1)。 */
  let ticks = 0
  /** 本段播放起始時的 index(改速度/暫停續播時重設基準)。 */
  let baseIndex = 0

  function clearTimer(): void {
    if (timer !== null) {
      clearInterval(timer)
      timer = null
    }
  }

  /** marker 累積切片:time <= 當前 bar.time 的全部 marker。 */
  function markersUpTo(time: number): MarkerSpec[] {
    return data.markers.filter((m) => m.time <= time)
  }
  /** equity 累積切片:time <= 當前 bar.time 的全部點。 */
  function equityUpTo(time: number): EquityPoint[] {
    return data.equity.filter((e) => e.time <= time)
  }

  /** 套用 marker/equity 累積切片到 sink(空 equity 用 clearEquityLine)。 */
  function applyOverlays(barTime: number): void {
    sink.setMarkers(markersUpTo(barTime))
    const eq = equityUpTo(barTime)
    if (eq.length) sink.setEquityLine(eq)
    else sink.clearEquityLine()
  }

  /**
   * 把 index 設到 target 並讓 sink 反映之。
   * - target > currentIndex:逐根 append 新增的 bar(高效)+ 更新 overlay 切片。
   * - target <= currentIndex(往回 / 重建):reset + setHistory 切片 + overlay。
   */
  function goTo(target: number, forceRebuild = false): void {
    if (total.value === 0) {
      currentIndex.value = 0
      return
    }
    const next = clamp(target, 0, total.value - 1)
    const barTime = data.bars[next].time
    if (forceRebuild || next < currentIndex.value) {
      // 往回 / 重建:無法收回已 append 的 bar,整批重設到切片。
      sink.reset()
      sink.setHistory(data.bars.slice(0, next + 1))
      applyOverlays(barTime)
      sink.fit()
    } else {
      // 往前:只 append 從 currentIndex+1..next 的新 bar(首次 load 時含 0)。
      const from = currentIndex.value === next ? next : currentIndex.value + 1
      for (let i = from; i <= next; i++) sink.updateBar(data.bars[i])
      applyOverlays(barTime)
    }
    currentIndex.value = next
  }

  function load(d: ReplayData): void {
    clearTimer()
    playing.value = false
    data = { bars: d.bars ?? [], markers: d.markers ?? [], equity: d.equity ?? [] }
    total.value = data.bars.length
    currentIndex.value = 0
    sink.reset()
    if (total.value === 0) return
    // 畫出第 0 根(只有第一根,無未來 marker/equity)。
    sink.updateBar(data.bars[0])
    applyOverlays(data.bars[0].time)
    sink.fit()
  }

  /** 重設推進基準到當前 index(開始播 / 改速度 / 暫停續播時呼叫)。 */
  function rebase(): void {
    baseIndex = currentIndex.value
    ticks = 0
  }

  function tick(): void {
    if (total.value === 0) return
    ticks += 1
    // 整數累進量:已過秒數 * 速度。用整數乘除避免浮點漂移。
    const advanced = Math.floor((ticks * speed.value) / TICKS_PER_SEC)
    const target = baseIndex + advanced
    if (target > currentIndex.value) goTo(target)
    if (currentIndex.value >= total.value - 1) {
      pause()
    }
  }

  function play(): void {
    if (total.value === 0) return
    if (currentIndex.value >= total.value - 1) return // 已在結尾,無可播。
    if (playing.value) return
    playing.value = true
    rebase()
    timer = setInterval(tick, TICK_MS)
  }

  function pause(): void {
    clearTimer()
    playing.value = false
  }

  function setSpeed(s: number): void {
    speed.value = clamp(Math.round(s), MIN_SPEED, MAX_SPEED)
    // 播放中改速度:以當前 index 為新基準,讓下一 tick 起用新速度推進。
    if (playing.value) rebase()
  }

  /** 拖動進度條:設 index(可往回 → reset 重建;往前 → 補畫)。
   *  scrub 是刻意的跳轉 → 一律 fit,讓使用者看到已長出的整段(往前補畫時
   *  LWC 預設停在最新幾根,不 fit 會像只長 2 根;goTo 的往回重建已含 fit)。 */
  function scrub(index: number): void {
    const wasPlaying = playing.value
    pause()
    goTo(index)
    sink.fit()
    if (wasPlaying && currentIndex.value < total.value - 1) play()
  }

  /** ↺ 重播:index 歸 0、reset、從頭自動播放(可暫停)。 */
  function replay(): void {
    pause()
    if (total.value === 0) return
    sink.reset()
    currentIndex.value = 0
    sink.updateBar(data.bars[0])
    applyOverlays(data.bars[0].time)
    sink.fit()
    play()
  }

  /** ⏭ 跳到結尾:一次性畫完整(setHistory 全量 + 全部 marker + 全部 equity),停。 */
  function toEnd(): void {
    pause()
    if (total.value === 0) return
    sink.reset()
    sink.setHistory(data.bars)
    sink.setMarkers(data.markers)
    if (data.equity.length) sink.setEquityLine(data.equity)
    else sink.clearEquityLine()
    sink.fit()
    currentIndex.value = total.value - 1
  }

  /** 元件卸載時清排程。 */
  function dispose(): void {
    clearTimer()
  }

  return {
    currentIndex: currentIndex as Ref<number>,
    total: total as Ref<number>,
    playing: playing as Ref<boolean>,
    speed: speed as Ref<number>,
    load,
    play,
    pause,
    setSpeed,
    scrub,
    replay,
    toEnd,
    dispose,
  }
}

export type ReplayPlayer = ReturnType<typeof useReplayPlayer>
