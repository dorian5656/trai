<!--
文件名：frontend/src/components/business/home/Sidebar.vue
作者：zcl
日期：2026-02-11
描述：PC端主页侧边栏组件
-->
<script setup lang="ts">
import { useAppStore, useChatStore, useUserStore } from '@/stores';
import type { DifyConversation } from '@/types/chat';
import { MoreFilled, Delete, Edit } from '@element-plus/icons-vue';
import { PC_TEXT } from '@/constants/texts';

const appStore = useAppStore();
const chatStore = useChatStore();
const userStore = useUserStore();

const props = defineProps<{
  handleNewChat: () => void;
  handleSwitchSession: (id: string) => Promise<void>;
  handleRenameConversation: (conv: DifyConversation) => Promise<void>;
  handleDeleteConversation: (conv: DifyConversation) => Promise<void>;
}>();

const onConversationCommand = (cmd: 'rename' | 'delete', conv: DifyConversation) => {
  if (cmd === 'rename') props.handleRenameConversation(conv);
  else props.handleDeleteConversation(conv);
};
</script>

<template>
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
          
          <el-dropdown trigger="click" @command="(cmd: any) => onConversationCommand(cmd, conv)" class="chat-actions">
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
</template>

<style scoped lang="scss">
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
      img {
        width: 100%;
        height: 100%;
        border-radius: 50%;
        object-fit: cover;
      }
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
</style>
