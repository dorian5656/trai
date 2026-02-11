<!--
文件名：frontend/src/views/pc/Home.vue
作者：zcl
日期：2026-02-11
描述：PC端主页组件 (集成聊天功能)
-->
<script setup lang="ts">
import { useHomeLogic } from '@/composables/useHomeLogic';
import Sidebar from '@/components/business/home/pc/Sidebar.vue';
import SimilarityDialog from '@/components/business/SimilarityDialog.vue';
import { ElImageViewer } from 'element-plus';
import { SkillSelector, ChatInput, MessageList } from '@/modules/chat';
import { PC_TEXT, MOBILE_TEXT } from '@/constants/texts';
import DocumentToolDialog from '@/components/business/DocumentToolDialog.vue';
import MeetingRecorder from '@/components/business/MeetingRecorder.vue';

const {
  appStore,
  chatStore,
  userStore,
  messageListRef,
  // Speech
  isListening, result, toggleListening,
  // File Upload
  uploadedFiles, showViewer, previewUrlList, initialIndex, handleFileSelect, removeFile, handlePreview, closeViewer, clearFiles,
  // Skills
  activeSkill, visibleSkills, moreSkills, moreSkillItem, removeSkill,
  // Chat Session
  isLoadingHistory, loadConversations, handleSwitchSession, handleNewChat, handleRenameConversation, handleDeleteConversation,
  // Layout State
  inputMessage, isDeepThinking, showSimilarityDialog, showMeetingRecorder, showDocumentDialog, toggleDeepThinking, handleLogin, handleLogout, handleStop,
  // Actions
  handleSend, handleRegenerate, handleSkillSelect
} = useHomeLogic();
</script>

<template>
  <div class="pc-container">
    <!-- 侧边栏 -->
    <Sidebar 
      :handle-new-chat="handleNewChat"
      :handle-switch-session="handleSwitchSession"
      :handle-rename-conversation="handleRenameConversation"
      :handle-delete-conversation="handleDeleteConversation"
    />

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
        @update:visible="(val: boolean) => showSimilarityDialog = val"
      />
      <DocumentToolDialog
        v-if="showDocumentDialog"
        :visible="showDocumentDialog"
        @update:visible="(val: boolean) => showDocumentDialog = val"
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

/* Sidebar styles removed (moved to Sidebar.vue) */

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
