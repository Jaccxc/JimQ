import { createRouter, createWebHistory } from 'vue-router'
import DashboardView from '@/views/DashboardView.vue'

export const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/', name: 'dashboard', component: DashboardView },
    // 卡 #21 (W2):Backtest 結果瀏覽器(歷史 run 列表 + 重載圖)。lazy-load。
    {
      path: '/explorer',
      name: 'explorer',
      component: () => import('@/views/RunExplorerView.vue'),
    },
  ],
})

export default router
