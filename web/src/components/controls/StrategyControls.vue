<script setup lang="ts">
/**
 * 卡 #24 (W5) — Live 頁的 Strategy 控制列。
 *
 * Start / Stop 目標策略 → 經 useStrategyControl 發控制命令到命令平面。狀態回饋
 * 顯示最近一次送出的命令(真實 RUNNING/STOPPED 狀態回流走既有 WS / 輪詢)。
 * control composable 可注入(測試決定論);預設用真實 REST client。
 *
 * 改版 S3:控制列玻璃化(L3 GlassToolbar)+ Apple 藍 start / 暖色 stop 按鈕 +
 * 節點狀態徽章 + 風控摘要。保留邏輯/store 綁定與 data-testid 不變。
 */
import { computed, inject } from 'vue'
import { useStrategyControl, type ControlApi } from '@/composables/useStrategyControl'
import { GlassToolbar } from '@/components/ui/glass'
import { Badge } from '@/components/ui/badge'

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
  <GlassToolbar class="strategy-controls" data-testid="strategy-controls">
    <span class="label">Strategy</span>
    <Badge variant="secondary" class="strategy-id">{{ props.strategyId }}</Badge>

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

    <Badge
      :variant="nodeStatus === 'KILLED' ? 'down' : 'up'"
      class="node-status"
      data-testid="node-status"
    >
      Node: {{ nodeStatus }}
    </Badge>

    <span class="risk-summary" data-testid="risk-summary" title="生效中的 Nautilus 原生風控">
      Risk: max notional {{ props.maxNotional }} USDT · rate {{ props.orderRateLimit }}
    </span>
  </GlassToolbar>
</template>

<style scoped>
.strategy-controls {
  border-radius: var(--radius-md);
  gap: calc(var(--spacing) * 2);
}
.label { font-size: 12px; color: var(--color-text-muted); }
.strategy-id { font-variant-numeric: tabular-nums; }
.ctl {
  font-size: 12px;
  font-weight: 600;
  padding: 5px 14px;
  border-radius: var(--radius-sm);
  cursor: pointer;
  border: 1px solid transparent;
  color: #fff;
  transition: opacity var(--duration-fast) var(--ease-glass),
    transform var(--duration-fast) var(--ease-glass);
}
.ctl:active:not(:disabled) { transform: scale(0.97); }
.ctl:disabled { cursor: not-allowed; opacity: 0.5; }
.start { background: var(--color-accent); }
.start:hover:not(:disabled) { opacity: 0.9; }
.stop {
  background: var(--color-down-pill);
  color: var(--color-down);
  border-color: rgba(255, 92, 92, 0.32);
}
.stop:hover:not(:disabled) { background: rgba(255, 92, 92, 0.24); }
.status {
  font-size: 11px;
  color: var(--color-text-faint);
  font-variant-numeric: tabular-nums;
}
.risk-summary {
  font-size: 11px;
  color: var(--color-text-muted);
  margin-left: auto;
  font-variant-numeric: tabular-nums;
}
</style>
