// 文件名：frontend/src/stores/user.ts
// 作者：zcl
// 日期：2026-01-27
// 描述：用户状态管理 (Pinia)

import { defineStore } from 'pinia';
import { ref, computed } from 'vue';
import { login as loginApi, wecomLogin as wecomLoginApi, type LoginParams } from '@/api/auth';
import { getUserInfo, type UserInfo } from '@/api/user';
import { ElMessage } from 'element-plus';
import { useAppStore } from './app';

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
      if (!res || !res.access_token) {
        throw new Error('登录响应格式错误: 缺少 access_token');
      }
      token.value = res.access_token;
      localStorage.setItem('token', res.access_token);
      
      // 登录成功后立即获取用户信息
      await fetchUserInfo();
      
      // 关闭登录模态框
      const appStore = useAppStore();
      appStore.closeLoginModal();
      
      return true;
    } catch (error) {
      console.error('登录失败:', error);
      throw error;
    }
  };

  /**
   * 企业微信登录
   */
  const loginByWecom = async (code: string) => {
    try {
      const res = await wecomLoginApi(code);
      if (!res || !res.access_token) {
        throw new Error('登录响应格式错误: 缺少 access_token');
      }
      token.value = res.access_token;
      localStorage.setItem('token', res.access_token);
      
      // 登录成功后立即获取用户信息
      await fetchUserInfo();
      
      // 关闭登录模态框
      const appStore = useAppStore();
      appStore.closeLoginModal();
      
      return true;
    } catch (error) {
      console.error('企业微信登录失败:', error);
      throw error;
    }
  };

  /**
   * 获取用户信息
   */
  const fetchUserInfo = async () => {
    if (!token.value) return;
    
    try {
      // 优先从后端接口获取完整信息
      const info = await getUserInfo();
      userInfo.value = info;
    } catch (error) {
      console.error('获取用户信息失败, 尝试本地解析:', error);
      
      // 接口调用失败时，尝试从 Token 解析 (降级方案)
      try {
        const parts = token.value.split('.');
        if (parts.length === 3 && parts[1]) {
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
          }
        }
      } catch (e) {
        console.error('Token 本地解析也失败:', e);
      }
    }
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
    if (!token.value) return;
    const exp = getTokenExp(token.value);
    if (exp && exp * 1000 <= Date.now()) {
      token.value = '';
      userInfo.value = null;
      localStorage.removeItem('token');
      return;
    }
    // 先从 Token 解析用户以减少“未登录”闪烁
    if (!userInfo.value) {
      try {
        const parts = token.value.split('.');
        if (parts.length === 3 && parts[1]) {
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
          }
        }
      } catch {}
    }
    if (!userInfo.value) await fetchUserInfo();
  };

  const getTokenExp = (t: string): number | null => {
    try {
      const p = JSON.parse(atob(t.split('.')[1]));
      return typeof p.exp === 'number' ? p.exp : null;
    } catch {
      return null;
    }
  };


  return {
    token,
    userInfo,
    isLoggedIn,
    username,
    avatar,
    login,
    loginByWecom,
    logout,
    fetchUserInfo,
    init,
  };
});
