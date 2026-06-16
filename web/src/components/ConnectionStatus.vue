<script setup lang="ts">
/**
 * WS 連線狀態指示。改版 S2:玻璃 pill + 狀態色點(綠=連上/live、黃=連線中、紅=斷線)。
 * 保留 store 綁定與 data-testid 不變;只換外觀(吃 theme.css token)。
 */
import { useConnectionStore } from '@/stores/connection'
const conn = useConnectionStore()
</script>

<template>
  <div class="conn" :data-status="conn.status" data-testid="conn-status">
    <span class="dot" :class="conn.status"></span>
    <span class="label">{{ conn.status }}</span>
    <small v-if="conn.lastSeq" class="meta">seq {{ conn.lastSeq }}</small>
    <small v-if="conn.reconnectAttempts" class="meta">retry {{ conn.reconnectAttempts }}</small>
  </div>
</template>

<style scoped>
.conn {
  display: inline-flex;
  align-items: center;
  gap: calc(var(--spacing) * 1.5);
  font-size: 12px;
  font-weight: 500;
  color: var(--color-text-muted);
  padding: calc(var(--spacing) * 1) calc(var(--spacing) * 2.5);
  border-radius: var(--radius-xs);
  border: 1px solid var(--glass-l1-border);
  background: rgba(255, 255, 255, 0.04);
  text-transform: capitalize;
}

.dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: var(--color-text-faint);
  box-shadow: 0 0 0 2px rgba(255, 255, 255, 0.04);
}

/* 連上 / live = 漲色(綠);實心點不在玻璃疊半透明色塊(契約)。 */
.dot.connected,
.dot.live {
  background: var(--color-up);
  box-shadow: 0 0 6px rgba(38, 208, 124, 0.5);
}

.dot.connecting {
  background: #f0b90b;
  box-shadow: 0 0 6px rgba(240, 185, 11, 0.5);
}

.dot.disconnected {
  background: var(--color-down);
  box-shadow: 0 0 6px rgba(255, 92, 92, 0.5);
}

.meta {
  color: var(--color-text-faint);
  font-variant-numeric: tabular-nums;
}
</style>
