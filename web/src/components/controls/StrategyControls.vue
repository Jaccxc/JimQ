<script setup lang="ts">
/**
 * 卡 #24 (W5) — Live 頁的 Strategy 控制列。
 *
 * Start / Stop 目標策略 → 經 useStrategyControl 發控制命令到命令平面。狀態回饋
 * 顯示最近一次送出的命令(真實 RUNNING/STOPPED 狀態回流走既有 WS / 輪詢)。
 * control composable 可注入(測試決定論);預設用真實 REST client。
 */
import { inject } from 'vue'
import { useStrategyControl, type ControlApi } from '@/composables/useStrategyControl'

const props = withDefaults(defineProps<{ strategyId?: string }>(), {
  strategyId: 'ema_cross',
})

const injectedApi = inject<Partial<ControlApi> | undefined>('strategyControlApi', undefined)
const control = useStrategyControl({ api: injectedApi })
</script>

<template>
  <div class="strategy-controls" data-testid="strategy-controls">
    <span class="label">Strategy: {{ props.strategyId }}</span>
    <button
      class="ctl start"
      type="button"
      :disabled="control.pending.value"
      data-testid="strategy-start"
      @click="control.start(props.strategyId)"
    >
      Start
    </button>
    <button
      class="ctl stop"
      type="button"
      :disabled="control.pending.value"
      data-testid="strategy-stop"
      @click="control.stop(props.strategyId)"
    >
      Stop
    </button>
    <span v-if="control.store.lastCommand" class="status" data-testid="strategy-status">
      {{ control.store.lastCommand.command_type }}
    </span>
  </div>
</template>

<style scoped>
.strategy-controls {
  display: flex; align-items: center; gap: 8px;
  padding: 6px 12px; border-bottom: 1px solid #1c2230;
}
.label { font-size: 12px; color: #9ca3af; }
.ctl {
  font-size: 11px; font-weight: 600; padding: 3px 10px; border-radius: 4px;
  cursor: pointer; border: 1px solid #334155; background: #1f2937; color: #d1d4dc;
}
.ctl:disabled { cursor: not-allowed; opacity: 0.6; }
.start:hover:not(:disabled) { background: #14532d; color: #86efac; border-color: #166534; }
.stop:hover:not(:disabled) { background: #422006; color: #fbbf24; border-color: #b45309; }
.status { font-size: 11px; color: #6b7280; }
</style>
