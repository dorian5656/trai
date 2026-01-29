// 文件名：frontend/src/utils/request.ts
// 作者：zcl
// 日期：2026-01-27
// 描述：Axios 网络请求封装

import axios, { type AxiosInstance, type AxiosResponse } from 'axios';
import { ElMessage } from 'element-plus';
import 'element-plus/es/components/message/style/css';

// ✅ 创建 axios 实例
const service: AxiosInstance = axios.create({
  baseURL: import.meta.env.VITE_APP_MAIN_URL || '/api', // 环境变量
  timeout: 100000,
  headers: { 'Content-Type': 'application/json;charset=utf-8' },
});

// ✅ 请求拦截器
service.interceptors.request.use(
  (config) => {
    // 注入 token
    const token = localStorage.getItem('token');
    if (token) {
      config.headers.Authorization = `Bearer ${token}`;
    }
    return config;
  },
  (error) => {
    console.error('❌ 请求错误:', error);
    return Promise.reject(error);
  }
);

// ✅ 响应拦截器
service.interceptors.response.use(
  (response: AxiosResponse) => {
    // 兼容 OAuth2 标准响应 (直接返回 { access_token, token_type })
    if (response.data && response.data.access_token) {
      return response.data;
    }

    // 兼容直接返回 JSON 对象的接口 (如 uploadFile 返回 { url, filename, ... })
    // 如果 response.data 没有 code 字段，但有 url/filename 等业务字段，视为成功
    if (response.data && response.data.url && !response.data.code) {
      return response.data;
    }

    const { code, msg, data } = response.data;
    // 假设 200 为成功
    if (code === 200) {
      return data; // 自动解包
    } else {
      // 某些接口可能直接返回数据结构，没有 code 包装
      // 如果后端返回的是标准的 Pydantic Model (如 UploadResponse)，可能没有 code 字段
      // 这种情况下，如果 status 是 200，则直接返回 data
      if (response.status === 200 && !code) {
         return response.data;
      }

      const errorMessage = msg || '请求失败';
      console.error(`❌ 接口异常: ${errorMessage}`);
      ElMessage.error(errorMessage);
      return Promise.reject(new Error(errorMessage));
    }
  },
  (error) => {
    console.error('❌ 网络错误:', error);
    ElMessage.error(error.message || '网络连接异常');
    return Promise.reject(error);
  }
);

export default service;
