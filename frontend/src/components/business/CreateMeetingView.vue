<!--
文件名：frontend/src/components/business/CreateMeetingView.vue
作者：Gemini
日期：2026-03-03
描述：会议记录创建视图，采用新版设计，支持暂停/继续。
-->
<script setup lang="ts">
import { ref, computed, watch, onUnmounted } from 'vue';
import { useWebSocketSpeech } from '@/composables/useWebSocketSpeech';
import { icons } from '@/assets/icons';
import { ElMessage } from 'element-plus';
import { renderMarkdown } from '@/utils/markdown';
import { streamChat } from '@/utils/stream';
import { createMeeting } from '@/api/meeting';

// --- 组件状态定义 ---
const emit = defineEmits(['saved', 'back']);
const isLoading = ref(false);

// --- 语音识别核心逻辑 ---
const {
  isRecording,
  isConnecting,
  isPaused,
  resultText,
  interimText,
  startMicrophone,
  pauseMicrophone,
  resumeMicrophone,
  stopMicrophone,
  uploadAudioFile
} = useWebSocketSpeech();

// --- 录音计时器逻辑 ---
const recordingTime = ref(0);
let timerInterval: any = null;

const formattedTime = computed(() => {
  const minutes = Math.floor(recordingTime.value / 60).toString().padStart(2, '0');
  const seconds = (recordingTime.value % 60).toString().padStart(2, '0');
  return `${minutes}:${seconds}`;
});

const startTimer = () => {
  stopTimer(); // Ensure no multiple timers
  timerInterval = setInterval(() => {
    if (isRecording.value && !isPaused.value) {
      recordingTime.value++;
    }
  }, 1000);
};

const stopTimer = () => {
  if (timerInterval) {
    clearInterval(timerInterval);
    timerInterval = null;
  }
};

// 监视录音状态以控制计时器
watch(isRecording, (newVal) => {
  if (newVal) {
    recordingTime.value = 0;
    startTimer();
  } else {
    stopTimer();
  }
});

// 组件卸载时确保计时器被清除
onUnmounted(() => {
  stopTimer();
  // 如果仍在录音，则停止
  if (isRecording.value) {
    stopMicrophone();
  }
});

// --- 视图状态和交互处理 ---
const currentView = ref('initial'); // 'initial', 'recording', 'finished'

const handleStartRecording = async () => {
  await startMicrophone();
  if (isRecording.value) {
    currentView.value = 'recording';
  }
};

const handleTogglePause = () => {
  if (isPaused.value) {
    resumeMicrophone();
  } else {
    pauseMicrophone();
  }
};

const handleStopRecording = () => {
  stopMicrophone((finalText) => {
    resultText.value = finalText;
    currentView.value = 'finished';
  });
};

// --- 文件上传和纪要生成 (逻辑保持不变) ---
const fileInputRef = ref<HTMLInputElement | null>(null);
const summaryText = ref('');
const isSummarizing = ref(false);
const canGenerateSummary = computed(() => !!resultText.value);

const triggerFileUpload = () => {
  fileInputRef.value?.click();
};

const handleFileSelect = (event: Event) => {
  const input = event.target as HTMLInputElement;
  if (input.files && input.files[0]) {
    // 先切换到创建视图
    currentView.value = 'recording';
    // 然后上传音频文件
    uploadAudioFile(input.files[0], (text) => {
      resultText.value = text;
      currentView.value = 'finished';
    });
    input.value = '';
  }
};

const handleGenerateSummary = async () => {
    // ... (纪要生成逻辑不变)
    if (!canGenerateSummary.value) return;
    const baseText = resultText.value;
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

// 设置视图状态的方法（供父组件调用）
const setViewState = (view: 'initial' | 'recording' | 'finished') => {
  currentView.value = view;
};

// 暴露给父组件的方法
defineExpose({
  startMicrophone: handleStartRecording, // 暴露新的启动函数
  triggerFileUpload,
  uploadAudioFile,
  setViewState
});
</script>

<template>
  <div class="create-view-new">
    <!-- 1. 初始待机界面 -->
    <div v-if="currentView === 'initial'" class="initial-view">
      <button class="start-mic-btn" @click="handleStartRecording" :disabled="isConnecting">
        <span v-if="isConnecting" class="loading-spinner"></span>
        <span v-else v-html="icons.micBig"></span>
      </button>
      <p class="hint">点击开始录音</p>
      <a href="#" @click.prevent="triggerFileUpload">或者上传音频文件</a>
    </div>

    <!-- 2. 录音/完成 界面 -->
    <div v-if="currentView === 'recording' || currentView === 'finished'" class="recording-view">
      <div class="transcription-panel">
        <p>{{ resultText }}</p>
      </div>
      
      <!-- 底部控制栏 -->
      <div class="footer-controls">
        <div class="timer">
          <span class="status-dot" :class="{ 'paused': isPaused }"></span>
          {{ formattedTime }}
        </div>
        <div class="main-actions">
          <button class="control-btn pause-btn" @click="handleTogglePause">
            <span v-if="isPaused" v-html="icons.play"></span>
            <span v-else v-html="icons.pause"></span>
          </button>
          <button class="control-btn stop-btn" @click="handleStopRecording">
            <span v-html="icons.power"></span>
          </button>
        </div>
      </div>
    </div>
    
    <!-- 3. 完成后的操作 (暂时放在这里，后续可以集成到 finished 视图中) -->
    <div v-if="currentView === 'finished'" class="finished-actions">
        <button class="pill-btn" @click="emit('back')">返回</button>
        <button class="pill-btn primary" @click="saveAndFinish" :disabled="!resultText">保存</button>
    </div>

    <input type="file" ref="fileInputRef" @change="handleFileSelect" accept="audio/*" style="display: none" />
  </div>
</template>


<style scoped>
.create-view-new {
  display: flex;
  flex-direction: column;
  height: 100%;
  width: 100%;
  background-color: #fff;
  overflow: hidden;
}

/* 初始视图 */
.initial-view {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  height: 100%;
  gap: 1.5rem;
}
.start-mic-btn {
  width: 6rem;
  height: 6rem;
  border-radius: 50%;
  background-color: #165dff;
  color: white;
  border: none;
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  transition: background-color 0.2s;
}
.start-mic-btn:hover { background-color: #4080ff; }
.start-mic-btn:disabled { background-color: #a0bfff; cursor: not-allowed; }
.start-mic-btn :deep(svg) {
  width: 3rem;
  height: 3rem;
}
.hint { font-size: 1rem; color: #1d2129; margin: 0; }
.initial-view a { font-size: 0.875rem; color: #86909c; text-decoration: none; }
.initial-view a:hover { text-decoration: underline; }

/* 录音视图 */
.recording-view {
  flex: 1;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}
.transcription-panel {
  flex: 1;
  overflow-y: auto;
  padding: 1.5rem;
  font-size: 1rem;
  line-height: 1.8;
  color: #1d2129;
}
.transcription-panel p {
  white-space: pre-wrap; /* 支持换行 */
}

.transcription-panel .interim {
  color: #86909c;
}

/* 底部控制栏 */
.footer-controls {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 1rem 1.5rem;
  border-top: 1px solid #f2f3f5;
  background: rgba(255, 255, 255, 0.8);
  backdrop-filter: blur(10px);
  -webkit-backdrop-filter: blur(10px);
}
.timer {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  font-size: 1.125rem;
  font-weight: 500;
  color: #1d2129;
}
.status-dot {
  width: 0.625rem;
  height: 0.625rem;
  border-radius: 50%;
  background-color: #00b42a; /* 录制中 */
  animation: pulse 2s infinite;
}
.status-dot.paused {
  background-color: #ff7d00; /* 暂停中 */
  animation: none;
}

.main-actions {
  display: flex;
  gap: 1.5rem;
}

.control-btn {
  width: 3.5rem;
  height: 3.5rem;
  border-radius: 50%;
  border: none;
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  transition: background-color 0.2s;
}
.control-btn :deep(svg) {
  width: 1.75rem;
  height: 1.75rem;
}

.pause-btn {
  background-color: #f2f3f5;
  color: #1d2129;
}
.pause-btn:hover { background-color: #e5e6eb; }

.stop-btn {
  background-color: #f53f3f;
  color: white;
}
.stop-btn:hover { background-color: #ff7d7d; }

/* 完成后的操作 */
.finished-actions {
    padding: 1rem;
    display: flex;
    justify-content: space-around;
    border-top: 1px solid #f2f3f5;
}

/* 通用样式 */
.pill-btn { display: inline-flex; align-items: center; gap: 0.375rem; padding: 0.5rem 1.25rem; border-radius: 999px; border: 1px solid #e5e6eb; background: #ffffff; font-size: 0.875rem; cursor: pointer; }
.pill-btn.primary { border-color: #165dff; background: #165dff; color: #ffffff; }
.pill-btn:disabled { opacity: 0.5; cursor: not-allowed; }
.loading-spinner { width: 2rem; height: 2rem; border: 3px solid rgba(255,255,255,0.3); border-top-color: #fff; border-radius: 50%; animation: spin 1s linear infinite; }

@keyframes pulse {
  0% { box-shadow: 0 0 0 0 rgba(0, 180, 42, 0.7); }
  70% { box-shadow: 0 0 0 10px rgba(0, 180, 42, 0); }
  100% { box-shadow: 0 0 0 0 rgba(0, 180, 42, 0); }
}

@keyframes spin {
  to { transform: rotate(360deg); }
}
</style>
