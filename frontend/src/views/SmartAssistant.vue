<!--
文件名：frontend/src/views/SmartAssistant.vue
作者：zcl
日期：2026-01-28
描述：智能助手对话页面 (集成官网路由与嵌入式Widget支持)
-->
<template>
  <div>
    <div
      class="chat-window"
      :class="{ 'is-maximized': isMaximized }"
      ref="chatWindowRef"
    >
      <div class="chat-header"> 
        <div class="header-icons">
          <!-- 预留控制按钮 -->
        </div>
      </div>

      <div class="chat-body">
        <div v-if="!conversationStarted" class="welcome-container">
          <div class="chat-avatar-wrapper">
            <img :src="AiAvatarImg" alt="AI助手" class="chat-avatar-img"/>
          </div>
          <div class="message-box">
            <p class="greeting">您好，我是智小驼 (测试版)</p>
            <p class="intro">任何关于驼人集团的问题都可以问我，请在输入框输入您的问题。</p>
          </div>
          <div class="example-questions">
            <p class="title">您可以试着这样问：</p>
            <div v-for="(q, i) in randomQuestions" :key="i" @click="askQuestion(q)" class="question">{{ q }}</div>
          </div>
        </div>

        <div v-else ref="chatHistoryRef" class="chat-history" @wheel="handleScrollLock">
          <div v-for="msg in messages" :key="msg.id" class="message-row" :class="`message-${msg.sender}`">
            <div v-if="msg.sender === 'ai'" class="ai-avatar">
              <img :src="AiAvatarImg" alt="AI" />
            </div>
            <div class="message-wrapper">
              <div class="message-content" v-html="msg.renderedText"
                   :class="{'thinking': isThinking && msg === messages[messages.length - 1] && msg.sender === 'ai'}" />
            </div>
          </div>
        </div>

        <div class="chat-input-area">
          <input ref="inputRef" v-model="userInput" @keyup.enter="askQuestion(userInput)" placeholder="请输入您的问题" />
          <button @click="canStop ? stopReplying() : askQuestion(userInput)" :disabled="!canSend && !canStop">
            <svg v-if="canStop" width="20" height="20" viewBox="0 0 24 24" fill="currentColor">
              <path d="M6 6h12v12H6z"/>
            </svg>
            <svg v-else width="20" height="20" viewBox="0 0 24 24" fill="currentColor">
              <path d="M2.01 21L23 12 2.01 3 2 10l15 2-15 2 .01 9z"/>
            </svg>
          </button>
        </div>
        <div class="chat-footer">
          内容由AI生成，仅供参考
        </div>
      </div>
      
      <!-- 关闭确认弹窗 -->
      <div v-if="showCloseConfirm" class="chat-confirm-overlay" @click="showCloseConfirm = false">
        <div class="chat-confirm-dialog" @click.stop>
          <div class="confirm-body">
            <p>请留下您的联系方式和感兴趣的产品/业务，我们能更好地为您服务！</p>
            <div class="confirm-buttons">
              <button @click="cancelClose" class="confirm-btn">点击留资</button>
              <button @click="confirmClose" class="cancel-btn">仍要关闭</button>
            </div>
          </div>
        </div>
      </div>
    </div>

    <ContactForm 
      v-if="showCustomForm" 
      @close="showCustomForm = false" 
      @submit="handleCustomFormSubmit" 
    />
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted, nextTick, watchEffect, watch } from 'vue';
import ContactForm from '@/components/ContactForm.vue';
import AiAvatarImg from '@/assets/images/smart-assistant.png';
import { ElMessage } from 'element-plus';
import MarkdownIt from 'markdown-it';
import hljs from 'highlight.js';
import 'highlight.js/styles/github-dark.css';

import { streamDifyChat } from '@/utils/stream';
import { getPresetQuestions } from '@/api/questions';
import { getLocationBasedUserId, saveUserIdToCookie } from '@/utils/location';
import { useChatStore } from '@/stores/chat';
import { submitCustomerInfo } from '@/api/customer';

// 定义 Props
const props = defineProps({
  showChatDirectly: {
    type: Boolean,
    default: true
  }
});

// Markdown 配置
const md = new MarkdownIt({
  html: true, // 开启 HTML 以支持自定义交互链接
  linkify: true,
  breaks: true,
  highlight: function (str, lang) {
    if (lang && hljs.getLanguage(lang)) {
      try {
        return '<pre class="hljs"><code>' +
               hljs.highlight(str, { language: lang, ignoreIllegals: true }).value +
               '</code></pre>';
      } catch (__) {}
    }
    return '<pre class="hljs"><code>' + md.utils.escapeHtml(str) + '</code></pre>';
  }
});

// 自定义链接渲染 (在新标签页打开)
const defaultRenderLink = md.renderer.rules.link_open || function(tokens, idx, options, env, self) {
  return self.renderToken(tokens, idx, options);
};
md.renderer.rules.link_open = function (tokens, idx, options, env, self) {
  const token = tokens[idx];
  token.attrSet('target', '_blank');
  token.attrSet('rel', 'noopener noreferrer');
  return defaultRenderLink(tokens, idx, options, env, self);
};

interface Message {
  id: string;
  sender: 'user' | 'ai';
  text: string;
  renderedText: string;
}

declare global {
  interface Window {
    openContactForm: () => void;
    showCloseConfirmDialog: () => void;
    showContactFormDialog: () => void;
  }
}

// 状态定义
  const isMaximized = ref(false);
  const userInput = ref('');const messages = ref<Message[]>([]);
const conversationStarted = ref(false);
const isThinking = ref(false);
const isReplying = ref(false);
const currentDifyConversationId = ref<string | null>(null);
const chatHistoryRef = ref<HTMLElement | null>(null);
const inputRef = ref<HTMLInputElement | null>(null);
const chatWindowRef = ref<HTMLElement | null>(null);
const showCustomForm = ref(false);
const showCloseConfirm = ref(false);
const presetQuestions = ref<string[]>([]);
const randomQuestions = ref<string[]>([]);
const currentUserId = ref('');

const chatStore = useChatStore();

// 计算属性
const canSend = computed(() => userInput.value.trim().length > 0);
const canStop = computed(() => isReplying.value && chatStore.abortController !== null);

// 监听 CustomForm 显示状态，通知父级 iframe
watch(showCustomForm, (newVal) => {
  if (window.parent !== window) {
    window.parent.postMessage({
      type: 'setControlsVisibility',
      visible: !newVal
    }, '*');
  }
});

// 方法
const generateId = () => `${Date.now()}-${Math.random().toString(36).slice(-6)}`;

const parseMarkdown = (text: string, processLinks = true): string => {
  if (!text) return '';
  try {
    let processedText = text;
    if (processLinks) {
        // 将 [点击留下](contact) 转换为特殊的 HTML
        processedText = text.replace(/\[点击留下\]\(contact\)/g, '<span class="leave-contact" style="cursor: pointer; color: #2473ba; text-decoration: underline;">点击留下</span>');
    }
    return md.render(processedText);
  } catch {
    return text;
  }
};

const scrollToBottom = () => nextTick(() => {
  if (chatHistoryRef.value) {
    chatHistoryRef.value.scrollTo({
      top: chatHistoryRef.value.scrollHeight,
      behavior: 'smooth'
    });
  }
});

const updateLastMessage = (text: string) => {
  if (messages.value.length === 0) return;
  const lastMessage = messages.value[messages.value.length - 1];
  lastMessage.text = text;
  lastMessage.renderedText = parseMarkdown(text);
  scrollToBottom();
};

const addMessage = (sender: 'user' | 'ai', text: string) => {
  const msgId = generateId();
  let renderedText = parseMarkdown(text, true);
  
  // 替换留资链接为 postMessage 调用 (如果需要与父页面交互)
  if (text.includes('<span class="leave-contact"')) {
    renderedText = renderedText.replace(
      /<span class="leave-contact" style="cursor: pointer; color: #2473ba; text-decoration: underline;">点击留下<\/span>/g,
      `<span class="leave-contact" onclick="window.parent.postMessage({type:'openContactForm', source:'${msgId}'}, '*')">点击留下</span>`
    );
  }

  messages.value.push({
    id: msgId,
    sender,
    text,
    renderedText,
  });
  scrollToBottom();
};

const handleCustomFormSubmit = async (data: any) => {
  try {
    const response = await submitCustomerInfo(data);
    if (response.success) {
       showCustomForm.value = false;
       addMessage('ai', '感谢您的留资，我们将尽快与您联系。');
       ElMessage.success('表单提交成功！');
    } else {
       ElMessage.error(response.message || '提交失败');
    }
  } catch (error) {
     console.error(error);
     ElMessage.error('提交失败，请稍后重试');
  }
};

const stopReplying = () => {
  if (chatStore.abortController) {
    chatStore.abortController.abort();
    chatStore.abortController = null;
    isReplying.value = false;
    isThinking.value = false;
    ElMessage.info('已停止生成');
  }
};

const askQuestion = async (question: string) => {
  const text = question.trim();
  if (!text || isReplying.value) return;

  isReplying.value = true;
  isThinking.value = true;
  conversationStarted.value = true;
  
  addMessage('user', text);
  userInput.value = '';

  addMessage('ai', '正在思考......');

  // Dify 流式请求
  const userId = currentUserId.value || 'guest_user';
  
  await streamDifyChat(
    {
        query: text,
        user: userId,
        conversation_id: currentDifyConversationId.value || undefined,
        app_name: 'guanwang' // 指定为官网助手
    },
    (streamText, conversationId) => {
        isThinking.value = false;
        updateLastMessage(streamText);
        if (conversationId) {
            currentDifyConversationId.value = conversationId;
        }
    },
    () => { // onDone
        isReplying.value = false;
        isThinking.value = false;
        // 如果是第一句，追加引导
        const userMsgCount = messages.value.filter(m => m.sender === 'user').length;
        if (userMsgCount <= 1) {
            setTimeout(() => {
                addMessage('ai', '感谢您的咨询！如果您对我们的产品感兴趣，请[点击留下](contact)您的联系方式和感兴趣的产品/业务，我们将有专人与您联系。');
            }, 1000);
        }
    },
    (err) => { // onError
        console.error(err);
        isReplying.value = false;
        isThinking.value = false;
        updateLastMessage('网络异常，请稍后重试');
        ElMessage.error('请求失败');
    }
  );
};

// Iframe 交互逻辑
const handleIframeMessage = (event: MouseEvent) => {
  const target = event.target as HTMLElement;
  if (window.parent !== window) {
    window.parent.postMessage({
      type: 'iframeClick',
      element: target.tagName,
      text: target.textContent,
      id: target.id
    }, '*');
  }
};

const handleScrollLock = (event: WheelEvent) => {
  const element = event.currentTarget as HTMLElement;
  if (!element) return;
  const { scrollTop, scrollHeight, clientHeight } = element;
  const isAtBottom = scrollTop + clientHeight >= scrollHeight - 1;
  if ((event.deltaY > 0 && isAtBottom) || (event.deltaY < 0 && scrollTop === 0)) {
    // 阻止滚动冒泡到父页面
    // event.preventDefault(); 
  }
};

const confirmClose = () => {
  showCloseConfirm.value = false;
  if (window.parent !== window) {
    window.parent.postMessage({
      type: 'confirmClose'
    }, '*');
  }
};

const cancelClose = () => {
  showCloseConfirm.value = false;
  showCustomForm.value = true;
};

const showContactFormHandler = (source = '') => {
  showCustomForm.value = true;
};

// 初始化
onMounted(async () => {
  // 检测是否在iframe中
  const isInIframe = window !== window.top;
  if (isInIframe) {
    document.documentElement.setAttribute('data-iframe', 'true');
    console.log('[SmartAssistant] 检测到iframe环境，已应用iframe样式');
  }

  // 用户ID初始化
  const { userId } = await getLocationBasedUserId();
  currentUserId.value = userId;
  saveUserIdToCookie(userId);

  // 获取预设问题
  const res = await getPresetQuestions();
  presetQuestions.value = res.data || [];
  randomQuestions.value = [...presetQuestions.value].sort(() => Math.random() - 0.5).slice(0, 3);

  // 全局方法挂载
  window.showCloseConfirmDialog = () => {
    showCloseConfirm.value = true;
  };
  
  window.openContactForm = () => {
    showContactFormHandler('消息链接');
  };
  window.showContactFormDialog = () => {
    showContactFormHandler('点击链接');
  };

  // 全局点击拦截 (处理留资链接)
  document.body.addEventListener('click', (event) => {
    handleIframeMessage(event);
    const target = event.target as HTMLElement;
    if (target.classList?.contains('leave-contact') || 
        (target.parentElement && target.parentElement.classList?.contains('leave-contact'))) {
      event.preventDefault();
      event.stopPropagation();
      showContactFormHandler('点击链接');
    }
  });

  // 监听来自父页面的消息
  window.addEventListener('message', (event) => {
    if (event.data && event.data.type) {
      if (event.data.type === 'showCloseConfirm') {
        showCloseConfirm.value = true;
        return;
      }
      if (event.data.type === 'formSubmitted') {
         // 处理外部表单提交 (如果有)
         const formData = event.data.formData;
         if (formData) {
             handleCustomFormSubmit(formData);
         }
      }
      else if (event.data.type === 'showSuccessMessage') {
        conversationStarted.value = true;
        const message = event.data.message || `感谢您的留资，我们将尽快与您联系。`;
        addMessage('ai', message);
        ElMessage.success('表单提交成功！');
      }
    }
  });

  // 处理 URL 参数
  const urlParams = new URLSearchParams(window.location.search);
  const questionParam = urlParams.get('question');
  if (questionParam) {
    setTimeout(() => {
      askQuestion(questionParam);
    }, 500);
  }
  
  // 窗口调整
  window.addEventListener('resize', () => {
      if (chatWindowRef.value && props.showChatDirectly) {
        nextTick(scrollToBottom);
      }
  });
});

onUnmounted(() => {
  // @ts-ignore
  window.openContactForm = undefined;
  // @ts-ignore
  window.showCloseConfirmDialog = undefined;
  // @ts-ignore
  window.showContactFormDialog = undefined;
});

watchEffect(() => {
  nextTick(scrollToBottom);
});
</script>

<style lang="scss" scoped>
/* 样式复用自原项目，稍微调整 */
$primary: #2473ba;
$bg: #e6f7ff;
$radius: 20px;
$shadow: rgba(0, 0, 0, 0.15);

@mixin desktop-only { @media (min-width: 1025px) { @content; } }
@mixin tablet { @media (max-width: 1024px) and (min-width: 769px) { @content; } }
@mixin mobile { @media (max-width: 768px) { @content; } }

.chat-window {
  width: 100%;
  height: 100vh;
  min-height: 600px; /* 设置最小高度 */
  background: $bg;
  display: flex;
  flex-direction: column;
  font-family: 'Helvetica Neue', Helvetica, Arial, sans-serif;
  color: #333;
  overflow: hidden;
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  
  /* iframe环境适配 */
  :global(html[data-iframe="true"]) & {
    height: 100%;
    min-height: 500px;
    position: relative; /* iframe下不需要fixed */
  }

  &.is-maximized {
    width: 100%;
    height: 100vh;
  }
  
  /* 移动端适配 */
  @include mobile {
    height: auto;
    min-height: 100vh;
    overflow: visible;
    position: relative;
    
    :global(html[data-iframe="true"]) & {
      min-height: 400px;
    }
  }
}

.chat-header {
  padding: 10px 12px;
  background: rgba(255, 255, 255, 0.5);
  display: flex;
  justify-content: flex-end;
  
  @include mobile {
    font-size: 15px;
    padding: 10px 12px;
  }
}

.chat-body {
  flex: 1;
  padding: 0 20px;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  max-width: 800px;
  margin: 0 auto;
  width: 100%;
  box-sizing: border-box;
  
  @include mobile {
    padding: 0 15px 10px 15px;
  }
}

.welcome-container {
  flex: 1;
  display: flex;
  flex-direction: column;
  justify-content: center;
  align-items: center;
  width: 100%;
  overflow-y: auto;
  padding-bottom: 20px;

  .chat-avatar-wrapper {
    width: 80px;
    height: 80px;
    margin-bottom: 20px;
    border-radius: 50%;
    background: #fff;
    overflow: hidden;
    img { width: 100%; height: 100%; object-fit: cover; }
    
    @include mobile {
       width: 60px;
       height: 60px;
    }
  }

  .message-box {
    background: rgba(255,255,255,0.7);
    border-radius: 12px;
    padding: 20px;
    text-align: center;
    max-width: 80%;

    .greeting {
      font-weight: 600;
      font-size: 18px;
      margin-bottom: 10px;
      @include mobile { font-size: 16px; }
    }
    .intro {
      font-size: 14px;
      color: #555;
      @include mobile { font-size: 12px; }
    }
  }

  .example-questions {
    margin-top: 30px;
    width: 100%;
    max-width: 400px;
    
    .title {
      font-size: 14px;
      color: #777;
      margin-bottom: 10px;
      text-align: center;
      @include mobile { font-size: 12px; }
    }
    
    .question {
      background: white;
      padding: 10px 15px;
      margin-bottom: 8px;
      border-radius: 20px;
      font-size: 14px;
      color: $primary;
      cursor: pointer;
      text-align: center;
      box-shadow: 0 2px 5px rgba(0,0,0,0.05);
      transition: transform 0.2s;
      
      &:hover {
        transform: translateY(-2px);
        box-shadow: 0 4px 8px rgba(0,0,0,0.1);
      }
      @include mobile { font-size: 12px; padding: 8px 10px; }
    }
  }
}

.chat-history {
  flex: 1;
  overflow-y: auto;
  padding: 20px 0;
  
  @include mobile {
     margin-bottom: 20px;
     padding-bottom: 20px;
  }
  
  .message-row {
    display: flex;
    margin-bottom: 20px;
    gap: 10px;
    
    &.message-user {
      justify-content: flex-end;
      
      .message-wrapper {
        align-items: flex-end;
      }

      .message-content {
        background: $primary;
        color: white;
        border-radius: 12px 12px 0 12px;
        position: relative;
        height: auto;
      }
    }
    
    &.message-ai {
      justify-content: flex-start;
      align-items: flex-start; /* 确保顶对齐 */
      
      .message-wrapper {
        align-items: flex-start;
      }

      .ai-avatar {
        width: 40px;
        height: 40px;
        margin-right: 0; /* gap handles spacing now, but keep 0 to reset if needed */
        border-radius: 50%;
        overflow: hidden;
        flex-shrink: 0;
        background: #fff; /* 确保有背景 */
        img { width: 100%; height: 100%; object-fit: cover; }
        @include mobile { width: 32px; height: 32px; min-width: 32px; }
      }
      .message-content {
        background: white;
        color: #333;
        border-radius: 0 12px 12px 12px;
        box-shadow: 0 2px 8px rgba(0,0,0,0.08);
      }
    }

    .message-wrapper {
      display: flex;
      flex-direction: column;
      max-width: 88%;
    }
    
    .message-content {
      padding: 12px 16px;
      word-break: break-word; /* 参考首页逻辑 */
      line-height: 1.6;
      font-size: 15px;
      position: relative;
      
      @include mobile { font-size: 14px; padding: 10px 12px; max-width: 100%; /* wrapper handles constraint */ }
      
      /* 修复 Markdown 内容样式 */
      :deep(p) { margin: 0 0 8px 0; &:last-child { margin-bottom: 0; } }
      :deep(ul), :deep(ol) { padding-left: 20px; margin: 0 0 8px 0; }
      :deep(pre) { 
        background: #2d2d2d; 
        padding: 12px; 
        border-radius: 6px; 
        overflow-x: auto; 
        color: #f8f8f2; 
        margin: 8px 0;
        font-size: 13px;
      }
      :deep(code) { font-family: monospace; }
      :deep(.leave-contact) { cursor: pointer; color: $primary; text-decoration: underline; }
      
      &.thinking {
        position: relative;
        &:after {
          content: "";
          position: absolute;
          bottom: 10px;
          right: 10px;
          width: 8px;
          height: 8px;
          background-color: $primary;
          border-radius: 50%;
          animation: pulse 1.5s infinite;
        }
      }
    }
  }
}

.chat-input-area {
  padding: 15px 0;
  display: flex;
  gap: 10px;
  
  @include mobile {
     margin: 10px 0 20px 0;
  }
  
  input {
    flex: 1;
    padding: 12px 15px;
    border: 1px solid #ddd;
    border-radius: 25px;
    font-size: 15px;
    outline: none;
    box-shadow: 0 2px 10px rgba(0,0,0,0.05);
    &:focus { border-color: $primary; }
    @include mobile { height: 38px; font-size: 13px; padding: 8px 0 8px 12px; }
  }
  
  button {
    width: 46px;
    height: 46px;
    border-radius: 50%;
    border: none;
    background: $primary;
    color: white;
    font-size: 20px;
    cursor: pointer;
    display: flex;
    justify-content: center;
    align-items: center;
    transition: background 0.3s;
    
    @include mobile { width: 38px; height: 38px; min-width: 38px; }
    
    &:disabled {
      background: #ccc;
      cursor: not-allowed;
    }
    
    &:hover:not(:disabled) {
      background: darken($primary, 10%);
    }
  }
}

.chat-footer {
  text-align: center;
  font-size: 12px;
  color: #999;
  padding-bottom: 10px;
}

/* 确认弹窗样式 */
.chat-confirm-overlay {
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: rgba(0, 0, 0, 0.5);
  display: flex;
  justify-content: center;
  align-items: center;
  z-index: 2000;
}

.chat-confirm-dialog {
  background: white;
  width: 80%;
  max-width: 300px;
  border-radius: 12px;
  padding: 20px;
  text-align: center;
  box-shadow: 0 4px 12px rgba(0,0,0,0.15);
}

.confirm-body p {
  margin: 0 0 20px 0;
  font-size: 14px;
  color: #333;
  line-height: 1.5;
}

.confirm-buttons {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.confirm-btn {
  background: $primary;
  color: white;
  border: none;
  padding: 10px;
  border-radius: 20px;
  font-size: 14px;
  cursor: pointer;
}

.cancel-btn {
  background: #f5f5f5;
  color: #666;
  border: none;
  padding: 10px;
  border-radius: 20px;
  font-size: 14px;
  cursor: pointer;
}

@keyframes pulse {
  0% { transform: scale(0.8); opacity: 0.5; }
  100% { transform: scale(1.5); opacity: 0; }
}
</style>
