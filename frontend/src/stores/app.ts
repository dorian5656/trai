// 文件名：frontend/src/stores/app.ts
// 作者：zcl
// 日期：2026-01-27
// 描述：应用全局状态管理 (Pinia)

import { defineStore } from 'pinia';
import { ref } from 'vue';

export const useAppStore = defineStore('app', () => {
  // ✅ 侧边栏状态
  const isSidebarOpen = ref(true); // PC 端默认展开
  const isMobileSidebarOpen = ref(false); // 移动端默认收起

  // ✅ 切换 PC 侧边栏
  const toggleSidebar = () => {
    isSidebarOpen.value = !isSidebarOpen.value;
  };

  // ✅ 切换移动端侧边栏
  const toggleMobileSidebar = () => {
    isMobileSidebarOpen.value = !isMobileSidebarOpen.value;
  };

  // ✅ 关闭移动端侧边栏（点击遮罩层时）
  const closeMobileSidebar = () => {
    isMobileSidebarOpen.value = false;
  };

  return {
    isSidebarOpen,
    isMobileSidebarOpen,
    toggleSidebar,
    toggleMobileSidebar,
    closeMobileSidebar,
  };
});
