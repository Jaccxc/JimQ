<script setup lang="ts">
import { useConnectionStore } from '@/stores/connection'
const conn = useConnectionStore()
</script>

<template>
  <div class="conn" :data-status="conn.status" data-testid="conn-status">
    <span class="dot" :class="conn.status"></span>
    <span class="label">{{ conn.status }}</span>
    <small v-if="conn.lastSeq">seq {{ conn.lastSeq }}</small>
    <small v-if="conn.reconnectAttempts">retry {{ conn.reconnectAttempts }}</small>
  </div>
</template>

<style scoped>
.conn { display: flex; align-items: center; gap: 8px; font-size: 12px; color: #d1d4dc; }
.dot { width: 8px; height: 8px; border-radius: 50%; background: #6b7280; }
.dot.connected, .dot.live { background: #26a69a; }
.dot.connecting { background: #f0b90b; }
.dot.disconnected { background: #ef5350; }
</style>
