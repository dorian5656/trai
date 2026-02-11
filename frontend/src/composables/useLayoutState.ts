// 文件名：frontend/src/composables/useLayoutState.ts
// 作者：zcl
// 日期：2026-02-11
// 描述：UI 布局状态管理 (弹窗、输入框、DeepThinking 等)

import { ref } from 'vue';
import { useChatStore, useAppStore, useUserStore } from '@/stores';

export function useLayoutState() {
  const appStore = useAppStore();
  const chatStore = useChatStore();
  const userStore = useUserStore();
  
  // UI 状态
  const inputMessage = ref('');
  const isDeepThinking = ref(false);
  
  // 弹窗状态
  const showSimilarityDialog = ref(false);
  const showMeetingRecorder = ref(false);
  const showDocumentDialog = ref(false);

  const toggleDeepThinking = () => {
    isDeepThinking.value = !isDeepThinking.value;
  };

  const handleLogin = () => {
    appStore.openLoginModal();
  };

  const handleLogout = () => {
    userStore.logout();
  };

  const handleStop = () => {
    chatStore.stopGenerating();
  };

  return {
    inputMessage,
    isDeepThinking,
    showSimilarityDialog,
    showMeetingRecorder,
    showDocumentDialog,
    toggleDeepThinking,
    handleLogin,
    handleLogout,
    handleStop
  };
}
