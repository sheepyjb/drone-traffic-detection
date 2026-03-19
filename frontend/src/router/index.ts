import { createRouter, createWebHistory } from 'vue-router'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    {
      path: '/',
      name: 'detection',
      component: () => import('@/views/DetectionView.vue'),
      meta: { title: '实时检测' },
    },
    {
      path: '/compare',
      name: 'compare',
      component: () => import('@/views/CompareView.vue'),
      meta: { title: '模型对比' },
    },
    {
      path: '/metrics',
      name: 'metrics',
      component: () => import('@/views/MetricsView.vue'),
      meta: { title: '评估指标' },
    },
    {
      path: '/map',
      name: 'map',
      component: () => import('@/views/MapView.vue'),
      meta: { title: '地图监控' },
    },
  ],
})

router.beforeEach((to) => {
  document.title = `${to.meta.title || '检测'} - 无人机目标检测系统`
})

export default router
