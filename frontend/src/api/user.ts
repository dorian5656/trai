// 文件名：frontend/src/api/user.ts
// 作者：zcl
// 日期：2026-01-27
// 描述：用户相关接口

import request from '@/utils/request';

export interface UserInfo {
  id: string;
  username: string;
  full_name?: string;
  email?: string;
  phone?: string;
  avatar?: string;
  is_active: boolean;
  is_superuser: boolean;
  department_id?: string;
  created_at: string;
}

/**
 * 获取当前用户信息
 */
export const getUserInfo = () => {
  return request.get<any, UserInfo>('/users/me');
};

/**
 * 获取用户列表 (仅管理员)
 */
export const getUsers = (params: { skip?: number; limit?: number } = {}) => {
  return request.get<any, UserInfo[]>('/users/', { params });
};

export interface UserAuditParams {
  username: string;
  is_active: boolean;
  remark?: string;
}

/**
 * 审核用户 (仅管理员)
 */
export const auditUser = (data: UserAuditParams) => {
  return request.post<any, any>('/users/audit', data);
};

export interface PasswordChangeParams {
  old_password: string;
  new_password: string;
  reason: string;
}

/**
 * 修改密码
 */
export const changePassword = (data: PasswordChangeParams) => {
  return request.post<any, any>('/users/change-password', data);
};
