<!--
文件名：frontend/src/components/business/MeetingRecorder.vue
作者：whf
日期：2026-02-03
描述：会议记录组件 (实时/文件流式识别)
-->
<script setup lang="ts">
import { ref, computed } from 'vue';
import { useWebSocketSpeech } from '@/composables/useWebSocketSpeech';
import { icons } from '@/assets/icons';
import { ElMessage } from 'element-plus';
import { renderMarkdown } from '@/utils/markdown';
import { streamChat } from '@/utils/stream';

const emit = defineEmits(['close']);

const {
  isRecording,
  isConnecting,
  isProcessingFile,
  resultText,
  interimText,
  startMicrophone,
  stopMicrophone,
  uploadAudioFile
} = useWebSocketSpeech();

const fileInputRef = ref<HTMLInputElement | null>(null);

const summaryText = ref('');
const isSummarizing = ref(false);

const canGenerateSummary = computed(() => {
  return !!resultText.value || !!interimText.value;
});

const handleFileSelect = (event: Event) => {
  const input = event.target as HTMLInputElement;
  if (input.files && input.files.length > 0) {
    const file = input.files[0];
    if (file) {
      // 简单检查格式
      if (!file.type.includes('audio') && !file.name.endsWith('.wav') && !file.name.endsWith('.mp3') && !file.name.endsWith('.m4a')) {
        ElMessage.error('请上传音频文件 (WAV/MP3/M4A)');
        return;
      }
      uploadAudioFile(file);
      // 清空 input 允许重复选择同一文件
      input.value = '';
    }
  }
};

const triggerFileUpload = () => {
  fileInputRef.value?.click();
};

const handleCopy = () => {
  if (!resultText.value) return;
  navigator.clipboard.writeText(resultText.value).then(() => {
    ElMessage.success('已复制到剪贴板');
  });
};

const handleGenerateSummary = async () => {
  if (!canGenerateSummary.value) {
    ElMessage.warning('暂无可总结的内容');
    return;
  }
  const baseText = `${resultText.value}${interimText.value ? '\n' + interimText.value : ''}`;
  const prompt = [
    '你是一个专业的会议纪要助手。',
    '请根据下面的逐字稿内容，用中文生成结构化会议纪要，包括：',
    '1. 会议概述',
    '2. 重要决策列表',
    '3. 待办事项列表（尽量包含责任人和完成时间）',
    '4. 风险与问题列表',
    '请使用 Markdown 格式输出，条理清晰，便于直接发送给同事查看。',
    '',
    '以下是会议逐字稿：',
    baseText
  ].join('\n');

  isSummarizing.value = true;
  summaryText.value = '';

  await streamChat(
    prompt,
    (text: string) => {
      summaryText.value = text;
    },
    () => {
      isSummarizing.value = false;
    },
    (err: Error) => {
      isSummarizing.value = false;
      ElMessage.error(`生成纪要失败：${err.message || '未知错误'}`);
    }
  );
};

const handleCopySummary = () => {
  if (!summaryText.value) return;
  navigator.clipboard.writeText(summaryText.value).then(() => {
    ElMessage.success('纪要已复制到剪贴板');
  });
};
</script>

<template>
  <div class="meeting-recorder-overlay" @click.self="emit('close')">
    <div class="recorder-card">
      <div class="card-header">
        <div class="title">
          <span class="icon" v-html="icons.micNormal"></span>
          会议记录
        </div>
        <button class="close-btn" @click="emit('close')">
          <span v-html="icons.closeSmall"></span>
        </button>
      </div>

      <div class="card-body">
        <div class="main-layout">
          <section class="panel transcript-panel">
            <header class="panel-header">
              <div class="panel-title">
                <span class="status-dot" :class="{ active: isRecording }"></span>
                <span class="title-text">实时转写</span>
                <span class="status-text" v-if="isRecording">录音中...</span>
                <span class="status-text" v-else-if="isProcessingFile">转写中...</span>
              </div>
              <div class="panel-actions">
                <button
                  class="pill-btn"
                  :class="{ primary: isRecording, disabled: isProcessingFile || isConnecting }"
                  @click="isRecording ? stopMicrophone() : startMicrophone()"
                  :disabled="isProcessingFile || isConnecting"
                >
                  <span class="btn-icon" v-html="isRecording ? icons.micListening : icons.micNormal"></span>
                  <span>{{ isRecording ? '停止录音' : '实时录音' }}</span>
                </button>
                <button
                  class="pill-btn"
                  :class="{ disabled: isRecording }"
                  @click="triggerFileUpload()"
                  :disabled="isRecording || isProcessingFile"
                >
                  <span class="btn-icon" v-if="isProcessingFile">
                    <span class="loading-spinner"></span>
                  </span>
                  <span class="btn-icon" v-else v-html="icons.attachment"></span>
                  <span>{{ isProcessingFile ? '转写中...' : '上传音频' }}</span>
                </button>
              </div>
            </header>
            <div class="panel-body transcript-body">
              <div v-if="!resultText && !interimText" class="placeholder">
                <p>点击上方按钮开始录音或上传音频，系统会自动进行文字转写。</p>
                <p class="sub-text">支持 WAV、MP3、M4A 等常见格式</p>
              </div>
              <div v-else class="text-content">
                <span class="final">{{ resultText }}</span>
                <span class="interim">{{ interimText }}</span>
                <span class="cursor" v-if="isRecording || isProcessingFile">|</span>
              </div>
            </div>
            <footer class="panel-footer" v-if="resultText">
              <button class="link-btn" @click="handleCopy">复制逐字稿</button>
            </footer>
          </section>

          <section class="panel summary-panel">
            <header class="panel-header">
              <div class="panel-title">
                <span class="title-text">智能会议纪要</span>
              </div>
              <div class="panel-actions">
                <button
                  class="pill-btn primary"
                  :class="{ disabled: !canGenerateSummary || isSummarizing }"
                  :disabled="!canGenerateSummary || isSummarizing"
                  @click="handleGenerateSummary"
                >
                  <span>{{ isSummarizing ? '生成中...' : '生成纪要' }}</span>
                </button>
                <button
                  v-if="summaryText"
                  class="link-btn"
                  @click="handleCopySummary"
                >
                  复制纪要
                </button>
              </div>
            </header>
            <div class="panel-body summary-body">
              <div v-if="!summaryText && !isSummarizing" class="summary-placeholder">
                <p>生成后的结构化会议纪要会展示在这里，便于复制到聊天工具或邮件中。</p>
              </div>
              <div
                v-else
                class="summary-content markdown-body"
                v-html="renderMarkdown(summaryText || '正在生成纪要...')"
              />
            </div>
          </section>
        </div>

        <input
          type="file"
          ref="fileInputRef"
          style="display: none"
          accept="audio/*,.wav,.mp3,.m4a"
          @change="handleFileSelect"
        />
      </div>
    </div>
  </div>
</template>

<style scoped lang="scss">
.meeting-recorder-overlay {
  position: fixed;
  top: 0;
  left: 0;
  width: 100vw;
  height: 100vh;
  background: rgba(0, 0, 0, 0.5);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 2000;
  backdrop-filter: blur(0.25rem);
}

.recorder-card {
  width: 56rem;
  max-width: 94vw;
  height: 36rem;
  max-height: 88vh;
  background: white;
  border-radius: 1rem;
  display: flex;
  flex-direction: column;
  box-shadow: 0 0.625rem 1.875rem rgba(0, 0, 0, 0.2);
  overflow: hidden;

  .card-header {
    padding: 1rem 1.5rem;
    border-bottom: 1px solid #f2f3f5;
    display: flex;
    justify-content: space-between;
    align-items: center;

    .title {
      font-size: 1.125rem;
      font-weight: 600;
      color: #1d2129;
      display: flex;
      align-items: center;
      gap: 0.5rem;
      
      .icon {
        width: 1.25rem;
        height: 1.25rem;
        color: #F53F3F;
      }
    }

    .close-btn {
      background: none;
      border: none;
      cursor: pointer;
      padding: 0.25rem;
      border-radius: 0.25rem;
      color: #86909c;
      transition: all 0.2s;

      &:hover {
        background: #f2f3f5;
        color: #4e5969;
      }
      
      :deep(svg) {
          width: 1.25rem;
          height: 1.25rem;
      }
    }
  }

.card-body {
  flex: 1;
  padding: 1.5rem;
  background: #f7f8fa;

  .main-layout {
    display: grid;
    grid-template-columns: 3fr 2fr;
    gap: 1.25rem;
    height: 100%;

    @media (max-width: 64rem) {
      grid-template-columns: 1fr;
    }
  }

  .panel {
    background: #ffffff;
    border-radius: 0.75rem;
    box-shadow: 0 0.125rem 0.5rem rgba(0, 0, 0, 0.03);
    display: flex;
    flex-direction: column;
    min-height: 0;
  }

  .panel-header {
    padding: 0.75rem 1rem;
    border-bottom: 1px solid #f2f3f5;
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 0.75rem;
  }

  .panel-title {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    min-width: 0;

    .title-text {
      font-size: 0.9375rem;
      font-weight: 600;
      color: #1d2129;
      white-space: nowrap;
    }

    .status-text {
      font-size: 0.8125rem;
      color: #4e5969;
      white-space: nowrap;
    }
  }

  .status-dot {
    width: 0.5rem;
    height: 0.5rem;
    border-radius: 50%;
    background: #c9cdd4;

    &.active {
      background: #f53f3f;
      box-shadow: 0 0 0 0.1875rem rgba(245, 63, 63, 0.2);
    }
  }

  .panel-actions {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    flex-shrink: 0;
  }

  .pill-btn {
    display: inline-flex;
    align-items: center;
    gap: 0.375rem;
    padding: 0.375rem 0.875rem;
    border-radius: 999px;
    border: 1px solid #e5e6eb;
    background: #ffffff;
    font-size: 0.8125rem;
    color: #1d2129;
    cursor: pointer;
    transition: all 0.2s;

    &:hover:not(.disabled) {
      border-color: #165dff;
      color: #165dff;
      background: #f0f6ff;
    }

    &.primary {
      border-color: #165dff;
      background: #165dff;
      color: #ffffff;
    }

    &.disabled {
      opacity: 0.5;
      cursor: not-allowed;
    }

    .btn-icon {
      display: flex;
      align-items: center;
      justify-content: center;
      width: 1rem;
      height: 1rem;
    }
  }

  .link-btn {
    background: none;
    border: none;
    color: #4e5969;
    cursor: pointer;
    font-size: 0.8125rem;
    padding: 0.25rem 0.5rem;
    border-radius: 0.25rem;

    &:hover {
      background: #f2f3f5;
      color: #1d2129;
    }
  }

  .panel-body {
    flex: 1;
    padding: 0.75rem 1rem 0.75rem;
    min-height: 0;
    overflow-y: auto;
  }

  .transcript-body {
    .placeholder {
      height: 100%;
      display: flex;
      flex-direction: column;
      align-items: center;
      justify-content: center;
      color: #86909c;
      text-align: center;
      padding: 0 1.5rem;

      .sub-text {
        font-size: 0.75rem;
        margin-top: 0.5rem;
        color: #c9cdd4;
      }
    }

    .text-content {
      font-size: 0.9375rem;
      line-height: 1.8;
      color: #1d2129;
      white-space: pre-wrap;

      .final {
        color: #1d2129;
      }

      .interim {
        color: #86909c;
      }

      .cursor {
        display: inline-block;
        width: 0.125rem;
        height: 1em;
        background-color: #165dff;
        animation: blink 1s step-end infinite;
        vertical-align: text-bottom;
        margin-left: 0.125rem;
      }
    }
  }

  .summary-body {
    .summary-placeholder {
      height: 100%;
      display: flex;
      align-items: center;
      justify-content: center;
      color: #86909c;
      font-size: 0.875rem;
      text-align: center;
      padding: 0 1rem;
    }

    .summary-content {
      font-size: 0.875rem;
      line-height: 1.7;
    }
  }

  .panel-footer {
    padding: 0.5rem 1rem 0.75rem;
    border-top: 1px solid #f2f3f5;
    display: flex;
    justify-content: flex-end;
  }
}
}

.loading-spinner {
    width: 1.125rem;
    height: 1.125rem;
    border: 0.125rem solid #165DFF;
    border-top-color: transparent;
    border-radius: 50%;
    animation: spin 1s linear infinite;
    display: block;
}

@keyframes spin {
    to { transform: rotate(360deg); }
}

@keyframes blink {
    0%, 100% { opacity: 1; }
    50% { opacity: 0; }
}

@media (max-width: 48rem) {
  .recorder-card {
    width: 95vw;
    height: 80vh;
    border-radius: 0.75rem;
    .card-header {
      padding: 0.75rem 1rem;
      .title {
        font-size: 1rem;
        .icon {
          width: 1.125rem;
          height: 1.125rem;
        }
      }
      :deep(svg) {
        width: 1.125rem;
        height: 1.125rem;
      }
    }
    .card-body {
      padding: 1rem;
    }
  }
}


@keyframes pulse {
    0% { box-shadow: 0 0 0 0 rgba(245, 63, 63, 0.4); }
    70% { box-shadow: 0 0 0 0.625rem rgba(245, 63, 63, 0); }
    100% { box-shadow: 0 0 0 0 rgba(245, 63, 63, 0); }
}
</style>
