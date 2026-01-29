// 文件名：frontend/src/router/index.ts
// 作者：zcl
// 日期：2026-01-27
// 描述：路由配置

import { createRouter, createWebHistory, type RouteRecordRaw } from 'vue-router';
import { isMobile } from '@/utils/device';

// 路由配置
const routes: RouteRecordRaw[] = [
  {
    path: '/',
    name: 'Root',
    redirect: () => {
      // ✅ 根据设备类型重定向到对应路径
      return isMobile() ? '/m' : '/pc';
    },
  },
  {
    path: '/login',
    name: 'Login',
    component: () => import('@/views/Login.vue'),
  },
  {
    path: '/pc',
    name: 'PCHome',
    component: () => import('@/views/pc/Home.vue'),
  },
  {
    path: '/m',
    name: 'MobileHome',
    component: () => import('@/views/mobile/Home.vue'),
  },
  {
    path: '/guanwang',
    name: 'SmartAssistant',
    component: () => import('@/views/SmartAssistant.vue'),
  },
];

const router = createRouter({
  history: createWebHistory(),
  routes,
});

// ✅ 简单的全局前置守卫，确保设备类型匹配（可选）
router.beforeEach((to, _from, next) => {
  const mobile = isMobile();
  if (to.path.startsWith('/pc') && mobile) {
    next('/m');
  } else if (to.path.startsWith('/m') && !mobile) {
    next('/pc');
  } else {
    next();
  }
});

export default router;
