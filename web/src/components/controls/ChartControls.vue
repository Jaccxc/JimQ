<script setup lang="ts">
/**
 * 圖表控制列:標的選擇器 + 時間週期選擇器 + EMA fast/slow 疊圖開關與週期。
 *
 * 切換 symbol/timeframe → emit('switch', {symbol, timeframe}),由 DashboardView
 * 委派 useChartData.switchTo(重載 bars + 重訂串流)。EMA 設定直接寫 chartSettings
 * store(CandleChart watcher 命令式套用)。
 *
 * 可選清單受限 catalog 已灌資料(目前主要 BTCUSDT-PERP;灌更多見
 * docs/web-chart-symbols.md)。
 */
import { useChartSettingsStore } from '@/stores/chartSettings'

const settings = useChartSettingsStore()

const emit = defineEmits<{
  (e: 'switch', sel: { symbol: string; timeframe: string }): void
}>()

function onSymbol(ev: Event) {
  const value = (ev.target as HTMLSelectElement).value
  emit('switch', { symbol: value, timeframe: settings.timeframe })
}
function onTimeframe(ev: Event) {
  const value = (ev.target as HTMLSelectElement).value
  emit('switch', { symbol: settings.symbol, timeframe: value })
}
</script>

<template>
  <div class="chart-controls" data-testid="chart-controls">
    <label class="ctl">
      <span>標的</span>
      <select
        data-testid="symbol-select"
        :value="settings.symbol"
        @change="onSymbol"
      >
        <option v-for="s in settings.symbols" :key="s.value" :value="s.value">
          {{ s.label }}
        </option>
      </select>
    </label>

    <label class="ctl">
      <span>週期</span>
      <select
        data-testid="timeframe-select"
        :value="settings.timeframe"
        @change="onTimeframe"
      >
        <option v-for="tf in settings.timeframes" :key="tf" :value="tf">
          {{ tf }}
        </option>
      </select>
    </label>

    <label class="ctl ema">
      <input
        type="checkbox"
        data-testid="ema-fast-toggle"
        :checked="settings.emaFast.enabled"
        @change="settings.toggleEmaFast(($event.target as HTMLInputElement).checked)"
      />
      <span class="ema-dot fast"></span>
      <span>EMA</span>
      <input
        type="number"
        min="1"
        data-testid="ema-fast-period"
        :value="settings.emaFast.period"
        @change="settings.setEmaFastPeriod(Number(($event.target as HTMLInputElement).value))"
      />
    </label>

    <label class="ctl ema">
      <input
        type="checkbox"
        data-testid="ema-slow-toggle"
        :checked="settings.emaSlow.enabled"
        @change="settings.toggleEmaSlow(($event.target as HTMLInputElement).checked)"
      />
      <span class="ema-dot slow"></span>
      <span>EMA</span>
      <input
        type="number"
        min="1"
        data-testid="ema-slow-period"
        :value="settings.emaSlow.period"
        @change="settings.setEmaSlowPeriod(Number(($event.target as HTMLInputElement).value))"
      />
    </label>
  </div>
</template>

<style scoped>
.chart-controls {
  display: flex;
  align-items: center;
  gap: 16px;
  padding: 6px 12px;
  border-bottom: 1px solid #1c2230;
  background: #0e1117;
  flex-wrap: wrap;
}
.ctl {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  color: #d1d4dc;
  font-size: 12px;
}
.ctl select,
.ctl input[type='number'] {
  background: #161b22;
  color: #d1d4dc;
  border: 1px solid #2a3140;
  border-radius: 4px;
  padding: 2px 6px;
  font-size: 12px;
}
.ctl input[type='number'] {
  width: 48px;
}
.ema-dot {
  width: 10px;
  height: 2px;
  display: inline-block;
}
.ema-dot.fast { background: #42a5f5; }
.ema-dot.slow { background: #ffa726; }
</style>
