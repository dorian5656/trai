// 文件名：frontend/src/stores/chat.ts
// 作者：zcl
// 日期：2026-01-27
// 描述：聊天状态管理

import { defineStore } from 'pinia';
import { ref, computed } from 'vue';
import type { Message, ChatSession, DifyConversation } from '@/types/chat';
import { v4 as uuidv4 } from 'uuid';
import { generateImage } from '@/api/image';
import { streamDifyChat } from '@/utils/stream';
import { ErrorHandler } from '@/utils/errorHandler';
import { ElMessage } from 'element-plus';
import { useUserStore } from '@/stores/user';
import type { UploadFile } from '@/composables/useFileUpload';
import type { Skill } from '@/composables/useSkills';

export const useChatStore = defineStore('chat', () => {
  // 当前会话 ID
  const currentSessionId = ref<string | null>(null);
  // 所有会话列表
  const sessions = ref<ChatSession[]>([]);
  // 正在生成消息的 AbortController (用于停止生成)
  const abortController = ref<AbortController | null>(null);
  // 是否正在发送/生成中
  const isSending = ref(false);

  // Dify 会话列表
  const difyConversations = ref<DifyConversation[]>([]);
  // Dify 当前 conversation_id
  const difySessionId = ref<string | null>(null);

  // 添加临时会话到列表首部
  const addTempDifyConversation = (title: string = '新对话') => {
    const tempId = `temp-${Date.now()}`;
    const newConv: DifyConversation = {
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

  // 发送消息核心逻辑
  const sendMessage = async (
    content: string, 
    files: UploadFile[] = [], 
    skill: Skill | null = null,
    onConversationCreated?: () => void
  ) => {
    // 1. 构造完整内容
    let fullContent = content;
    if (skill) {
      fullContent = `${skill.label} ${content}`;
    }
    
    if (files.length > 0) {
      const fileNames = files.map(f => `[文件: ${f.name}]`).join(' ');
      fullContent = `${fileNames} ${fullContent}`;
    }

    // 2. 添加用户消息
    addMessage('user', fullContent);
    isSending.value = true;

    // 3. 处理图像生成技能
    if (skill && skill.label === '图像生成' && content) {
      // 添加 AI 占位消息
      addMessage('assistant', '正在生成图片...');
      
      try {
        // 调用图像生成接口
        const result = await generateImage({
          prompt: content,
          model: 'Z-Image',
          size: '512x512'
        });
        
        // 处理返回结果
        let imageUrl: string | null = null;
        
        // 情况1: 直接返回完整的 ImageGenResponse
        if (result && (result as any).data && Array.isArray((result as any).data) && (result as any).data.length > 0) {
          imageUrl = (result as any).data[0].url;
        }
        // 情况2: 响应拦截器自动解包了，直接返回了 data 数组
        else if (Array.isArray(result) && result.length > 0) {
          imageUrl = (result as any)[0].url;
        }
        
        if (imageUrl) {
          updateLastMessage(`![生成的图片](${imageUrl})`);
        } else {
          updateLastMessage('❌ 生成失败：未返回有效的图片 URL');
        }
      } catch (error: any) {
        console.error('图像生成失败:', error);
        const appError = ErrorHandler.handleHttpError(error);
        updateLastMessage(`❌ 生成失败：${appError.message}`);
      } finally {
        isSending.value = false;
      }
      return;
    }

    // 4. 处理普通对话 (Dify)
    addMessage('assistant', ''); // 占位

    const userStore = useUserStore();
    const username = userStore.username || 'guest';
    
    // 记录开始时的 conversationId
    const initialConversationId = difySessionId.value;
    let tempConversationId: string | null = null;

    // 如果是新会话（没有ID），先创建一个临时会话占位
    if (!initialConversationId) {
        tempConversationId = addTempDifyConversation('新对话');
    }
    
    await streamDifyChat(
      {
        query: fullContent,
        user: username,
        conversation_id: difySessionId.value || undefined,
      },
      (text: string, conversationId?: string) => {
        updateLastMessage(text);
        
        // 当后端返回真实 ID 时
        if (conversationId && !difySessionId.value) {
            setDifySessionId(conversationId);
            
            // 如果之前创建了临时会话，将临时 ID 替换为真实 ID
            if (tempConversationId) {
                updateTempDifyConversation(tempConversationId, conversationId);
            }
            
            // 如果是新会话，触发回调刷新列表 (获取真实标题等信息)
            if (!initialConversationId && onConversationCreated) {
                onConversationCreated();
            }
        }
      },
      () => {
        isSending.value = false;
      },
      (err) => {
         isSending.value = false;
         const appError = ErrorHandler.handleHttpError(err);
         ElMessage.error('对话请求失败: ' + appError.message);
         updateLastMessage('❌ 请求失败，请重试。');
      }
    );
  };

  // 停止生成
  const stopGenerating = () => {
    if (abortController.value) {
      abortController.value.abort();
      isSending.value = false;
      ElMessage.info('已停止生成');
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
    updateTempDifyConversation,
    // 新增
    isSending,
    sendMessage,
    stopGenerating
  };
});
