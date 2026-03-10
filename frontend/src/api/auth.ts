// 文件名：frontend/src/api/auth.ts
// 作者：zcl
// 日期：2026-01-27
// 描述：认证相关接口

import request from '@/utils/request';

export interface LoginParams {
  username: string;
  password: string;
}

export interface LoginResult {
  access_token: string;
  token_type: string;
}

/**
 * 登录接口
 * @param data 登录参数
 */
export const login = (data: LoginParams) => {
  // OAuth2PasswordRequestForm 标准要求 application/x-www-form-urlencoded
  // 使用 URLSearchParams 来构建请求体
  const params = new URLSearchParams();
  params.append('username', data.username);
  params.append('password', data.password);

  return request.post<any, LoginResult>('/auth/login', params, {
    headers: {
      'Content-Type': 'application/x-www-form-urlencoded',
    },
  });
};

export interface RegisterParams {
  username: string;
  password: string;
  full_name?: string;
  email?: string;
  phone?: string;
}

/**
 * 用户注册接口
 * @param data 注册参数
 */
export const register = (data: RegisterParams) => {
  return request.post<any, any>('/auth/register', data);
};

/**
 * 企业微信静默登录
 * @param code OAuth2 code
 */
export const wecomLogin = (code: string) => {
  return request.post<any, LoginResult>('/auth/wecom-login', { code });
};
