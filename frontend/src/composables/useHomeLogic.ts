// 文件名：frontend/src/composables/useHomeLogic.ts
// 作者：zcl
// 日期：2026-02-11
// 描述：主页通用逻辑封装 (PC/Mobile 共用)

import { ref, watch, onMounted, computed, nextTick } from 'vue';
import { useAppStore, useChatStore, useUserStore } from '@/stores';
import { useSpeechRecognition } from './useSpeechRecognition';
import { useFileUpload } from './useFileUpload';
import { useSkills } from './useSkills';
import { useChatSession } from './useChatSession';
import { useLayoutState } from './useLayoutState';
import { ElMessage } from 'element-plus';
import type { MessageList } from '@/modules/chat';
import type { Skill } from './useSkills';

export function useHomeLogic() {
  const appStore = useAppStore();
  const chatStore = useChatStore();
  const userStore = useUserStore();

  // 集成各个功能模块
  const speech = useSpeechRecognition();
  const files = useFileUpload();
  const skills = useSkills();
  const session = useChatSession();
  const layout = useLayoutState();

  const messageListRef = ref<InstanceType<typeof MessageList> | null>(null);

  // 初始化逻辑
  onMounted(async () => {
    await userStore.init();
    if (userStore.isLoggedIn) {
      session.loadConversations();
    }
  });

  // 自动滚动监听
  watch(
    () => chatStore.messages,
    () => {
      nextTick(() => {
        messageListRef.value?.scrollToBottom();
      });
    },
    { deep: true }
  );

  // 语音识别结果监听
  watch(speech.result, (newVal) => {
    if (newVal) {
      layout.inputMessage.value = newVal;
    }
  });

  // 发送消息逻辑
  const handleSend = async () => {
    const content = layout.inputMessage.value.trim();
    if ((!content && files.uploadedFiles.value.length === 0) || chatStore.isSending) return;

    // 1. 捕获当前状态
    const currentFiles = [...files.uploadedFiles.value];
    const currentSkill = skills.activeSkill.value;
    
    // 2. 立即清空 UI 输入状态
    layout.inputMessage.value = '';
    files.clearFiles();
    skills.removeSkill();

    // 3. 调用 Store Action
    await chatStore.sendMessage(
      content,
      currentFiles,
      currentSkill,
      () => {
        // PC端需要在发送后刷新会话列表，Mobile端也可以保持一致
        setTimeout(() => {
          session.loadConversations();
        }, 1000);
      }
    );
  };

  // 重新生成逻辑 (主要用于 PC，但 Mobile 也可以用)
  const handleRegenerate = () => {
    if (chatStore.isSending) return;
    // 找到最后一条 user 消息
    const messages = chatStore.messages;
    let lastUserMsgContent = '';
    for (let i = messages.length - 1; i >= 0; i--) {
      const msg = messages[i];
      if (msg && msg.role === 'user') {
        lastUserMsgContent = msg.content;
        break;
      }
    }

    if (lastUserMsgContent) {
      // 尝试提取纯文本 (移除 [文件: ...] 前缀)
      const fileRegex = /^(\[文件: .*?\]\s*)+/;
      const match = lastUserMsgContent.match(fileRegex);
      if (match) {
        layout.inputMessage.value = lastUserMsgContent.replace(fileRegex, '').trim();
        ElMessage.warning('重新生成仅包含文本内容，文件需重新上传');
      } else {
        layout.inputMessage.value = lastUserMsgContent;
      }
      
      handleSend();
    }
  };

  const handleSkillSelect = (skill: Skill) => {
    if (!userStore.isLoggedIn) {
      appStore.openLoginModal();
      return;
    }
    if (skill.label === '会议记录') {
      layout.showMeetingRecorder.value = true;
      return;
    }
    if (skill.label === '文档工具') {
      layout.showDocumentDialog.value = true;
      return;
    }
    if (skill.label === '图像生成') {
      layout.showImageGenDialog.value = true;
      return;
    }
    
    // 调用基础的技能点击逻辑 (处理相似度识别的回调或其他通用逻辑)
    skills.handleSkillClick(skill, () => {
      layout.showSimilarityDialog.value = true;
    });

    // 非特殊弹窗类技能，自动聚焦输入框
    if (skill.label !== '相似度识别') {
      nextTick(() => {
        const input = document.querySelector('.input-box input') as HTMLInputElement;
        if (input) input.focus();
      });
    }
  };

  // 统一的混合会话列表 (用于 Mobile Sidebar，PC Sidebar 也可以复用)
  const mixedRecentItems = computed(() => {
    const locals = chatStore.sessions.map(s => ({ id: s.id, title: s.title, type: 'local' as const }));
    const dify = chatStore.difyConversations.map(c => ({ id: c.id, title: c.name || '新对话', type: 'dify' as const }));
    return [...locals, ...dify];
  });

  return {
    appStore,
    chatStore,
    userStore,
    messageListRef,
    // 模块
    ...speech,
    ...files,
    ...skills,
    ...session,
    ...layout,
    // 操作
    handleSend,
    handleRegenerate,
    handleSkillSelect,
    mixedRecentItems
  };
}
