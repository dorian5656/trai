// 文件名：frontend/src/api/dify.ts
// 作者：zcl
// 日期：2026-01-28
// 描述：Dify AI 接口封装

import request from '@/utils/request';

export interface DifyConversation {
  id: string;
  name: string;
  inputs: Record<string, any>;
  status: string;
  introduction: string;
  created_at: number;
  updated_at: number;
}

export interface DifyConversationListResponse {
  data: DifyConversation[];
  has_more: boolean;
  limit: number;
}

/**
 * 获取 Dify 会话列表
 * @param user 用户标识
 * @param limit 限制数量
 * @param app_name 应用名称 (默认 guanwang)
 */
export const fetchDifyConversations = (user: string, limit: number = 20, app_name: string = 'guanwang') => {
  return request.get<DifyConversationListResponse>('/dify/conversations', {
    params: { user, limit, app_name }
  });
};

/**
 * 官网专用公开对话接口 (流式)
 * URL: /dify/chat/public
 */
export const publicChatUrl = '/dify/chat/public';
