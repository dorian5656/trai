<!--
文件名：frontend/src/components/business/MeetingRecorder.vue
作者：whf
日期：2026-02-03
描述：会议记录组件 (实时/文件流式识别)
-->
<script setup lang="ts">
import { ref, watch } from 'vue';
import { useWebSocketSpeech } from '@/composables/useWebSocketSpeech';
import { icons } from '@/assets/icons';
import { ElMessage } from 'element-plus';

const emit = defineEmits(['close']);

const {
  isRecording,
  isProcessingFile,
  resultText,
  interimText,
  startMicrophone,
  stopMicrophone,
  uploadAudioFile
} = useWebSocketSpeech();

const fileInputRef = ref<HTMLInputElement | null>(null);

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
        <div class="result-area">
          <div v-if="!resultText && !interimText" class="placeholder">
            <p>点击下方麦克风开始实时记录，或上传音频文件进行识别。</p>
            <p class="sub-text">支持 WAV, MP3, M4A 格式</p>
          </div>
          <div v-else class="text-content">
            <span class="final">{{ resultText }}</span>
            <span class="interim">{{ interimText }}</span>
            <span class="cursor" v-if="isRecording || isProcessingFile">|</span>
          </div>
        </div>
      </div>

      <div class="card-footer">
        <div class="actions">
          <!-- 麦克风按钮 -->
          <button 
            class="action-btn mic-btn" 
            :class="{ 'recording': isRecording, 'disabled': isProcessingFile }"
            @click="isRecording ? stopMicrophone() : startMicrophone()"
            :disabled="isProcessingFile"
          >
            <div class="mic-icon-wrapper">
                <span v-if="isRecording" class="mic-icon" v-html="icons.micListening"></span>
                <span v-else class="mic-icon" v-html="icons.micNormal"></span>
            </div>
            <span class="label">{{ isRecording ? '停止录音' : '实时录音' }}</span>
          </button>

          <!-- 文件上传按钮 -->
          <button 
            class="action-btn upload-btn" 
            :class="{ 'processing': isProcessingFile, 'disabled': isRecording }"
            @click="triggerFileUpload()"
            :disabled="isRecording || isProcessingFile"
          >
             <div class="upload-icon-wrapper">
                 <span v-if="isProcessingFile" class="loading-spinner"></span>
                 <span v-else class="upload-icon" v-html="icons.attachment"></span>
             </div>
            <span class="label">{{ isProcessingFile ? '转写中...' : '上传音频' }}</span>
          </button>
          
          <input 
            type="file" 
            ref="fileInputRef" 
            style="display: none" 
            accept="audio/*,.wav,.mp3,.m4a"
            @change="handleFileSelect"
          />
        </div>
        
        <div class="extra-actions" v-if="resultText">
             <button class="text-btn" @click="handleCopy">复制结果</button>
        </div>
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
  backdrop-filter: blur(4px);
}

.recorder-card {
  width: 800px;
  max-width: 90vw;
  height: 600px;
  max-height: 90vh;
  background: white;
  border-radius: 16px;
  display: flex;
  flex-direction: column;
  box-shadow: 0 10px 30px rgba(0, 0, 0, 0.2);
  overflow: hidden;

  .card-header {
    padding: 16px 24px;
    border-bottom: 1px solid #f2f3f5;
    display: flex;
    justify-content: space-between;
    align-items: center;

    .title {
      font-size: 18px;
      font-weight: 600;
      color: #1d2129;
      display: flex;
      align-items: center;
      gap: 8px;
      
      .icon {
        width: 20px;
        height: 20px;
        color: #F53F3F;
      }
    }

    .close-btn {
      background: none;
      border: none;
      cursor: pointer;
      padding: 4px;
      border-radius: 4px;
      color: #86909c;
      transition: all 0.2s;

      &:hover {
        background: #f2f3f5;
        color: #4e5969;
      }
      
      :deep(svg) {
          width: 20px;
          height: 20px;
      }
    }
  }

  .card-body {
    flex: 1;
    padding: 24px;
    overflow-y: auto;
    background: #f7f8fa;

    .result-area {
      background: white;
      border-radius: 8px;
      padding: 24px;
      min-height: 100%;
      box-shadow: 0 2px 8px rgba(0,0,0,0.02);
      
      .placeholder {
        height: 100%;
        display: flex;
        flex-direction: column;
        align-items: center;
        justify-content: center;
        color: #86909c;
        text-align: center;
        padding-top: 100px;
        
        .sub-text {
            font-size: 12px;
            margin-top: 8px;
            color: #c9cdd4;
        }
      }

      .text-content {
        font-size: 16px;
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
            width: 2px;
            height: 1em;
            background-color: #165DFF;
            animation: blink 1s step-end infinite;
            vertical-align: text-bottom;
            margin-left: 2px;
        }
      }
    }
  }

  .card-footer {
    padding: 20px 24px;
    border-top: 1px solid #f2f3f5;
    background: white;
    display: flex;
    justify-content: space-between;
    align-items: center;

    .actions {
      display: flex;
      gap: 16px;
    }
    
    .action-btn {
        display: flex;
        align-items: center;
        gap: 8px;
        padding: 10px 20px;
        border-radius: 30px;
        border: 1px solid #e5e6eb;
        background: white;
        cursor: pointer;
        transition: all 0.2s;
        font-size: 14px;
        font-weight: 500;
        
        &:hover:not(.disabled) {
            border-color: #165DFF;
            color: #165DFF;
            background: #f0f6ff;
        }
        
        &.disabled {
            opacity: 0.5;
            cursor: not-allowed;
        }
        
        &.recording {
            background: #F53F3F;
            border-color: #F53F3F;
            color: white;
            animation: pulse 2s infinite;
            
            &:hover {
                background: #F76560;
            }
        }
        
        &.processing {
            border-color: #165DFF;
            color: #165DFF;
        }
        
        .mic-icon, .upload-icon {
            width: 18px;
            height: 18px;
            display: block;
        }
    }
    
    .text-btn {
        background: none;
        border: none;
        color: #4e5969;
        cursor: pointer;
        font-size: 14px;
        padding: 8px 16px;
        border-radius: 4px;
        
        &:hover {
            background: #f2f3f5;
            color: #1d2129;
        }
    }
  }
}

.loading-spinner {
    width: 18px;
    height: 18px;
    border: 2px solid #165DFF;
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

@media (max-width: 768px) {
  .recorder-card {
    width: 95vw;
    height: 80vh;
    border-radius: 12px;
    .card-header {
      padding: 12px 16px;
      .title {
        font-size: 16px;
        .icon { width: 18px; height: 18px; }
      }
      :deep(svg) { width: 18px; height: 18px; }
    }
    .card-body {
      padding: 16px;
      .result-area {
        padding: 16px;
        .placeholder { padding-top: 40px; }
        .text-content { font-size: 14px; }
      }
    }
    .card-footer {
      padding: 12px 16px;
      .actions { gap: 10px; }
      .action-btn {
        padding: 8px 12px;
        border-radius: 20px;
        font-size: 13px;
        .mic-icon, .upload-icon { width: 16px; height: 16px; }
      }
      .text-btn { font-size: 13px; padding: 6px 10px; }
    }
  }
}


@keyframes pulse {
    0% { box-shadow: 0 0 0 0 rgba(245, 63, 63, 0.4); }
    70% { box-shadow: 0 0 0 10px rgba(245, 63, 63, 0); }
    100% { box-shadow: 0 0 0 0 rgba(245, 63, 63, 0); }
}
</style>
