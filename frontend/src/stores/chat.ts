// 文件名：frontend/src/stores/chat.ts
// 作者：zcl
// 日期：2026-01-27
// 描述：聊天状态管理

import { defineStore } from 'pinia';
import { ref, computed } from 'vue';
import type { Message, ChatSession } from '@/types/chat';
import { v4 as uuidv4 } from 'uuid'; // 如果没有uuid库，可以使用简单生成函数

export const useChatStore = defineStore('chat', () => {
  // 当前会话 ID
  const currentSessionId = ref<string | null>(null);
  // 所有会话列表
  const sessions = ref<ChatSession[]>([]);
  // 正在生成消息的 AbortController (用于停止生成)
  const abortController = ref<AbortController | null>(null);

  // Dify 会话列表
  const difyConversations = ref<any[]>([]);
  // Dify 当前 conversation_id
  const difySessionId = ref<string | null>(null);

  // 添加临时会话到列表首部
  const addTempDifyConversation = (title: string = '新对话') => {
    const tempId = `temp-${Date.now()}`;
    const newConv = {
      id: tempId,
      name: title,
      inputs: {},
      status: 'normal',
      introduction: '',
      created_at: Date.now() / 1000,
      updated_at: Date.now() / 1000,
      is_temp: true // 标记为临时会话
    };
    difyConversations.value.unshift(newConv);
    return tempId;
  };

  // 更新临时会话为真实会话
  const updateTempDifyConversation = (tempId: string, realId: string) => {
    const index = difyConversations.value.findIndex(c => c.id === tempId);
    if (index !== -1) {
      difyConversations.value[index].id = realId;
      difyConversations.value[index].is_temp = false;
      // 如果当前选中的是临时 ID，也更新为真实 ID
      if (difySessionId.value === tempId) {
        difySessionId.value = realId;
      }
    }
  };

  // 获取当前会话
  const currentSession = computed(() => {
    return sessions.value.find(s => s.id === currentSessionId.value) || null;
  });

  // 获取当前消息列表
  const messages = computed(() => {
    return currentSession.value?.messages || [];
  });

  // 设置 Dify 会话 ID (用于继续对话)
  const setDifySessionId = (id: string | null) => {
    difySessionId.value = id;
    // 如果切换了会话，可能需要同步 UI 状态，这里暂不处理复杂逻辑
  };

  // 创建新会话
  const createSession = (title: string = '新对话') => {
    const newSession: ChatSession = {
      id: Date.now().toString(), // 简单ID生成
      title,
      messages: [],
      updatedAt: Date.now(),
    };
    sessions.value.unshift(newSession);
    currentSessionId.value = newSession.id;
    // 重置 Dify 会话 ID
    difySessionId.value = null;
    return newSession;
  };

  // 切换会话
  const switchSession = (id: string) => {
    currentSessionId.value = id;
  };

  // 添加消息
  const addMessage = (role: 'user' | 'assistant', content: string) => {
    if (!currentSessionId.value) {
      createSession();
    }
    const session = sessions.value.find(s => s.id === currentSessionId.value);
    if (session) {
      const msg: Message = {
        id: Date.now().toString() + Math.random(),
        role,
        content,
        timestamp: Date.now(),
      };
      session.messages.push(msg);
      session.updatedAt = Date.now();
      return msg;
    }
    return null;
  };

  // 更新最后一条消息内容 (用于流式输出)
  const updateLastMessage = (content: string) => {
    if (messages.value.length > 0) {
      const lastMsg = messages.value[messages.value.length - 1];
      if (lastMsg && lastMsg.role === 'assistant') {
        lastMsg.content = content;
      }
    }
  };

  // 清空会话
  const clearSession = () => {
     if (currentSessionId.value) {
       const session = sessions.value.find(s => s.id === currentSessionId.value);
       if(session) session.messages = [];
     }
  };

  return {
    currentSessionId,
    sessions,
    currentSession,
    messages,
    createSession,
    switchSession,
    addMessage,
    updateLastMessage,
    abortController,
    clearSession,
    difyConversations,
    difySessionId,
    setDifySessionId,
    addTempDifyConversation,
    updateTempDifyConversation
  };
});
