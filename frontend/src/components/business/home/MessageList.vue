<!--
文件名：frontend/src/components/business/home/MessageList.vue
作者：zcl
日期：2026-01-28
描述：消息列表组件
-->
<script setup lang="ts">
import { ref, watch, nextTick, onMounted } from 'vue';
import { renderMarkdown } from '@/utils/markdown';
import { icons } from '@/assets/icons';
import { ElMessage } from 'element-plus';
import { ElImageViewer } from 'element-plus';

interface Message {
  id: string;
  role: 'user' | 'assistant' | 'system';
  content: string;
}

const props = defineProps<{
  messages: Message[];
}>();

const emit = defineEmits<{
  (e: 'regenerate'): void;
}>();

const chatContainerRef = ref<HTMLElement | null>(null);
const showViewer = ref(false);
const previewUrlList = ref<string[]>([]);
const initialIndex = ref(0);

const scrollToBottom = () => {
  nextTick(() => {
    if (chatContainerRef.value) {
      chatContainerRef.value.scrollTop = chatContainerRef.value.scrollHeight;
    }
  });
};

const extractImageUrls = (content: string): string[] => {
  const urls: string[] = [];
  const mdImgRegex = /!\[[^\]]*?\]\((.*?)\)/g;
  let match;
  while ((match = mdImgRegex.exec(content)) !== null) {
    if (match[1]) urls.push(match[1]);
  }
  return urls;
};

const onMessageListClick = (e: MouseEvent) => {
  const target = e.target as HTMLElement;
  if (target && target.tagName === 'IMG') {
    const container = target.closest('.markdown-body') as HTMLElement | null;
    if (!container) return;
    const imgs = Array.from(container.querySelectorAll('img'));
    const urls = imgs.map((img) => (img as HTMLImageElement).src).filter(Boolean);
    const idx = urls.indexOf((target as HTMLImageElement).src);
    if (urls.length > 0) {
      previewUrlList.value = urls;
      initialIndex.value = Math.max(0, idx);
      showViewer.value = true;
    }
  }
};

const downloadImagesFromContent = async (content: string) => {
  const urls = extractImageUrls(content);
  if (urls.length === 0) {
    ElMessage.warning('没有可下载的图片');
    return;
  }
  const url = urls[0] as string;
  try {
    const res = await fetch(url);
    const blob = await res.blob();
    const a = document.createElement('a');
    const objectUrl = URL.createObjectURL(blob);
    a.href = objectUrl;
    const filename = url.split('/').pop() || 'image';
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(objectUrl);
    ElMessage.success('开始下载');
  } catch {
    ElMessage.error('下载失败');
  }
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

onMounted(() => {
  scrollToBottom();
});

defineExpose({
  scrollToBottom
});
</script>

<template>
  <div class="chat-wrapper">
    <div class="message-list" ref="chatContainerRef" @click="onMessageListClick">
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
             <div v-else class="markdown-body user-content" v-html="renderMarkdown(msg.content)"></div>
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
            <button 
              class="action-btn" 
              title="下载图片" 
              @click="downloadImagesFromContent(msg.content)"
            >
              <span class="icon" v-html="icons.download"></span>
            </button>
          </div>
        </div>
      </div>
    </div>
    <Teleport to="body">
      <el-image-viewer
        v-if="showViewer"
        :url-list="previewUrlList"
        :initial-index="initialIndex"
        @close="showViewer = false"
      />
    </Teleport>
  </div>
</template>

<style scoped lang="scss">
.chat-wrapper {
  flex: 1;
  overflow-y: hidden;
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
    /* 隐藏滚动条 */
    scrollbar-width: none; /* Firefox */
    -ms-overflow-style: none; /* IE/Edge */
    &::-webkit-scrollbar {
      width: 0;
      height: 0;
      display: none;
    }

    @media (max-width: 48rem) {
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
          code { font-family: 'Consolas', monospace; color: #c7254e; background-color: #f9f2f4; padding: 0.125rem 0.25rem; border-radius: 0.25rem; }
          pre code { color: inherit; background-color: transparent; padding: 0; }
          
          /* 通用图片样式 */
          img {
            max-width: 100%;
            max-height: 50vh;
            width: auto;
            object-fit: contain;
            border-radius: 0.375rem;
            margin: 0.5rem 0;
            display: block;
          }
        }

        @media (max-width: 48rem) {
          :deep(.markdown-body) {
            font-size: 0.875rem;
            line-height: 1.7;
            img {
              max-height: 30vh !important;
              max-width: 75vw !important;
              width: auto !important;
              object-fit: contain;
              margin-left: auto;
              margin-right: auto;
            }
            h1 { font-size: 1.125rem; }
            h2 { font-size: 1.0625rem; }
            h3 { font-size: 1rem; }
            h4, h5, h6 { font-size: 0.9375rem; }
            pre {
              font-size: 0.8125rem;
              max-width: 90vw;
              max-height: 32vh;
              overflow: auto;
            }
            code {
              font-size: 0.8125rem;
              word-break: break-word;
            }
            table {
              display: block;
              max-width: 90vw;
              overflow-x: auto;
              border-collapse: collapse;
            }
            th, td {
              padding: 0.5rem;
              border: 1px solid #e5e6eb;
              text-align: left;
            }
            blockquote {
              border-left: 0.25rem solid #e5e6eb;
              padding-left: 0.75rem;
              color: #4e5969;
            }
            ul, ol {
              padding-left: 1rem;
            }
            a {
              word-break: break-all;
            }
          }
        }

        /* 用户消息特定样式调整 */
        .user-content {
          :deep(a) {
             color: #fff;
             text-decoration: underline;
          }
          :deep(code) {
             background-color: rgba(255, 255, 255, 0.2);
             color: #fff;
          }
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
