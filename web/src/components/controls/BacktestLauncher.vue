<script setup lang="ts">
/**
 * 卡 #20 (W1) — backtest launcher 表單。
 *
 * 使用者填 symbol/timeframe/strategy/params(fast/slow period)/start/end →
 * 送出 → useBacktestLauncher.launch(POST /backtests/run)→ 取 run_id →
 * 顯示 run 狀態(由 backtestRun store 反映;Dashboard 在 active 時訂 WS 即時看
 * K 線與進出場長出來)。
 *
 * 提交成功會 emit('launched', runId),讓父層(Dashboard)開始訂 WS / 輪詢狀態。
 */
import { ref } from 'vue'
import { useBacktestLauncher } from '@/composables/useBacktestLauncher'
import { useBacktestRunStore } from '@/stores/backtestRun'

const emit = defineEmits<{ (e: 'launched', runId: number): void }>()

const TIMEFRAMES = ['1m', '5m', '15m', '30m', '1h', '4h', '1d']
const STRATEGIES = ['ema_cross']

const symbol = ref('BTCUSDT-PERP.BINANCE')
const timeframe = ref('1m')
const strategy = ref('ema_cross')
const fastPeriod = ref(3)
const slowPeriod = ref(8)
const start = ref('2023-11-14T22:13')
const end = ref('2023-11-14T22:46')

const submitting = ref(false)
const launcher = useBacktestLauncher()
const runStore = useBacktestRunStore()

function toIso(local: string): string {
  // datetime-local 無時區;以 UTC 解讀(後端契約 timezone-aware)。
  return new Date(`${local}:00Z`).toISOString()
}

async function onSubmit() {
  submitting.value = true
  try {
    const runId = await launcher.launch({
      symbol: symbol.value,
      timeframe: timeframe.value,
      strategy: strategy.value,
      params: { fast_period: fastPeriod.value, slow_period: slowPeriod.value },
      start: toIso(start.value),
      end: toIso(end.value),
    })
    emit('launched', runId)
  } catch {
    // 錯誤已寫進 store(status=FAILED);UI 由 store 反映。
  } finally {
    submitting.value = false
  }
}
</script>

<template>
  <form class="launcher" @submit.prevent="onSubmit">
    <h3>Run backtest</h3>
    <div class="row">
      <label>Symbol<input v-model="symbol" /></label>
      <label>
        Timeframe
        <select v-model="timeframe">
          <option v-for="tf in TIMEFRAMES" :key="tf" :value="tf">{{ tf }}</option>
        </select>
      </label>
      <label>
        Strategy
        <select v-model="strategy">
          <option v-for="s in STRATEGIES" :key="s" :value="s">{{ s }}</option>
        </select>
      </label>
    </div>
    <div class="row">
      <label>Fast<input v-model.number="fastPeriod" type="number" min="1" /></label>
      <label>Slow<input v-model.number="slowPeriod" type="number" min="2" /></label>
    </div>
    <div class="row">
      <label>Start<input v-model="start" type="datetime-local" /></label>
      <label>End<input v-model="end" type="datetime-local" /></label>
    </div>
    <div class="actions">
      <button type="submit" :disabled="submitting">
        {{ submitting ? 'Launching…' : 'Run' }}
      </button>
      <span class="status" :data-status="runStore.status">
        {{ runStore.status }}<template v-if="runStore.runId"> · #{{ runStore.runId }}</template>
      </span>
    </div>
    <p v-if="runStore.error" class="err">{{ runStore.error }}</p>
  </form>
</template>

<style scoped>
/* 改版 S4:launcher 表單玻璃化(L1 面板)。token 來自 styles/theme.css。 */
.launcher {
  padding: calc(var(--spacing) * 4) calc(var(--spacing) * 4);
  background: var(--glass-l1-bg);
  border: 1px solid var(--glass-l1-border);
  border-radius: var(--radius-md);
  box-shadow: var(--glass-l1-shadow), var(--glass-l1-highlight);
  backdrop-filter: blur(var(--glass-l1-blur)) saturate(var(--glass-l1-saturate));
  -webkit-backdrop-filter: blur(var(--glass-l1-blur)) saturate(var(--glass-l1-saturate));
}
@supports not (backdrop-filter: blur(1px)) {
  .launcher { background: var(--glass-fallback-bg); }
}
.launcher h3 {
  margin: 0 0 calc(var(--spacing) * 3);
  font-size: 13px;
  font-weight: 600;
  color: var(--color-text);
  letter-spacing: -0.01em;
}
.row { display: flex; gap: calc(var(--spacing) * 2); margin-bottom: calc(var(--spacing) * 2); flex-wrap: wrap; }
label {
  display: flex; flex-direction: column; gap: calc(var(--spacing) * 1);
  font-size: 10px; color: var(--color-text-muted);
}
input, select {
  background: rgba(11, 14, 20, 0.5);
  color: var(--color-text);
  border: 1px solid var(--glass-l1-border);
  border-radius: var(--radius-xs);
  padding: 5px 7px; font-size: 12px;
  transition: border-color var(--duration-fast) var(--ease-glass),
    box-shadow var(--duration-fast) var(--ease-glass);
}
input:focus, select:focus {
  outline: none;
  border-color: var(--color-accent);
  box-shadow: 0 0 0 1px var(--color-accent);
}
input[type='number'] { width: 64px; }
.actions { display: flex; align-items: center; gap: calc(var(--spacing) * 3); margin-top: calc(var(--spacing) * 1); }
button {
  background: var(--color-accent); color: #fff; border: none;
  border-radius: var(--radius-sm);
  padding: 6px 16px; font-size: 12px; font-weight: 600; cursor: pointer;
  transition: opacity var(--duration-fast) var(--ease-glass),
    transform var(--duration-fast) var(--ease-glass);
}
button:hover:not(:disabled) { opacity: 0.9; }
button:active:not(:disabled) { transform: scale(0.97); }
button:disabled { opacity: 0.5; cursor: default; }
.status { font-size: 11px; color: var(--color-text-muted); font-variant-numeric: tabular-nums; }
.status[data-status='COMPLETED'] { color: var(--color-up); }
.status[data-status='FAILED'] { color: var(--color-down); }
.status[data-status='RUNNING'], .status[data-status='PENDING'] { color: var(--color-accent); }
.err { color: var(--color-down); font-size: 11px; margin: calc(var(--spacing) * 1) 0 0; }
</style>
