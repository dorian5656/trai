<!--
文件名：frontend/src/components/business/home/MessageList.vue
作者：zcl
日期：2026-01-28
描述：消息列表组件
-->
<script setup lang="ts">
import { ref, watch, nextTick } from 'vue';
import { renderMarkdown } from '@/utils/markdown';
import { icons } from '@/assets/icons';
import { ElMessage } from 'element-plus';

interface Message {
  id: string;
  role: 'user' | 'assistant';
  content: string;
}

const props = defineProps<{
  messages: Message[];
}>();

const emit = defineEmits<{
  (e: 'regenerate'): void;
}>();

const chatContainerRef = ref<HTMLElement | null>(null);

const scrollToBottom = () => {
  nextTick(() => {
    if (chatContainerRef.value) {
      chatContainerRef.value.scrollTop = chatContainerRef.value.scrollHeight;
    }
  });
};

// 复制功能
const copyMessage = (content: string) => {
  if (navigator.clipboard) {
    navigator.clipboard.writeText(content).then(() => {
      ElMessage.success('复制成功');
    }).catch(() => {
      ElMessage.error('复制失败');
    });
  } else {
    // 降级方案
    const textarea = document.createElement('textarea');
    textarea.value = content;
    document.body.appendChild(textarea);
    textarea.select();
    try {
      document.execCommand('copy');
      ElMessage.success('复制成功');
    } catch (err) {
      ElMessage.error('复制失败');
    }
    document.body.removeChild(textarea);
  }
};

// 监听消息数量变化
watch(() => props.messages.length, () => {
  scrollToBottom();
});

// 监听最后一条消息内容变化 (流式输出)
watch(() => props.messages[props.messages.length - 1]?.content, () => {
  scrollToBottom();
});

defineExpose({
  scrollToBottom
});
</script>

<template>
  <div class="chat-wrapper">
    <div class="message-list" ref="chatContainerRef">
      <div 
        v-for="(msg, index) in messages" 
        :key="msg.id" 
        class="message-row"
        :class="msg.role"
      >
        <!-- 头像 -->
        <div class="avatar-container">
          <div class="avatar">{{ msg.role === 'user' ? '你' : 'AI' }}</div>
        </div>

        <!-- 消息内容区 -->
        <div class="message-content-wrapper">
          <div class="sender-name">{{ msg.role === 'user' ? '我' : '驼人GPT' }}</div>
          
          <div class="content-bubble">
             <div v-if="msg.role === 'assistant'" class="markdown-body" v-html="renderMarkdown(msg.content)"></div>
             <div v-else>{{ msg.content }}</div>
          </div>

          <!-- AI 消息下方的操作栏 -->
          <div v-if="msg.role === 'assistant' && msg.content" class="message-actions">
            <button class="action-btn" title="复制" @click="copyMessage(msg.content)">
              <span class="icon" v-html="icons.copy"></span>
            </button>
            <button 
              v-if="index === messages.length - 1" 
              class="action-btn" 
              title="重新生成" 
              @click="emit('regenerate')"
            >
              <span class="icon" v-html="icons.regenerate"></span>
            </button>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped lang="scss">
.chat-wrapper {
  flex: 1;
  overflow-y: auto;
  padding: 1.25rem;
  display: flex;
  flex-direction: column;
  margin-top: 3.75rem; // 避开 top-bar

  .message-list {
    max-width: 60vw;
    margin: 0 auto;
    width: 100%;
    padding-bottom: 12vh;
    overflow-y: auto; 
    height: 100%;

    @media (max-width: 768px) {
      max-width: 95vw;
    }
  }

  .message-row {
    display: flex;
    margin-bottom: 1.5rem;
    align-items: flex-start;
    gap: 1rem;
    
    .avatar-container {
      flex-shrink: 0;
      .avatar {
        width: 2.5rem;
        height: 2.5rem;
        border-radius: 50%;
        background: #f2f3f5;
        display: flex;
        align-items: center;
        justify-content: center;
        font-size: 0.875rem;
        color: #4e5969;
        font-weight: 600;
      }
    }

    .message-content-wrapper {
      display: flex;
      flex-direction: column;
      max-width: 80%;
      
      .sender-name {
        font-size: 0.75rem;
        color: #86909c;
        margin-bottom: 0.25rem;
      }

      .content-bubble {
        padding: 0.75rem 1rem;
        border-radius: 0.75rem;
        line-height: 1.6;
        font-size: 0.9375rem;
        word-break: break-word;
        
        :deep(.markdown-body) {
          p { margin-bottom: 0.625rem; }
          p:last-child { margin-bottom: 0; }
          pre { background: #f7f8fa; padding: 0.75rem; border-radius: 0.375rem; overflow-x: auto; color: #333; border: 1px solid #e5e6eb; }
          code { font-family: 'Consolas', monospace; color: #c7254e; background-color: #f9f2f4; padding: 2px 4px; border-radius: 4px; }
          pre code { color: inherit; background-color: transparent; padding: 0; }
        }
      }

      .message-actions {
        display: flex;
        gap: 0.5rem;
        margin-top: 0.5rem;
        opacity: 0; // 默认隐藏，hover时显示
        transition: opacity 0.2s;

        .action-btn {
          background: none;
          border: none;
          cursor: pointer;
          color: #86909c;
          padding: 0.25rem;
          border-radius: 0.25rem;
          transition: all 0.2s;
          display: flex;
          align-items: center;
          justify-content: center;

          &:hover {
            background: #f2f3f5;
            color: #4e5969;
          }

          .icon {
            width: 1rem;
            height: 1rem;
            display: block;
          }
        }
      }
    }

    &:hover {
      .message-actions {
        opacity: 1;
      }
    }

    // AI 样式 (默认)
    &.assistant {
      .content-bubble {
        background: transparent; // AI 不需要气泡背景，类似 ChatGPT 的文本流
        padding-left: 0; // 对齐头像
      }
    }

    // User 样式 (右对齐)
    &.user {
      flex-direction: row-reverse;
      
      .avatar-container {
        .avatar {
          background: #e8f3ff;
          color: #165dff;
        }
      }

      .message-content-wrapper {
        align-items: flex-end; // 内容右对齐

        .sender-name {
          display: none; // 用户通常不显示名字
        }

        .content-bubble {
          background: #e8f3ff;
          color: #1d2129;
          border-top-right-radius: 0.25rem; // 右上角直角，模拟气泡方向
        }
      }
    }
  }
}
</style>
