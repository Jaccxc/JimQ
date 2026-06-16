<script setup lang="ts">
/**
 * 卡 #24 (W5) — Live 頁的 Strategy 控制列。
 *
 * Start / Stop 目標策略 → 經 useStrategyControl 發控制命令到命令平面。狀態回饋
 * 顯示最近一次送出的命令(真實 RUNNING/STOPPED 狀態回流走既有 WS / 輪詢)。
 * control composable 可注入(測試決定論);預設用真實 REST client。
 */
import { computed, inject } from 'vue'
import { useStrategyControl, type ControlApi } from '@/composables/useStrategyControl'

const props = withDefaults(
  defineProps<{
    strategyId?: string
    /** 生效中的名目上限(USDT);對齊 live 節點 DEFAULT_MAX_NOTIONAL_USDT。 */
    maxNotional?: number
    /** 生效中的下單頻率上限;對齊 live 節點 DEFAULT_MAX_ORDER_SUBMIT_RATE。 */
    orderRateLimit?: string
  }>(),
  {
    strategyId: 'ema_cross',
    maxNotional: 200,
    orderRateLimit: '10/00:00:01',
  },
)

const injectedApi = inject<Partial<ControlApi> | undefined>('strategyControlApi', undefined)
const control = useStrategyControl({ api: injectedApi })

// 節點狀態:全域 KILL 後為 KILLED,否則 RUNNING(復用 store 的 killed 旗標)。
const nodeStatus = computed(() => (control.store.killed ? 'KILLED' : 'RUNNING'))
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
    <span
      class="node-status"
      :class="{ killed: nodeStatus === 'KILLED' }"
      data-testid="node-status"
    >
      Node: {{ nodeStatus }}
    </span>
    <span class="risk-summary" data-testid="risk-summary" title="生效中的 Nautilus 原生風控">
      Risk: max notional {{ props.maxNotional }} USDT · rate {{ props.orderRateLimit }}
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
.node-status {
  font-size: 11px; font-weight: 600; padding: 2px 8px; border-radius: 4px;
  color: #86efac; background: #14532d33; border: 1px solid #166534;
}
.node-status.killed { color: #fca5a5; background: #7f1d1d33; border-color: #b91c1c; }
.risk-summary { font-size: 11px; color: #9ca3af; margin-left: auto; }
</style>
