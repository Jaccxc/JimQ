<script setup lang="ts">
import { usePositionsStore } from '@/stores/positions'
const positions = usePositionsStore()
</script>

<template>
  <div class="panel">
    <h3>部位 Positions</h3>
    <table data-testid="positions-table">
      <thead>
        <tr><th>ID</th><th>Side</th><th>Qty</th><th>Avg Px</th><th>Last Px</th></tr>
      </thead>
      <tbody>
        <tr v-for="p in positions.positions" :key="p.position_id">
          <td>{{ p.position_id }}</td>
          <td :class="p.side === 'LONG' ? 'long' : 'short'">{{ p.side }}</td>
          <td>{{ p.quantity }}</td>
          <td>{{ p.avg_px_open }}</td>
          <td>{{ p.last_px }}</td>
        </tr>
        <tr v-if="positions.positions.length === 0">
          <td colspan="5" class="empty">無持倉</td>
        </tr>
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
