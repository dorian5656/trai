// 文件名：frontend/src/composables/useChatLogic.ts
// 作者：zcl
// 日期：2026-01-28
// 描述：聊天核心逻辑复用

import { type Ref } from 'vue';
import { ElMessage } from 'element-plus';
import { mockStreamChat, streamDifyChat } from '@/utils/stream';
import type { UploadFile } from './useFileUpload';
import type { Skill } from './useSkills';
import { useUserStore } from '@/stores/user';

export function useChatLogic(
  chatStore: any,
  inputMessage: Ref<string>,
  activeSkill: Ref<Skill | null>,
  uploadedFiles: Ref<UploadFile[]>,
  isSending: Ref<boolean>,
  scrollToBottom: () => void,
  clearFiles: () => void,
  onConversationCreated?: () => void // 新增回调
) {
  const userStore = useUserStore();

  const handleSend = async () => {
    // ... (前置检查)
    const content = inputMessage.value.trim();
    if ((!content && uploadedFiles.value.length === 0) || isSending.value) return;

    let fullContent = content;
    if (activeSkill.value) {
      fullContent = `${activeSkill.value.label} ${content}`;
    }
    
    if (uploadedFiles.value.length > 0) {
      const fileNames = uploadedFiles.value.map(f => `[文件: ${f.name}]`).join(' ');
      fullContent = `${fileNames} ${fullContent}`;
    }

    // 添加用户消息
    chatStore.addMessage('user', fullContent);
    inputMessage.value = '';
    activeSkill.value = null; 
    clearFiles(); // 发送后清空文件列表
    isSending.value = true;
    
    // 滚动到底部
    scrollToBottom();

    // 添加 AI 占位消息
    chatStore.addMessage('assistant', '');

    // 开始流式请求 (使用 Dify)
    const username = userStore.username || 'guest';
    
    // 记录开始时的 conversationId
    const initialConversationId = chatStore.difySessionId;
    let tempConversationId: string | null = null;

    // 如果是新会话（没有ID），先创建一个临时会话占位
    if (!initialConversationId) {
        tempConversationId = chatStore.addTempDifyConversation('新对话');
        // 临时设置 currentSessionId 为这个 tempId，以便 UI 高亮
        // 注意：不要设置 chatStore.difySessionId，因为那个是传给后端的真实 ID，后端需要 null/undefined 才能创建新会话
        // 这里我们只更新列表，不更新 difySessionId，直到后端返回真实 ID
    }
    
    await streamDifyChat(
      {
        query: fullContent,
        user: username,
        conversation_id: chatStore.difySessionId || undefined,
        // 如果有上传文件，这里需要处理，Dify 支持 files 参数
        // 暂时只支持文本
      },
      (text: string, conversationId?: string) => {
        chatStore.updateLastMessage(text);
        
        // 当后端返回真实 ID 时
        if (conversationId && !chatStore.difySessionId) {
            chatStore.setDifySessionId(conversationId);
            
            // 如果之前创建了临时会话，将临时 ID 替换为真实 ID
            if (tempConversationId) {
                chatStore.updateTempDifyConversation(tempConversationId, conversationId);
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
         ElMessage.error('对话请求失败: ' + err.message);
         chatStore.updateLastMessage('❌ 请求失败，请重试。');
         // 如果失败，可能需要移除临时会话？或者保留让用户重试
      }
    );
  };

  const handleStop = () => {
    if (chatStore.abortController) {
      chatStore.abortController.abort();
      isSending.value = false;
      ElMessage.info('已停止生成');
    }
  };

  return {
    handleSend,
    handleStop
  };
}
