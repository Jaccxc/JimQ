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
.launcher { padding: 8px 12px; border-bottom: 1px solid #1c2230; }
.row { display: flex; gap: 8px; margin-bottom: 6px; flex-wrap: wrap; }
label { display: flex; flex-direction: column; font-size: 10px; color: #9ca3af; gap: 2px; }
input, select {
  background: #161b26; color: #d1d4dc; border: 1px solid #2a3142;
  border-radius: 4px; padding: 4px 6px; font-size: 12px;
}
input[type='number'] { width: 64px; }
.actions { display: flex; align-items: center; gap: 10px; }
button {
  background: #2563eb; color: #fff; border: none; border-radius: 4px;
  padding: 6px 14px; font-size: 12px; cursor: pointer;
}
button:disabled { opacity: 0.6; cursor: default; }
.status { font-size: 11px; color: #9ca3af; }
.status[data-status='COMPLETED'] { color: #22c55e; }
.status[data-status='FAILED'] { color: #ef4444; }
.status[data-status='RUNNING'], .status[data-status='PENDING'] { color: #eab308; }
.err { color: #ef4444; font-size: 11px; margin: 4px 0 0; }
</style>
