<!--
文件名：frontend/src/views/mobile/Home.vue
作者：zcl
日期：2026-01-28
描述：移动端主页组件 (修复输入框显示问题)
-->
<script setup lang="ts">
import { ref, watch, onMounted, nextTick, computed } from 'vue';
import { useRouter } from 'vue-router';
import { useAppStore, useChatStore, useUserStore } from '@/stores';
import { ElImageViewer, ElMessage } from 'element-plus';
import { useSpeechRecognition, useFileUpload, useSkills } from '@/composables';
import { ChatInput, MessageList } from '@/modules/chat';
import SimilarityDialog from '@/components/business/SimilarityDialog.vue';
import MeetingRecorder from '@/components/business/MeetingRecorder.vue';
import { fetchDifyConversations, fetchConversationMessages } from '@/api/dify';
import type { DifyConversation } from '@/types/chat';
import { MOBILE_TEXT } from '@/constants/texts';

const router = useRouter();
const appStore = useAppStore();
const chatStore = useChatStore();
const userStore = useUserStore();
const { isListening, result, toggleListening } = useSpeechRecognition();
const { uploadedFiles, showViewer, previewUrlList, initialIndex, handleFileSelect, removeFile, handlePreview, closeViewer, clearFiles } = useFileUpload();
const { allSkills, activeSkill, handleSkillClick, removeSkill } = useSkills();

const inputMessage = ref('');
const messageListRef = ref<InstanceType<typeof MessageList> | null>(null);
const isDeepThinking = ref(false);
const showSimilarityDialog = ref(false);
const showMeetingRecorder = ref(false);

// 自动滚动
watch(
  () => chatStore.messages,
  () => {
    messageListRef.value?.scrollToBottom();
  },
  { deep: true }
);

const handleSend = async () => {
  const content = inputMessage.value.trim();
  if ((!content && uploadedFiles.value.length === 0) || chatStore.isSending) return;

  // 1. 捕获当前状态
  const currentFiles = [...uploadedFiles.value];
  const currentSkill = activeSkill.value;
  
  // 2. 立即清空 UI 输入状态
  inputMessage.value = '';
  clearFiles();
  activeSkill.value = null;

  // 3. 调用 Store Action
  await chatStore.sendMessage(content, currentFiles, currentSkill);
};

const handleStop = () => {
  chatStore.stopGenerating();
};

const toggleDeepThinking = () => {
  isDeepThinking.value = !isDeepThinking.value;
};

// 监听语音识别结果
watch(result, (newVal) => {
  if (newVal) {
    inputMessage.value = newVal;
  }
});

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

// 初始化用户信息
onMounted(async () => {
  await userStore.init();
  if (userStore.isLoggedIn) {
    loadConversations();
  }
});

const loadConversations = async () => {
  try {
    const username = userStore.username;
    if (!username || username === '未登录') return;
    const res = await fetchDifyConversations(username, 50, 'guanwang');
    let list: DifyConversation[] = [];
    if (Array.isArray(res)) {
      list = res as unknown as DifyConversation[];
    } else if (res && (res as any).data) {
      list = (res as any).data as DifyConversation[];
    }
    chatStore.difyConversations = list;
  } catch (e) {
    console.error('加载会话失败', e);
  }
};

const handleSwitchDify = (conv: DifyConversation) => {
  chatStore.clearSession();
  chatStore.setDifySessionId(conv.id);
  ElMessage.success('已切换会话上下文');
};

const handleLogin = () => {
  appStore.openLoginModal();
};

const handleLogout = () => {
  userStore.logout();
};

const handleMobileSkillClick = (skill: any) => {
  if (skill.label === '会议记录') {
    showMeetingRecorder.value = true;
    return;
  }
  if (skill.label === '相似度识别') {
    showSimilarityDialog.value = true;
    return;
  }
  handleSkillClick(skill);
  nextTick(() => {
    const input = document.querySelector('.input-box input') as HTMLInputElement;
    if (input) input.focus();
  });
};

const recentItems = computed(() => {
  const locals = chatStore.sessions.map(s => ({ id: s.id, title: s.title, type: 'local' as const }));
  const dify = chatStore.difyConversations.map(c => ({ id: c.id, title: c.name || '新对话', type: 'dify' as const }));
  return [...locals, ...dify];
});

const handleRecentClick = (item: { id: string; type: 'local' | 'dify' }) => {
  if (item.type === 'local') {
    chatStore.switchSession(item.id);
  } else {
    const conv = chatStore.difyConversations.find(c => c.id === item.id);
    if (conv) handleSwitchDify(conv);
  }
  appStore.closeMobileSidebar();
};
</script>

<template>
  <div class="mobile-container">
    <!-- 侧边栏遮罩 -->
    <div v-if="appStore.isMobileSidebarOpen" class="sidebar-mask" @click="appStore.closeMobileSidebar"></div>

    <!-- 侧边栏抽屉 -->
    <aside class="mobile-sidebar" :class="{ 'open': appStore.isMobileSidebarOpen }">
      <div class="sidebar-header">
        <div class="user-info">
          <div class="avatar" v-if="userStore.avatar">
            <img :src="userStore.avatar" alt="Avatar" />
          </div>
          <div class="avatar" v-else>👩‍💻</div>
          <span class="username">{{ userStore.isLoggedIn ? userStore.username : MOBILE_TEXT.sidebar.usernameFallback }}</span>
        </div>
        <button class="close-btn" @click="appStore.closeMobileSidebar">{{ MOBILE_TEXT.sidebar.closeBtn }}</button>
      </div>
      
      <div class="action-area">
        <button class="new-chat-btn" @click="chatStore.createSession()">{{ MOBILE_TEXT.sidebar.newChatBtn }}</button>
      </div>

      <!-- <nav class="menu-list">
        <div class="menu-item"><span class="icon">✍️</span> 帮我写作</div>
        <div class="menu-item"><span class="icon">🎨</span> AI 创作</div>
        <div class="menu-item"><span class="icon">🧩</span> 更多</div>
      </nav> -->

      <div class="recent-chats">
        <div class="section-title">{{ MOBILE_TEXT.sidebar.recentSectionTitle }}</div>
        <div
          v-for="item in recentItems"
          :key="`${item.type}-${item.id}`"
          class="chat-item"
          @click="handleRecentClick(item)"
        >{{ item.title }}</div>
      </div>
      
      <div class="sidebar-footer">
        <button class="footer-btn">{{ MOBILE_TEXT.sidebar.aboutBtn }}</button>
      </div>
    </aside>

    <!-- 顶部导航 -->
    <header class="mobile-header">
      <div class="left">
        <button class="icon-btn" @click="appStore.toggleMobileSidebar">☰</button>
        <button class="new-chat-pill" @click="chatStore.createSession()">{{ MOBILE_TEXT.header.newChatPill }}</button>
      </div>
      <div class="right">
        <div v-if="userStore.isLoggedIn" class="user-actions">
          <button class="logout-btn" @click="handleLogout">{{ MOBILE_TEXT.header.logout }}</button>
        </div>
        <button v-else class="login-btn" @click="handleLogin">{{ MOBILE_TEXT.header.login }}</button>
      </div>
    </header>

    <!-- 主内容 -->
    <main class="mobile-content">
      <!-- 聊天模式：有消息时显示 -->
      <div v-if="chatStore.messages.length > 0" class="chat-layout">
        <!-- 消息列表 -->
        <MessageList 
          :messages="chatStore.messages" 
          ref="messageListRef"
        />
        
        <!-- 底部输入框 -->
        <div class="chat-footer">
          <ChatInput 
            v-model="inputMessage"
            :is-sending="chatStore.isSending"
            :is-deep-thinking="isDeepThinking"
            :active-skill="activeSkill"
            :uploaded-files="uploadedFiles"
            :is-listening="isListening"
            @send="handleSend"
            @stop="handleStop"
            @toggle-deep-think="toggleDeepThinking"
            @toggle-listening="toggleListening"
            @remove-skill="removeSkill"
            @file-select="handleFileSelect"
            @remove-file="removeFile"
            @preview-file="handlePreview"
          />
        </div>
      </div>

      <!-- 欢迎页：无消息时显示 -->
      <div v-else class="welcome-wrapper">
        <h1 class="greeting">{{ MOBILE_TEXT.welcomeTitle }}</h1>

        <div class="input-area-wrapper">
          <ChatInput 
            v-model="inputMessage"
            :is-sending="chatStore.isSending"
            :is-deep-thinking="isDeepThinking"
            :active-skill="activeSkill"
            :uploaded-files="uploadedFiles"
            :is-listening="isListening"
            @send="handleSend"
            @stop="handleStop"
            @toggle-deep-think="toggleDeepThinking"
            @toggle-listening="toggleListening"
            @remove-skill="removeSkill"
            @file-select="handleFileSelect"
            @remove-file="removeFile"
            @preview-file="handlePreview"
          />
        </div>

        <!-- 技能网格 -->
        <div class="skills-grid">
          <div 
            v-for="skill in allSkills" 
            :key="skill.label" 
            class="skill-item"
            @click="handleMobileSkillClick(skill)"
          >
            <div class="skill-icon-wrapper" :style="{ color: skill.color }">
              <span class="skill-icon" v-html="skill.icon"></span>
            </div>
            <span class="skill-label">{{ skill.label }}</span>
          </div>
        </div>
      </div>
    </main>

    <!-- 图片预览组件 -->
    <el-image-viewer
      v-if="showViewer"
      :url-list="previewUrlList"
      :initial-index="initialIndex"
      @close="closeViewer"
    />

    <!-- 相似度识别弹窗 -->
    <SimilarityDialog
      v-if="showSimilarityDialog"
      :visible="showSimilarityDialog"
      @update:visible="(val) => showSimilarityDialog = val"
    />

    <!-- 会议记录组件 -->
    <MeetingRecorder 
      v-if="showMeetingRecorder" 
      @close="showMeetingRecorder = false" 
    />
  </div>
</template>

<style scoped lang="scss">
.user-actions {
  display: flex;
  align-items: center;
}
.logout-btn {
  padding: 0.375rem 0.75rem;
  background-color: #f56c6c;
  color: white;
  border: none;
  border-radius: 1rem;
  font-size: 0.8125rem;
  cursor: pointer;
}
.mobile-container {
  display: flex;
  flex-direction: column;
  height: 100vh;
  background-color: #fff;
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
  position: relative;
  overflow: hidden; // 防止滚动穿透
}

.sidebar-mask {
  position: fixed;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
  background: rgba(0, 0, 0, 0.5);
  z-index: 99;
}

.mobile-sidebar {
  position: fixed;
  top: 0;
  left: 0;
  width: 17.5rem;
  height: 100%;
  background: #f7f8fa;
  z-index: 100;
  transform: translateX(-100%);
  transition: transform 0.3s ease;
  display: flex;
  flex-direction: column;
  padding: 1rem;
  box-shadow: 0.125rem 0 0.5rem rgba(0,0,0,0.1);

  &.open {
    transform: translateX(0);
  }

  .sidebar-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 1.5rem;
    
    .user-info {
      display: flex;
      align-items: center;
      .avatar {
        width: 2rem;
        height: 2rem;
        background: #ccc;
        border-radius: 50%;
        display: flex;
        align-items: center;
        justify-content: center;
        margin-right: 0.5rem;
      }
      .username { font-weight: 600; font-size: 1rem; }
    }
    
    .close-btn {
      background: none;
      border: none;
      font-size: 1.25rem;
      color: #86909c;
    }
  }

  .new-chat-btn {
    width: 100%;
    padding: 0.625rem;
    background: #e8f3ff;
    color: #165dff;
    border: none;
    border-radius: 0.5rem;
    font-weight: 500;
    margin-bottom: 1.5rem;
  }

  .menu-list {
    .menu-item {
      padding: 0.75rem 0;
      font-size: 0.9375rem;
      color: #4e5969;
      display: flex;
      align-items: center;
      .icon { margin-right: 0.75rem; }
    }
  }

  .recent-chats {
    margin-top: 1.5rem;
    flex: 1;
    overflow-y: auto;
    .section-title {
      font-size: 0.75rem;
      color: #86909c;
      margin-bottom: 0.75rem;
    }
    .chat-item {
      padding: 0.5rem 0;
      font-size: 0.875rem;
      cursor: pointer;
    }
  }

  .sidebar-footer {
    padding-top: 1rem;
    border-top: 1px solid #e5e6eb;
    .footer-btn {
      background: none;
      border: none;
      color: #86909c;
      font-size: 0.8125rem;
      display: flex;
      align-items: center;
    }
  }
}

.mobile-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 0.75rem 1rem;
  border-bottom: 1px solid #f2f3f5;
  flex-shrink: 0; // 固定顶部栏高度
  
  .left {
    display: flex;
    align-items: center;
    .icon-btn {
      font-size: 1.25rem;
      margin-right: 0.75rem;
      background: none;
      border: none;
    }
    .new-chat-pill {
      background: #e8f3ff;
      color: #165dff;
      border: none;
      padding: 0.375rem 0.75rem;
      border-radius: 1rem;
      font-size: 0.8125rem;
      font-weight: 500;
    }
  }

  .right {
    display: flex;
    align-items: center;
    .login-btn {
      background: #1d2129;
      color: #fff;
      border: none;
      padding: 0.375rem 1rem;
      border-radius: 1rem;
      font-size: 0.8125rem;
      font-weight: 500;
    }
  }
}

.mobile-content {
  flex: 1;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

/* 聊天模式布局 - 核心修复 */
.chat-layout {
  flex: 1;
  display: flex;
  flex-direction: column;
  height: 100%;
  overflow: hidden;
  
  :deep(.message-list) {
    flex: 1;
    overflow-y: auto;
    padding: 0.75rem 1rem;
  }

  .chat-footer {
    flex-shrink: 0;
    padding: 0.75rem 1rem;
    background: white;
    // border-top: 1px solid #f2f3f5;
    z-index: 10; // 确保输入框在最上层
  }
}

/* 欢迎页样式 */
.welcome-wrapper {
  flex: 1;
  display: flex;
  flex-direction: column;
  justify-content: center;
  padding: 1.25rem 1rem;
  padding-bottom: 2rem;
}

.greeting {
  font-size: 1.75rem;
  font-weight: 700;
  color: #1d2129;
  text-align: center;
  margin-bottom: 2rem;
}

.input-area-wrapper {
  margin-bottom: 2.5rem;
}

.skills-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr); // 4列
  gap: 1rem;
  
  .skill-item {
    display: flex;
    flex-direction: column;
    align-items: center;
    
    .skill-icon-wrapper {
      width: 3rem;
      height: 3rem;
      background: #fff;
      border: 1px solid #e5e6eb;
      border-radius: 1rem;
      display: flex;
      align-items: center;
      justify-content: center;
      margin-bottom: 0.375rem;
      box-shadow: 0 0.125rem 0.5rem rgba(0,0,0,0.02);
      
      .skill-icon {
        width: 1.5rem;
        height: 1.5rem;
        display: flex;
        align-items: center;
        justify-content: center;
      }
    }
    
    .skill-label {
      font-size: 0.75rem;
      color: #4e5969;
      text-align: center;
    }
  }
}
</style>
