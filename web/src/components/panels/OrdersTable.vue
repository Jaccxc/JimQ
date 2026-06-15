<script setup lang="ts">
import { useFillsStore } from '@/stores/fills'
const fills = useFillsStore()
</script>

<template>
  <div class="panel">
    <h3>成交 Fills</h3>
    <table data-testid="fills-table">
      <thead>
        <tr><th>Side</th><th>Qty</th><th>Px</th></tr>
      </thead>
      <tbody>
        <tr v-for="(f, i) in fills.fills.slice(-12).reverse()" :key="i">
          <td :class="f.order_side === 'BUY' ? 'long' : 'short'">{{ f.order_side }}</td>
          <td>{{ f.last_qty }}</td>
          <td>{{ f.last_px }}</td>
        </tr>
        <tr v-if="fills.fills.length === 0"><td colspan="3" class="empty">無成交</td></tr>
      </tbody>
    </table>
  </div>
</template>

<style scoped>
.panel { padding: 8px; }
table { width: 100%; border-collapse: collapse; font-size: 12px; }
th, td { text-align: left; padding: 4px 6px; border-bottom: 1px solid #1c2230; }
.long { color: #26a69a; }
.short { color: #ef5350; }
.empty { color: #6b7280; text-align: center; }
</style>
