<!--
文件名：frontend/src/components/business/home/MobileSidebar.vue
作者：zcl
日期：2026-02-11
描述：移动端主页侧边栏组件
-->
<script setup lang="ts">
import { useAppStore, useChatStore, useUserStore } from '@/stores';
import { MOBILE_TEXT } from '@/constants/texts';
import { MoreFilled, Delete, Edit } from '@element-plus/icons-vue';
import type { DifyConversation } from '@/types/chat';

const appStore = useAppStore();
const chatStore = useChatStore();
const userStore = useUserStore();

const props = defineProps<{
  handleNewChat: () => void;
  handleSwitchSession: (id: string) => Promise<void>;
  handleRenameConversation: (conv: DifyConversation) => Promise<void>;
  handleDeleteConversation: (conv: DifyConversation) => Promise<void>;
  recentItems: Array<{ id: string; title: string; type: 'local' | 'dify' }>;
}>();

const handleRecentClick = (item: { id: string; type: 'local' | 'dify' }) => {
  if (item.type === 'local') {
    chatStore.switchSession(item.id);
  } else {
    props.handleSwitchSession(item.id);
  }
  appStore.closeMobileSidebar();
};
</script>

<template>
  <div>
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
        <button class="new-chat-btn" @click="handleNewChat">{{ MOBILE_TEXT.sidebar.newChatBtn }}</button>
      </div>

      <div class="recent-chats">
        <div class="section-title">{{ MOBILE_TEXT.sidebar.recentSectionTitle }}</div>
        <div
          v-for="item in recentItems"
          :key="`${item.type}-${item.id}`"
          class="chat-item"
          @click="handleRecentClick(item)"
        >
          <span>{{ item.title }}</span>
          <template v-if="item.type === 'dify'">
            <el-popover
              placement="left"
              trigger="click"
              :width="180"
              popper-class="mobile-action-popover"
            >
              <div class="action-menu">
                <button 
                  class="menu-item" 
                  @click.stop="handleRenameConversation(chatStore.difyConversations.find(c=>c.id===item.id)!)"
                >
                  <el-icon><Edit /></el-icon>
                  <span>重命名</span>
                </button>
                <button 
                  class="menu-item danger" 
                  @click.stop="handleDeleteConversation(chatStore.difyConversations.find(c=>c.id===item.id)!)"
                >
                  <el-icon><Delete /></el-icon>
                  <span>删除</span>
                </button>
              </div>
              <template #reference>
                <button class="mini-icon-btn" @click.stop>
                  <el-icon><MoreFilled /></el-icon>
                </button>
              </template>
            </el-popover>
          </template>
        </div>
      </div>
      
      <div class="sidebar-footer">
        <button class="footer-btn">{{ MOBILE_TEXT.sidebar.aboutBtn }}</button>
      </div>
    </aside>
  </div>
</template>

<style scoped lang="scss">
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
        img {
          width: 100%;
          height: 100%;
          border-radius: 50%;
          object-fit: cover;
        }
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
      display: flex;
      align-items: center;
      justify-content: space-between;
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

.mini-icon-btn {
  background: none;
  border: none;
  padding: 0.25rem;
  border-radius: 0.375rem;
  color: #86909c;
}
.mini-icon-btn:active {
  background-color: rgba(0,0,0,0.06);
}

.mobile-action-popover {
  padding: 0.5rem;
}
.action-menu {
  display: flex;
  flex-direction: column;
  gap: 0.25rem;
}
.menu-item {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  width: 100%;
  padding: 0.5rem 0.75rem;
  border: 1px solid #e5e6eb;
  border-radius: 0.5rem;
  background: #fff;
  color: #1d2129;
}
.menu-item:active {
  background: #f2f3f5;
}
.menu-item.danger {
  border-color: #ffccc7;
  color: #f56c6c;
}
</style>
