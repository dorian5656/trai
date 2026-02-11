<!--
文件名：frontend/src/views/mobile/Home.vue
作者：zcl
日期：2026-02-11
描述：移动端主页组件
-->
<script setup lang="ts">
import { useHomeLogic } from '@/composables/useHomeLogic';
import MobileSidebar from '@/components/business/home/MobileSidebar.vue';
import { ElImageViewer } from 'element-plus';
import { ChatInput, MessageList } from '@/modules/chat';
import SimilarityDialog from '@/components/business/SimilarityDialog.vue';
import MeetingRecorder from '@/components/business/MeetingRecorder.vue';
import DocumentToolDialog from '@/components/business/DocumentToolDialog.vue';
import { MOBILE_TEXT } from '@/constants/texts';

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
  allSkills, activeSkill, removeSkill,
  // Chat Session
  isLoadingHistory, loadConversations, handleSwitchSession, handleNewChat, handleRenameConversation, handleDeleteConversation,
  // Layout State
  inputMessage, isDeepThinking, showSimilarityDialog, showMeetingRecorder, showDocumentDialog, toggleDeepThinking, handleLogin, handleLogout, handleStop,
  // Actions
  handleSend, handleRegenerate, handleSkillSelect, mixedRecentItems
} = useHomeLogic();
</script>

<template>
  <div class="mobile-container">
    <!-- 侧边栏 -->
    <MobileSidebar
      :handle-new-chat="handleNewChat"
      :handle-switch-session="handleSwitchSession"
      :handle-rename-conversation="handleRenameConversation"
      :handle-delete-conversation="handleDeleteConversation"
      :recent-items="mixedRecentItems"
    />

    <!-- 顶部导航 -->
    <header class="mobile-header">
      <div class="left">
        <button class="icon-btn" @click="appStore.toggleMobileSidebar">☰</button>
        <button class="new-chat-pill" @click="handleNewChat">{{ MOBILE_TEXT.header.newChatPill }}</button>
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
      <div v-if="chatStore.messages.length > 0 || isLoadingHistory" class="chat-layout">
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
            @click="handleSkillSelect(skill)"
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
      @update:visible="(val: boolean) => showSimilarityDialog = val"
    />

    <!-- 会议记录组件 -->
    <MeetingRecorder 
      v-if="showMeetingRecorder" 
      @close="showMeetingRecorder = false" 
    />
    <DocumentToolDialog
      v-if="showDocumentDialog"
      :visible="showDocumentDialog"
      @update:visible="(val: boolean) => showDocumentDialog = val"
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

/* Sidebar styles removed (moved to MobileSidebar.vue) */

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
