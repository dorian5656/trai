<!--
文件名：frontend/src/views/Login.vue
作者：zcl
日期：2026-02-04
描述：用户登录页面 (已废弃，重定向到首页并打开登录模态框)
-->

<script setup lang="ts">
import { onMounted } from 'vue';
import { useRouter, useRoute } from 'vue-router';
import { useAppStore } from '@/stores/app';

const router = useRouter();
const route = useRoute();
const appStore = useAppStore();

onMounted(() => {
  // 保留查询参数（如企业微信回调 code）
  router.replace({ path: '/', query: route.query });
  // 打开登录模态框
  appStore.openLoginModal();
});
</script>

<template>
  <div class="login-redirect">正在跳转...</div>
</template>

<style scoped>
.login-redirect {
  display: flex;
  justify-content: center;
  align-items: center;
  height: 100vh;
  font-size: 1rem;
  color: #606266;
}
</style>
