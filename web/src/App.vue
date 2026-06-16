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
   的 h2/th/td)繼承瀏覽器黑色預設而在深色底上隱形(黑底黑字)。
   改版 S2:背景/文字色改吃 theme.css token(仍為非黑,保 dark-theme 可見性契約)。
   改版(背景切換):背景移到 html[data-bg]::before 圖層(backgrounds.css),body 透明
   讓背景透出、玻璃面板得以顯現折射;文字色維持 token。 */
body { background: transparent; color: var(--color-text-muted); }
h1 { color: var(--color-text); }
h2 { color: var(--color-text); }
h3 { font-size: 12px; color: var(--color-text-muted); margin: 0 0 6px; text-transform: uppercase; letter-spacing: 0.05em; }
</style>
