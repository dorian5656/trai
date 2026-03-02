<!--
文件名：frontend/src/components/business/CreateMeetingView.vue
作者：whf & zcl
日期：2026-03-02
描述：会议记录创建视图组件
-->
<script setup lang="ts">
import { ref, computed } from 'vue';
import { useWebSocketSpeech } from '@/composables/useWebSocketSpeech';
import { icons } from '@/assets/icons';
import { ElMessage } from 'element-plus';
import { renderMarkdown } from '@/utils/markdown';
import { streamChat } from '@/utils/stream';
import { createMeeting } from '@/api/meeting';

// --- Component State ---
const emit = defineEmits(['saved', 'back']);
const isLoading = ref(false);

// --- Create View State ---
const { isRecording, isConnecting, isProcessingFile, resultText, interimText, startMicrophone, stopMicrophone, uploadAudioFile } = useWebSocketSpeech();
const fileInputRef = ref<HTMLInputElement | null>(null);
const summaryText = ref('');
const isSummarizing = ref(false);
const canGenerateSummary = computed(() => !!resultText.value || !!interimText.value);

// --- Functions ---

const handleFileSelect = (event: Event) => {
  const input = event.target as HTMLInputElement;
  if (input.files && input.files.length > 0) {
    const file = input.files[0];
    if (file) {
      uploadAudioFile(file, async (transcribedText) => {
        if (transcribedText) {
          resultText.value = transcribedText;
        }
      });
      input.value = '';
    }
  }
};

const triggerFileUpload = () => {
  fileInputRef.value?.click();
};

const handleGenerateSummary = async () => {
  if (!canGenerateSummary.value) return;
  const baseText = `${resultText.value}${interimText.value}`;
  const prompt = [
    '你是一个专业的会议纪要助手。',
    '请根据下面的逐字稿内容，用中文生成一份结构化、重点突出、清晰易读的会议纪要。请遵循以下要求：',
    '1. **会议标题**：在纪要开头，根据内容生成一个简洁的标题。',
    '2. **核心议题**：总结会议讨论的核心议题，使用列表形式呈现。',
    '3. **主要结论**：提炼会议达成的关键结论或共识。',
    '4. **待办事项**：明确列出需要跟进的"Action Items"，并指定负责人（如果逐字稿中提到）。',
    '5. **格式**：使用 Markdown 格式，合理运用标题、加粗和列表，让纪要清晰明了。',
    '---',
    '**会议逐字稿:**',
    baseText
  ].join('\n');

  isSummarizing.value = true;
  summaryText.value = '';
  try {
    await streamChat(
      prompt,
      (text) => { summaryText.value = text; },
      () => { isSummarizing.value = false; },
      (err) => { 
        isSummarizing.value = false; 
        ElMessage.error(`生成失败: ${err.message}`); 
      }
    );
  } catch (error) {
    isSummarizing.value = false;
    ElMessage.error('生成纪要时发生未知错误');
  }
};

const saveAndFinish = async () => {
  if (!resultText.value) {
    ElMessage.warning('没有可保存的内容');
    return;
  }
  isLoading.value = true;
  try {
    const newMeeting = await createMeeting({
      title: resultText.value.substring(0, 20) + '...',
      text: resultText.value,
      summary: summaryText.value
    });
    ElMessage.success('保存成功');
    emit('saved', newMeeting.id);
  } catch (e) {
    ElMessage.error('保存失败');
  } finally {
    isLoading.value = false;
  }
};

const stopMicAndSetText = () => {
  stopMicrophone((finalText) => {
    resultText.value = finalText;
  });
};

defineExpose({
  startMicrophone,
  triggerFileUpload
});

</script>

<template>
  <div class="create-view">
    <div class="main-content">
      <div v-if="!resultText && !interimText && !isRecording && !isConnecting" class="placeholder">
        <span v-html="icons.micBig" class="placeholder-icon"></span>
        <p>点击下方按钮开始录音或上传文件</p>
        <p v-if="isProcessingFile">正在处理音频文件，请稍候...</p>
      </div>
      <div v-else class="text-content">
        <span class="final">{{ resultText }}</span>
        <span class="interim">{{ interimText }}</span>
        <span v-if="isRecording" class="cursor">|</span>
      </div>
    </div>

    <div class="summary-section">
      <div class="summary-header">
        <h4>会议纪要</h4>
        <button class="pill-btn" @click="handleGenerateSummary" :disabled="!canGenerateSummary || isSummarizing">
          <span v-if="isSummarizing" class="loading-spinner-small"></span>
          {{ isSummarizing ? '生成中...' : '生成纪要' }}
        </button>
      </div>
      <div class="summary-content" v-html="renderMarkdown(summaryText || '点击按钮开始生成纪要...')" :class="{'placeholder-text': !summaryText}"></div>
    </div>

    <div class="create-footer">
        <button class="pill-btn" @click="emit('back')">
            返回
        </button>
        <button v-if="isRecording" class="pill-btn primary" @click="stopMicAndSetText">
            <span v-html="icons.stop" class="btn-icon"></span>
            停止录音
        </button>
        <button class="pill-btn primary" @click="saveAndFinish" :disabled="!resultText">
            <span v-html="icons.save" class="btn-icon"></span>
            保存并完成
        </button>
    </div>
    <input type="file" ref="fileInputRef" @change="handleFileSelect" accept="audio/*" style="display: none" />
  </div>
</template>

<style scoped>
.create-view {
  display: flex;
  flex-direction: column;
  height: 100%;
  padding: 1rem;
  gap: 1rem;
  background-color: #f7f8fa;
}

.main-content {
  flex: 1;
  overflow-y: auto;
  background: #fff;
  padding: 1.5rem;
  border-radius: 0.5rem;
  border: 1px solid #e5e6eb;
}

.placeholder {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  height: 100%;
  text-align: center;
  color: #86909c;
}
.placeholder-icon {
    width: 3rem;
    height: 3rem;
    margin-bottom: 1rem;
    color: #c9cdd4;
}
.placeholder-icon :deep(svg) {
    width: 100%;
    height: 100%;
}


.text-content {
  white-space: pre-wrap;
  line-height: 1.7;
  font-size: 0.9375rem;
}

.final {
  color: #1d2129;
}

.interim {
  color: #86909c;
}

.cursor {
  animation: blink 1s step-end infinite;
  font-weight: 600;
}

.summary-section {
  padding: 1.5rem;
  background: #fff;
  border-radius: 0.5rem;
  border: 1px solid #e5e6eb;
  display: flex;
  flex-direction: column;
  gap: 1rem;
  max-height: 45%; /* Limit height */
}

.summary-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.summary-header h4 {
    font-size: 1rem;
    font-weight: 600;
    margin: 0;
}

.summary-content {
    flex: 1;
    overflow-y: auto;
    line-height: 1.7;
    font-size: 0.875rem;
    color: #4e5969;
}
.summary-content.placeholder-text {
    color: #86909c;
}

.summary-content :deep(h1),
.summary-content :deep(h2),
.summary-content :deep(h3) {
    margin-top: 1rem;
    margin-bottom: 0.5rem;
    font-weight: 600;
}
.summary-content :deep(ul),
.summary-content :deep(ol) {
    padding-left: 1.2rem;
}


.create-footer {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 0.75rem 1rem;
  border-top: 1px solid #f2f3f5;
  background-color: #fff;
  margin: 0 -1rem -1rem; /* Extend to full width */
  border-bottom-left-radius: 0.875rem;
  border-bottom-right-radius: 0.875rem;
}

/* Common Styles */
.pill-btn {
  display: inline-flex;
  align-items: center;
  gap: 0.375rem;
  padding: 0.5rem 1rem;
  border-radius: 999px;
  border: 1px solid #e5e6eb;
  background: #ffffff;
  font-size: 0.875rem;
  cursor: pointer;
  transition: background-color 0.2s;
}
.pill-btn:hover {
    background-color: #f2f3f5;
}
.pill-btn.primary {
  border-color: #165dff;
  background: #165dff;
  color: #ffffff;
}
.pill-btn.primary:hover {
    background-color: #4080ff;
}
.pill-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}
.pill-btn .btn-icon {
    width: 1rem;
    height: 1rem;
}
.pill-btn .btn-icon :deep(svg) {
    width: 100%;
    height: 100%;
}

.loading-spinner-small {
  width: 0.875rem;
  height: 0.875rem;
  border: 2px solid currentColor;
  border-top-color: transparent;
  border-radius: 50%;
  animation: spin 1s linear infinite;
}

@keyframes spin {
  to {
    transform: rotate(360deg);
  }
}

@keyframes blink {
  50% {
    opacity: 0;
  }
}
</style>
