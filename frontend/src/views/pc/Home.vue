<!--
文件名：frontend/src/views/pc/Home.vue
作者：zcl
日期：2026-01-27
描述：PC端主页组件 (集成聊天功能) - 修复顶部导航栏+聊天输入框
-->
<script setup lang="ts">
import { ref, watch, nextTick, onMounted } from 'vue';
import { useRouter } from 'vue-router';
import { useAppStore, useChatStore, useUserStore } from '@/stores';
import SimilarityDialog from '@/components/business/SimilarityDialog.vue';
import { ElMessage, ElImageViewer } from 'element-plus';
import { useSpeechRecognition, useFileUpload, useSkills } from '@/composables';
import { SkillSelector, ChatInput, MessageList } from '@/modules/chat';
import { fetchDifyConversations, fetchConversationMessages, renameDifyConversation, deleteDifyConversation } from '@/api/dify';
import type { DifyConversation } from '@/types/chat';
import { MoreFilled, Delete, Edit } from '@element-plus/icons-vue';
import { ElMessageBox } from 'element-plus';
import { PC_TEXT, MOBILE_TEXT } from '@/constants/texts';
import DocumentToolDialog from '@/components/business/DocumentToolDialog.vue';

const router = useRouter();
const appStore = useAppStore();
const chatStore = useChatStore();
const userStore = useUserStore();
const showSimilarityDialog = ref(false);
const showMeetingRecorder = ref(false);
const showDocumentDialog = ref(false);
const { isListening, result, toggleListening } = useSpeechRecognition();
const { uploadedFiles, showViewer, previewUrlList, initialIndex, handleFileSelect, removeFile, handlePreview, closeViewer, clearFiles } = useFileUpload();
const { activeSkill, visibleSkills, moreSkills, moreSkillItem, handleSkillClick, removeSkill } = useSkills();

const inputMessage = ref('');
const messageListRef = ref<InstanceType<typeof MessageList> | null>(null);
const isDeepThinking = ref(false);
const isLoadingHistory = ref(false);

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
  
  // 2. 立即清空 UI 输入状态 (让用户感觉响应快)
  inputMessage.value = '';
  clearFiles();
  activeSkill.value = null;

  // 3. 调用 Store Action
  await chatStore.sendMessage(
    content,
    currentFiles,
    currentSkill,
    () => {
      // 当新会话创建时，刷新会话列表
      setTimeout(() => {
        loadConversations();
      }, 1000);
    }
  );
};

const handleStop = () => {
  chatStore.stopGenerating();
};

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
    // 简单起见，我们模拟用户重新输入了这条消息
    inputMessage.value = lastUserMsgContent;
    
    // 尝试提取纯文本 (移除 [文件: ...] 前缀)
    const fileRegex = /^(\[文件: .*?\]\s*)+/;
    const match = lastUserMsgContent.match(fileRegex);
    if (match) {
        inputMessage.value = lastUserMsgContent.replace(fileRegex, '').trim();
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
  const username = userStore.username;
  if (!username || username === '未登录') return;
  try {
    const res = await fetchDifyConversations(username);
    if (res && res.data) {
      chatStore.difyConversations = (res.data as unknown) as DifyConversation[];
      // 自动加载第一条会话，避免进入后空白
      if (
        !chatStore.difySessionId &&
        Array.isArray(chatStore.difyConversations) &&
        chatStore.difyConversations.length > 0
      ) {
        const first = chatStore.difyConversations[0];
        if (first && first.id) {
          try {
            await handleSwitchSession(first.id);
          } catch (err) {
            console.error('自动切换首会话失败', err);
          }
        }
      }
    }
  } catch (e) {
    console.error('加载历史会话失败', e);
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

// 初始化用户信息
onMounted(async () => {
  await userStore.init();
  if (userStore.isLoggedIn) {
      loadConversations();
  }
});

const handleSkillSelect = (skill: any) => {
  if (!userStore.isLoggedIn) {
    appStore.openLoginModal();
    return;
  }
  if (skill.label === '会议记录') {
    showMeetingRecorder.value = true;
    return;
  }
  if (skill.label === '文档工具') {
    showDocumentDialog.value = true;
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

const handleLogin = () => {
  appStore.openLoginModal();
};

const handleLogout = () => {
  userStore.logout();
};

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

const onConversationCommand = (cmd: 'rename' | 'delete', conv: DifyConversation) => {
  if (cmd === 'rename') handleRenameConversation(conv);
  else handleDeleteConversation(conv);
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
            <span class="chat-title">{{ conv.name || '未命名对话' }}</span>
            
            <el-dropdown trigger="click" @command="(cmd) => onConversationCommand(cmd, conv)" class="chat-actions">
              <span class="el-dropdown-link" @click.stop>
                <el-icon><MoreFilled /></el-icon>
              </span>
              <template #dropdown>
                <el-dropdown-menu>
                  <el-dropdown-item command="rename" :icon="Edit">重命名</el-dropdown-item>
                  <el-dropdown-item command="delete" :icon="Delete" style="color: var(--el-color-danger)">删除</el-dropdown-item>
                </el-dropdown-menu>
              </template>
            </el-dropdown>
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
        <div class="footer-item">{{ PC_TEXT.sidebarFooter }}</div>
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
            <span class="welcome-text">{{ PC_TEXT.topBar.welcomePrefix }}{{ userStore.username }}</span>
            <button class="logout-btn" @click="handleLogout">{{ PC_TEXT.topBar.logout }}</button>
          </div>
          <button v-else class="login-btn" @click="handleLogin">{{ PC_TEXT.topBar.login }}</button>
        </div>
      </header>

      <!-- 内容主体：flex占满剩余高度，作为flex第二项 -->
      <div class="content-body">
        <!-- 聊天模式：加载历史或有消息或已选择会话时显示 -->
        <div class="chat-layout" v-if="chatStore.messages.length > 0 || isLoadingHistory || chatStore.difySessionId">
          <div v-if="isLoadingHistory" class="loading-overlay">
            <div class="spinner"></div>
            <div class="loading-text">正在加载历史消息...</div>
          </div>
          <MessageList 
            v-if="!isLoadingHistory"
            :messages="chatStore.messages" 
            ref="messageListRef"
            @regenerate="handleRegenerate"
          />
          <!-- 底部输入区域 -->
          <div class="chat-footer" v-if="!isLoadingHistory">
            <div class="footer-input-wrapper">
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
      <DocumentToolDialog
        v-if="showDocumentDialog"
        :visible="showDocumentDialog"
        @update:visible="(val) => showDocumentDialog = val"
      />
    </main>

    <MeetingRecorder 
      v-if="showMeetingRecorder" 
      @close="showMeetingRecorder = false" 
    />

    <!-- 图片预览组件 (挂载到 body 以确保全屏覆盖) -->
    <Teleport to="body">
      <el-image-viewer
        v-if="showViewer"
        :url-list="previewUrlList"
        :initial-index="initialIndex"
        @close="closeViewer"
      />
    </Teleport>
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
      display: flex;
      justify-content: space-between;
      align-items: center;
      
      .chat-title {
        overflow: hidden;
        text-overflow: ellipsis;
        flex: 1;
      }
      
      .chat-actions {
        opacity: 0;
        transition: opacity 0.2s;
        margin-left: 0.5rem;
        flex-shrink: 0;
        
        .el-icon {
          font-size: 1rem;
          color: #86909c;
          padding: 0.125rem;
          border-radius: 0.125rem;
          &:hover {
             background-color: rgba(0,0,0,0.05);
             color: #1d2129;
          }
        }
      }

      &:hover { 
        background-color: #e5e6eb; 
        .chat-actions {
           opacity: 1;
        }
      }
      
      &.active { 
        background-color: #e8f3ff; 
        color: #165dff; 
        .chat-actions {
           opacity: 1; /* 选中时常显 */
        }
      }
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
  position: relative;
    
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

  .loading-overlay {
    position: absolute;
    top: 0;
    left: 0;
    right: 0;
    bottom: 0;
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    background: #ffffff;
    z-index: 5;
    .loading-text {
      margin-top: 0.75rem;
      color: #606266;
      font-size: 0.875rem;
    }
    .spinner {
      width: 2rem;
      height: 2rem;
      border: 0.25rem solid #e5e6eb;
      border-top-color: #165dff;
      border-radius: 50%;
      animation: spin 0.8s linear infinite;
    }
  }
  @keyframes spin {
    to { transform: rotate(360deg); }
  }
}
</style>
