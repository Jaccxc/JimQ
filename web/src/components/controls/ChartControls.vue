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
/* 改版 S3:圖表控制列玻璃化(L3)。token 來自 styles/theme.css。
 * EMA dot 顏色刻意保留(對齊 CandleChart 疊圖線色,非通用漲跌)。 */
.chart-controls {
  display: flex;
  align-items: center;
  gap: calc(var(--spacing) * 4);
  padding: calc(var(--spacing) * 2) calc(var(--spacing) * 3);
  border-radius: var(--radius-md);
  flex-wrap: wrap;
  background: var(--glass-l3-bg);
  border: 1px solid var(--glass-l1-border);
  box-shadow: var(--glass-l1-highlight);
  backdrop-filter: blur(var(--glass-l3-blur)) saturate(var(--glass-l1-saturate));
  -webkit-backdrop-filter: blur(var(--glass-l3-blur)) saturate(var(--glass-l1-saturate));
}
@supports not (backdrop-filter: blur(1px)) {
  .chart-controls { background: var(--glass-fallback-bg); }
}
.ctl {
  display: inline-flex;
  align-items: center;
  gap: calc(var(--spacing) * 1.5);
  color: var(--color-text-muted);
  font-size: 12px;
}
.ctl select,
.ctl input[type='number'] {
  background: var(--field-bg);
  color: var(--color-text);
  border: 1px solid var(--glass-l1-border);
  border-radius: var(--radius-xs);
  padding: 3px 7px;
  font-size: 12px;
  font-variant-numeric: tabular-nums;
  transition: border-color var(--duration-fast) var(--ease-glass),
    box-shadow var(--duration-fast) var(--ease-glass);
}
.ctl select:focus,
.ctl input[type='number']:focus {
  outline: none;
  border-color: var(--color-accent);
  box-shadow: 0 0 0 1px var(--color-accent);
}
.ctl input[type='number'] {
  width: 48px;
}
.ema-dot {
  width: 10px;
  height: 2px;
  display: inline-block;
}
.ema-dot.fast { background: var(--ema-fast); }
.ema-dot.slow { background: var(--ema-slow); }
</style>
