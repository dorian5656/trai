// 文件名：frontend/src/types/chat.ts
// 作者：zcl
// 日期：2026-01-27
// 描述：聊天相关类型定义

export interface Message {
  id: string;
  role: 'user' | 'assistant' | 'system';
  content: string;
  timestamp: number;
  loading?: boolean; // 正在生成中
  error?: boolean;   // 发送失败
}

export interface ChatSession {
  id: string;
  title: string;
  messages: Message[];
  updatedAt: number;
}

export interface DifyConversation {
  id: string;
  name: string;
  inputs: Record<string, any>;
  status: string;
  introduction: string;
  created_at: number;
  updated_at: number;
  is_temp?: boolean;
}
