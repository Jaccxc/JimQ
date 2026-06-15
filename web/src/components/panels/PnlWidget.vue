<script setup lang="ts">
import { usePnlStore } from '@/stores/pnl'
const pnl = usePnlStore()
</script>

<template>
  <div class="panel pnl" data-testid="pnl-widget">
    <h3>權益 PnL</h3>
    <div class="equity">
      <span v-if="pnl.equity != null">{{ pnl.equity.toLocaleString() }}</span>
      <span v-else class="empty">—</span>
      <small v-if="pnl.latest"> {{ pnl.latest.base_currency }}</small>
    </div>
  </div>
</template>

<style scoped>
.panel { padding: 8px; }
.equity { font-size: 22px; font-weight: 600; color: #d1d4dc; }
.empty { color: #6b7280; }
</style>
