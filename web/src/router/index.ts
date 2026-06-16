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
    // 設計系統元件預覽 gallery(改版 S1b 建,S6 決議保留為內部 gallery):
    // lazy-load、不掛 header nav、不接 store/API,作為後續換皮卡的 living reference。
    {
      path: '/ui-preview',
      name: 'ui-preview',
      component: () => import('@/views/UiPreviewView.vue'),
    },
  ],
})

export default router
