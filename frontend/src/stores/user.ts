// 文件名：frontend/src/stores/user.ts
// 作者：zcl
// 日期：2026-01-27
// 描述：用户状态管理 (Pinia)

import { defineStore } from 'pinia';
import { ref, computed } from 'vue';
import { login as loginApi, type LoginParams } from '@/api/auth';
import { getUserInfo, type UserInfo } from '@/api/user';
import { ElMessage } from 'element-plus';

export const useUserStore = defineStore('user', () => {
  // State
  const token = ref<string>(localStorage.getItem('token') || '');
  const userInfo = ref<UserInfo | null>(null);

  // Getters
  const isLoggedIn = computed(() => !!token.value);
  const username = computed(() => userInfo.value?.username || userInfo.value?.full_name || '未登录');
  const avatar = computed(() => userInfo.value?.avatar || '');

  // Actions
  /**
   * 登录
   */
  const login = async (loginForm: LoginParams) => {
    try {
      const res = await loginApi(loginForm);
      token.value = res.access_token;
      localStorage.setItem('token', res.access_token);
      
      // 登录成功后立即获取用户信息
      await fetchUserInfo();
      return true;
    } catch (error) {
      console.error('登录失败:', error);
      throw error;
    }
  };

  /**
   * 获取用户信息
   * 暂时直接从 Token 解析，不调用后端接口
   */
  const fetchUserInfo = async () => {
    if (!token.value) return;
    
    // 直接尝试从 Token 解析
    try {
      const parts = token.value.split('.');
      if (parts.length === 3) {
        const payload = JSON.parse(atob(parts[1]));
        if (payload && payload.sub) {
          userInfo.value = {
            id: 'local',
            username: payload.sub,
            full_name: payload.sub,
            is_active: true,
            is_superuser: false,
            created_at: new Date().toISOString()
          } as UserInfo;
          // console.log('已从 Token 本地解析用户信息');
          return;
        }
      }
    } catch (e) {
      console.error('Token 解析失败:', e);
    }

    // 如果 Token 解析失败，尝试调用接口作为备选 (或直接忽略)
    /*
    try {
      const info = await getUserInfo();
      userInfo.value = info;
    } catch (error) {
      console.error('获取用户信息失败:', error);
    }
    */
  };

  /**
   * 登出
   */
  const logout = () => {
    token.value = '';
    userInfo.value = null;
    localStorage.removeItem('token');
    ElMessage.success('已退出登录');
  };

  /**
   * 初始化（恢复会话）
   */
  const init = async () => {
    if (token.value && !userInfo.value) {
      await fetchUserInfo();
    }
  };

  return {
    token,
    userInfo,
    isLoggedIn,
    username,
    avatar,
    login,
    logout,
    fetchUserInfo,
    init,
  };
});
