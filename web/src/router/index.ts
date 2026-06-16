import { createRouter, createWebHistory } from 'vue-router'

// 卡 #27 (P2-S1) tabbed shell IA:頂部分頁籤 Live / Backtest / Research。
// 根路徑重導向到 Live(預設首頁 = 即時)。Live 為主視圖直接載入,其餘 lazy-load。
import LiveView from '@/views/LiveView.vue'

export const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/', redirect: '/live' },
    { path: '/live', name: 'live', component: LiveView },
    {
      path: '/backtest',
      name: 'backtest',
      component: () => import('@/views/BacktestView.vue'),
    },
    {
      path: '/research',
      name: 'research',
      component: () => import('@/views/ResearchView.vue'),
    },
  ],
})

export default router
