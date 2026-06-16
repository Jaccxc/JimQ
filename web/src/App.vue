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
/* 全域 dark theme:深色底 + 淺色 base text,避免未顯式設色的文字(如 RunExplorerView
   的 h2/th/td)繼承瀏覽器黑色預設而在 #0e1117 上隱形(黑底黑字)。 */
body { font-family: system-ui, -apple-system, sans-serif; background: #0e1117; color: #d1d4dc; }
h1 { color: #e5e7eb; }
h2 { color: #e5e7eb; }
h3 { font-size: 12px; color: #9ca3af; margin: 0 0 6px; text-transform: uppercase; letter-spacing: 0.05em; }
</style>
