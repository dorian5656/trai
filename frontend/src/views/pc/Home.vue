<!--
文件名：frontend/src/views/pc/Home.vue
作者：zcl
日期：2026-01-27
描述：PC端主页组件 (集成聊天功能) - 修复顶部导航栏+聊天输入框
-->
<script setup lang="ts">
import { ref, watch, nextTick, onMounted } from 'vue';
import { useRouter } from 'vue-router';
import { useAppStore } from '@/stores/app';
import { useChatStore } from '@/stores/chat';
import { useUserStore } from '@/stores/user';
import SimilarityDialog from '@/components/business/SimilarityDialog.vue';
import { mockStreamChat } from '@/utils/stream';
import { renderMarkdown } from '@/utils/markdown';
import { ElMessage, ElImageViewer } from 'element-plus';
import { useSpeechRecognition } from '@/composables/useSpeechRecognition';
import { useFileUpload } from '@/composables/useFileUpload';
import { useSkills } from '@/composables/useSkills';
import { useChatLogic } from '@/composables/useChatLogic';
import SkillSelector from '@/components/business/home/SkillSelector.vue';
import ChatInput from '@/components/business/home/ChatInput.vue';
import MessageList from '@/components/business/home/MessageList.vue';
import { fetchDifyConversations } from '@/api/dify';

const router = useRouter();
const appStore = useAppStore();
const chatStore = useChatStore();
const userStore = useUserStore();
const showSimilarityDialog = ref(false);
const showMeetingRecorder = ref(false);
const { isListening, result, toggleListening } = useSpeechRecognition();
const { uploadedFiles, showViewer, previewUrlList, initialIndex, handleFileSelect, removeFile, handlePreview, closeViewer, clearFiles } = useFileUpload();
const { activeSkill, visibleSkills, moreSkills, moreSkillItem, handleSkillClick, removeSkill } = useSkills();

const inputMessage = ref('');
const isSending = ref(false);
const messageListRef = ref<InstanceType<typeof MessageList> | null>(null);
const isDeepThinking = ref(false);

const { handleSend, handleStop } = useChatLogic(
  chatStore,
  inputMessage,
  activeSkill,
  uploadedFiles,
  isSending,
  () => messageListRef.value?.scrollToBottom(),
  clearFiles,
  () => {
      // 当新会话创建时，刷新会话列表
      // 延迟一点时间，确保后端已经可以查到
      setTimeout(() => {
          loadConversations();
      }, 1000);
  }
);

const handleRegenerate = () => {
  if (isSending.value) return;
  // 找到最后一条 user 消息
  const messages = chatStore.messages;
  let lastUserMsgContent = '';
  for (let i = messages.length - 1; i >= 0; i--) {
    const msg = messages[i];
    if (msg && msg.role === 'user') {
      // 提取纯文本内容（去除可能的 [文件: ...] 前缀，如果需要重新上传文件逻辑会更复杂，这里简化为重发文本）
      // 现在的 fullContent 是 "[文件: xxx] 文本"，这里简单起见直接重发整条内容
      lastUserMsgContent = msg.content;
      break;
    }
  }

  if (lastUserMsgContent) {
    // 移除最后一条 assistant 消息 (如果是失败的消息) 或者准备生成新的
    // 简单起见，我们模拟用户重新输入了这条消息
    inputMessage.value = lastUserMsgContent;
    // 这里的 content 可能包含 "[文件: ...]"，在 handleSend 中会再次拼接，导致重复
    // 需要清洗 content，或者调整 handleSend 逻辑
    // 更好的做法是：让 useChatLogic 暴露一个 directSend 方法，或者我们在 handleSend 中判断
    
    // 临时方案：如果内容以 [文件: 开头，尝试提取真实文本
    // 这里的逻辑稍微有点 hack，但为了不改动太大
    const fileRegex = /^(\[文件: .*?\]\s*)+/;
    const match = lastUserMsgContent.match(fileRegex);
    if (match) {
        inputMessage.value = lastUserMsgContent.replace(fileRegex, '').trim();
        // 注意：这里丢失了文件信息，如果重新生成需要带文件，需要重新 select 文件
        // 由于文件上传是临时的，发送后 clearFiles 了，所以很难完全还原
        ElMessage.warning('重新生成仅包含文本内容，文件需重新上传');
    } else {
        inputMessage.value = lastUserMsgContent;
    }
    
    handleSend();
  }
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

// 加载历史会话
const loadConversations = async () => {
  if (!userStore.username) return;
  try {
    const res = await fetchDifyConversations(userStore.username);
    if (res && res.data) {
      chatStore.difyConversations = (res.data as unknown) as any[];
    }
  } catch (e) {
    console.error('加载历史会话失败', e);
  }
};

// 初始化用户信息
onMounted(async () => {
  await userStore.init();
  if (userStore.isLoggedIn) {
      loadConversations();
  }
});

const handleSkillSelect = (skill: any) => {
  if (skill.label === '会议记录') {
    showMeetingRecorder.value = true;
    return;
  }
  handleSkillClick(skill, () => {
    showSimilarityDialog.value = true;
  });
  if (skill.label !== '相似度识别') {
    // Focus input
    nextTick(() => {
      const input = document.querySelector('.input-box input') as HTMLInputElement;
      if (input) input.focus();
    });
  }
};

const handleNewChat = () => {
  chatStore.createSession();
  chatStore.setDifySessionId(null);
};

const handleSwitchSession = (conversationId: string) => {
  // 切换到 Dify 会话
  // TODO: 后端目前没有获取历史消息详情的接口，所以这里暂时只能设置 ID，无法回显消息
  // 临时方案：清空当前消息，提示用户已切换
  chatStore.clearSession();
  chatStore.setDifySessionId(conversationId);
  ElMessage.success('已切换会话上下文 (暂不支持回显历史消息)');
};

const handleLogin = () => {
  router.push('/login');
};

const handleLogout = () => {
  userStore.logout();
};
</script>

<template>
  <div class="pc-container">
    <!-- 侧边栏 -->
    <aside class="sidebar" :class="{ 'collapsed': !appStore.isSidebarOpen }">
      <div class="user-profile">
        <div class="avatar" v-if="userStore.avatar">
          <img :src="userStore.avatar" alt="Avatar" />
        </div>
        <div class="avatar" v-else>👩‍💻</div>
        <span class="username" v-show="appStore.isSidebarOpen">
          {{ userStore.isLoggedIn ? userStore.username : '驼人GPT' }}
        </span>
        <button class="sidebar-toggle" @click="appStore.toggleSidebar" v-show="appStore.isSidebarOpen">
          <span>||</span>
        </button>
      </div>

      <div class="action-btn" v-show="appStore.isSidebarOpen">
        <button class="new-chat-btn" @click="handleNewChat">
          <span class="icon">📝</span> 新对话
        </button>
      </div>

      <!-- <nav class="menu-list" v-show="appStore.isSidebarOpen">
        <div class="menu-item"><span class="icon">✨</span> 帮我写作</div>
        <div class="menu-item"><span class="icon">🎨</span> AI 创作</div>
        <div class="menu-item"><span class="icon">🧩</span> 更多</div>
      </nav> -->

      <div class="recent-chats" v-show="appStore.isSidebarOpen">
        <div class="section-title">最近对话</div>
        
        <!-- Dify 会话列表 -->
        <template v-if="chatStore.difyConversations.length > 0">
           <div 
            v-for="conv in chatStore.difyConversations" 
            :key="conv.id" 
            class="chat-item"
            :class="{ active: conv.id === chatStore.difySessionId }"
            @click="handleSwitchSession(conv.id)"
          >
            {{ conv.name || '未命名对话' }}
          </div>
        </template>
        
        <!-- 本地临时会话 (如果有) -->
        <template v-else>
          <div 
            v-for="session in chatStore.sessions" 
            :key="session.id" 
            class="chat-item"
            :class="{ active: session.id === chatStore.currentSessionId }"
            @click="chatStore.switchSession(session.id)"
          >
            {{ session.title }}
          </div>
        </template>
      </div>
      
      <div class="sidebar-footer" v-show="appStore.isSidebarOpen">
        <div class="footer-item">关于驼人GPT</div>
      </div>
    </aside>

    <!-- 主内容区：改用flex垂直布局，解决top-bar定位问题 -->
    <main class="main-content">
      <!-- 顶部导航栏：移除绝对定位，作为flex第一项，自然顶置 -->
      <header class="top-bar">
        <button v-if="!appStore.isSidebarOpen" class="sidebar-toggle-main" @click="appStore.toggleSidebar">
          ☰
        </button>
        <div class="right-actions">
          <div v-if="userStore.isLoggedIn" class="user-actions">
            <span class="welcome-text">欢迎, {{ userStore.username }}</span>
            <button class="logout-btn" @click="handleLogout">退出</button>
          </div>
          <button v-else class="login-btn" @click="handleLogin">登录</button>
        </div>
      </header>

      <!-- 内容主体：flex占满剩余高度，作为flex第二项 -->
      <div class="content-body">
        <!-- 聊天模式：有消息时显示 -->
        <div class="chat-layout" v-if="chatStore.messages.length > 0">
          <!-- 消息列表 -->
          <MessageList 
            :messages="chatStore.messages" 
            ref="messageListRef"
            @regenerate="handleRegenerate"
          />
          <!-- 底部输入区域 -->
          <div class="chat-footer">
            <div class="footer-input-wrapper">
              <ChatInput 
                v-model="inputMessage"
                :is-sending="isSending"
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
              <SkillSelector
                :visible-skills="visibleSkills"
                :more-skills="moreSkills"
                :more-skill-item="moreSkillItem"
                @select="handleSkillSelect"
              />
            </div>
          </div>
        </div>

        <!-- 欢迎页：无消息时显示 -->
        <div class="welcome-area" v-else>
          <div class="welcome-card">
            <h1 class="greeting">你好，我是驼人GPT</h1>
            <div class="input-area-wrapper">
              <ChatInput 
                v-model="inputMessage"
                :is-sending="isSending"
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
              <SkillSelector
                :visible-skills="visibleSkills"
                :more-skills="moreSkills"
                :more-skill-item="moreSkillItem"
                @select="handleSkillSelect"
              />
            </div>
          </div>
        </div>
      </div>

      <!-- 弹窗组件 -->
      <SimilarityDialog
        v-if="showSimilarityDialog"
        :visible="showSimilarityDialog"
        @update:visible="(val) => showSimilarityDialog = val"
      />
    </main>

    <MeetingRecorder 
      v-if="showMeetingRecorder" 
      @close="showMeetingRecorder = false" 
    />

    <!-- 图片预览组件 -->
    <el-image-viewer
      v-if="showViewer"
      :url-list="previewUrlList"
      :initial-index="initialIndex"
      @close="closeViewer"
    />
  </div>
</template>

<style scoped lang="scss">
.user-actions {
  display: flex;
  align-items: center;
  gap: 0.625rem;
}
.welcome-text {
  font-size: 0.875rem;
  color: #606266;
}
.logout-btn {
  padding: 0.375rem 0.75rem;
  background-color: #f56c6c;
  color: white;
  border: none;
  border-radius: 0.25rem;
  cursor: pointer;
  font-size: 0.875rem;
}
.logout-btn:hover {
  background-color: #f78989;
}
.pc-container {
  display: flex;
  height: 100vh;
  width: 100vw;
  background-color: #fff;
  overflow: hidden;
}

.sidebar {
  width: 16.25rem;
  background-color: #f7f8fa;
  border-right: 1px solid #e5e6eb;
  display: flex;
  flex-direction: column;
  padding: 1rem;
  transition: width 0.3s ease;
  flex-shrink: 0;

  &.collapsed {
    width: 3.75rem;
    padding: 1rem 0.5rem;
    
    .user-profile {
      justify-content: center;
      .avatar { margin-right: 0; }
    }
  }

  .user-profile {
    display: flex;
    align-items: center;
    margin-bottom: 1.25rem;
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
    .username {
      font-weight: 600;
      flex: 1;
      white-space: nowrap;
      overflow: hidden;
    }
    .sidebar-toggle {
      border: none;
      background: none;
      cursor: pointer;
      color: #86909c;
    }
  }

  .new-chat-btn {
    width: 100%;
    padding: 0.625rem;
    background: #e8f3ff;
    color: #165dff;
    border: none;
    border-radius: 0.375rem;
    cursor: pointer;
    display: flex;
    align-items: center;
    justify-content: center;
    font-weight: 500;
    margin-bottom: 1.25rem;
    white-space: nowrap;
    overflow: hidden;
    .icon { margin-right: 0.375rem; }
  }

  .menu-list {
    .menu-item {
      padding: 0.625rem;
      cursor: pointer;
      border-radius: 0.375rem;
      color: #4e5969;
      display: flex;
      align-items: center;
      white-space: nowrap;
      &:hover { background-color: #e5e6eb; }
      .icon { margin-right: 0.625rem; }
    }
  }

  .recent-chats {
    flex: 1;
    overflow-y: auto;
    margin-top: 1.25rem;
    .section-title {
      font-size: 0.75rem;
      color: #86909c;
      margin-bottom: 0.625rem;
    }
    .chat-item {
      padding: 0.5rem 0.625rem;
      cursor: pointer;
      border-radius: 0.375rem;
      color: #1d2129;
      font-size: 0.875rem;
      white-space: nowrap;
      overflow: hidden;
      text-overflow: ellipsis;
      &:hover { background-color: #e5e6eb; }
      &.active { background-color: #e8f3ff; color: #165dff; }
    }
  }

  .sidebar-footer {
    margin-top: auto;
    padding-top: 1.25rem;
    .footer-item {
      font-size: 0.75rem;
      color: #86909c;
      cursor: pointer;
    }
  }
}

/* 主内容区核心修改：改用flex垂直布局 */
.main-content {
  flex: 1;
  display: flex;
  flex-direction: column;
  height: 100vh;
  overflow: hidden;

  /* 顶部导航栏：移除绝对定位，自然顶置，固定高度 */
  .top-bar {
    height: 3.75rem;
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 0 1.25rem;
    // border-bottom: 1px solid #f2f3f5;
    background: white;
    z-index: 10;
    flex-shrink: 0; /* 防止被挤压 */

    .sidebar-toggle-main {
      background: none;
      border: none;
      font-size: 1.25rem;
      cursor: pointer;
    }

    .right-actions {
      margin-left: auto;
      .login-btn {
        background: #165dff;
        color: white;
        border: none;
        padding: 0.375rem 1rem;
        border-radius: 0.25rem;
        cursor: pointer;
      }
    }
  }

  /* 内容主体：占满剩余高度，自动适配top-bar，无需手动margin */
  .content-body {
    flex: 1;
    overflow: hidden;
    padding: 0;
  }

  /* 欢迎模式：基于content-body居中，无手动margin-top */
  .welcome-area {
    height: 100%;
    display: flex;
    justify-content: center;
    align-items: center;
    padding: 0 1.25rem;
  }

  .welcome-card {
    width: 100%;
    max-width: 60rem;
    padding: 2rem;
    border-radius: 1rem;
    background: white;
    // box-shadow: 0 0.25rem 0.75rem rgba(0, 0, 0, 0.05);
    // border: 1px solid #e5e6eb;
    text-align: center;

    .greeting {
      font-size: 2rem;
      font-weight: 600;
      color: #1d2129;
      margin: 0 0 2rem;
    }

    .input-area-wrapper {
      width: 100%;
    }
  }

  /* 聊天模式布局：基于content-body占满高度 */
  .chat-layout {
    height: 100%;
    display: flex;
    flex-direction: column;
    overflow: hidden;
    
    :deep(.message-list) {
      flex: 1;
      overflow-y: auto;
      padding: 1rem 1.25rem;
    }

    .chat-footer {
      flex-shrink: 0;
      padding: 1.25rem;
      background: white;
      // border-top: 1px solid #e5e6eb;
      display: flex;
      justify-content: center;
      
      .footer-input-wrapper {
        width: 100%;
        max-width: 50rem;
      }
    }
  }
}
</style>