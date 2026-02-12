// 文件名：frontend/src/composables/useChatSession.ts
// 作者：zcl
// 日期：2026-02-11
// 描述：聊天会话管理逻辑复用

import { ref, watch } from 'vue';
import { useChatStore, useUserStore } from '@/stores';
import { fetchDifyConversations, fetchConversationMessages, renameDifyConversation, deleteDifyConversation } from '@/api/dify';
import type { DifyConversation } from '@/types/chat';
import { ElMessage, ElMessageBox } from 'element-plus';

export function useChatSession() {
  const chatStore = useChatStore();
  const userStore = useUserStore();
  const isLoadingHistory = ref(false);

  // 加载会话列表
  const loadConversations = async () => {
    const username = userStore.username;
    if (!username || username === '未登录') return;
    try {
      const res = await fetchDifyConversations(username);
      if (res && res.data) {
        chatStore.difyConversations = (res.data as unknown) as DifyConversation[];
      }
    } catch (e) {
      console.error('加载历史会话失败', e);
    }
  };

  // 切换会话
  const handleSwitchSession = async (conversationId: string) => {
    isLoadingHistory.value = true;
    chatStore.clearSession();
    chatStore.setDifySessionId(conversationId);
    try {
      const username = userStore.username || 'guest';
      const res = await fetchConversationMessages(conversationId, username, 50, 'guanwang');
      let history: any[] = [];
      const conv = chatStore.difyConversations.find(c => c.id === conversationId);
      if (Array.isArray(res)) {
        history = res as any[];
      } else if (res && (res as any).data) {
        history = (res as any).data as any[];
      }
      chatStore.replaceMessagesFromDify(history, conv?.name || '会话', conversationId);
    } catch (e) {
      console.error('加载历史消息失败', e);
      ElMessage.error('加载历史消息失败');
    } finally {
      isLoadingHistory.value = false;
    }
  };

  // 新建会话
  const handleNewChat = () => {
    chatStore.createSession();
    chatStore.setDifySessionId(null);
  };

  // 重命名会话
  const handleRenameConversation = async (conv: DifyConversation) => {
    try {
      const { value } = await ElMessageBox.prompt('请输入新名称', '重命名会话', {
        confirmButtonText: '确定',
        cancelButtonText: '取消',
        inputValue: conv.name,
        inputPattern: /\S/,
        inputErrorMessage: '名称不能为空',
      });

      if (value && value !== conv.name) {
        await renameDifyConversation(conv.id, value, 'guanwang', false);
        chatStore.renameDifyConversation(conv.id, value);
        ElMessage.success('重命名成功');
      }
    } catch (e: any) {
      if (e === 'cancel' || e === 'close') return;
      ElMessage.error('重命名失败，请稍后重试');
    }
  };

  // 删除会话
  const handleDeleteConversation = async (conv: DifyConversation) => {
    try {
      await ElMessageBox.confirm(
        '确定要删除该会话吗？删除后无法恢复。',
        '删除确认',
        {
          confirmButtonText: '删除',
          cancelButtonText: '取消',
          type: 'warning',
        }
      );
      
      await deleteDifyConversation(conv.id, 'guanwang');
      chatStore.removeDifyConversation(conv.id);
      ElMessage.success('删除成功');
    } catch (e: any) {
      if (e === 'cancel' || e === 'close') return;
      ElMessage.error('删除失败，请稍后重试');
    }
  };

  // 监听登录状态变化，自动刷新会话列表
  watch(
    () => userStore.isLoggedIn,
    (isLoggedIn) => {
      if (isLoggedIn) {
        loadConversations();
      } else {
        chatStore.clearAllConversations();
      }
    }
  );

  return {
    isLoadingHistory,
    loadConversations,
    handleSwitchSession,
    handleNewChat,
    handleRenameConversation,
    handleDeleteConversation
  };
}
