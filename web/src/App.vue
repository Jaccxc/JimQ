<script setup lang="ts">
// 卡 #27 (P2-S1):tabbed shell 作為應用外殼(header nav + badge + KILL + WS)。
import AppShell from '@/components/AppShell.vue'
</script>

<template>
  <AppShell />
</template>

<style>
* { box-sizing: border-box; }
html, body, #app { margin: 0; height: 100%; }
body { font-family: system-ui, -apple-system, sans-serif; background: #0e1117; }
h3 { font-size: 12px; color: #9ca3af; margin: 0 0 6px; text-transform: uppercase; letter-spacing: 0.05em; }
</style>
