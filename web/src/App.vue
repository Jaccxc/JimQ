<script setup lang="ts"></script>

<template>
  <nav class="topnav">
    <RouterLink to="/">Dashboard</RouterLink>
    <RouterLink to="/explorer">Backtest Explorer</RouterLink>
  </nav>
  <RouterView />
</template>

<style>
* { box-sizing: border-box; }
html, body, #app { margin: 0; height: 100%; }
body { font-family: system-ui, -apple-system, sans-serif; background: #0e1117; }
h3 { font-size: 12px; color: #9ca3af; margin: 0 0 6px; text-transform: uppercase; letter-spacing: 0.05em; }
.topnav { display: flex; gap: 16px; padding: 8px 14px; background: #11151d; border-bottom: 1px solid #1c2230; }
.topnav a { color: #9ca3af; text-decoration: none; font-size: 13px; }
.topnav a.router-link-active { color: #e5e7eb; font-weight: 600; }
</style>
