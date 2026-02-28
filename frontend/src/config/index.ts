// 文件名：frontend/src/config/index.ts
// 作者：whf
// 日期：2026-02-03
// 描述：全局配置管理

/**
 * 获取并规范化环境变量
 */
const getEnv = (key: string, defaultValue: string = ''): string => {
  return import.meta.env[key] || defaultValue;
};

/**
 * 规范化 URL (去除末尾斜杠)
 */
const normalizeUrl = (url: string): string => {
  return url.endsWith('/') ? url.slice(0, -1) : url;
};

// 服务端地址 (e.g. http://localhost:5777)
export const SERVER_URL = normalizeUrl(getEnv('VITE_APP_SERVER_URL', 'http://localhost:5777'));

// API 基础路径 (e.g. /api_trai/v1)
export const API_BASE_URL = getEnv('VITE_APP_BASE_URL', '/api_trai/v1');

// 完整的 API URL
export const API_URL = `${SERVER_URL}${API_BASE_URL.startsWith('/') ? API_BASE_URL : '/' + API_BASE_URL}`;

// WebSocket URL
export const WS_BASE_URL = SERVER_URL.replace(/^http/, 'ws');
