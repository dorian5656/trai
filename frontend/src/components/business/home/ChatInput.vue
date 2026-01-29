<!--
文件名：frontend/src/components/business/home/ChatInput.vue
作者：zcl
日期：2026-01-28
描述：聊天输入框组件
-->
<script setup lang="ts">
import { ref } from 'vue';
import type { UploadFile } from '@/composables/useFileUpload';
import type { Skill } from '@/composables/useSkills';
import { icons } from '@/assets/icons';

const props = defineProps<{
  modelValue: string;
  isSending: boolean;
  isDeepThinking: boolean;
  activeSkill: Skill | null;
  uploadedFiles: UploadFile[];
  isListening: boolean;
}>();

const emit = defineEmits<{
  (e: 'update:modelValue', value: string): void;
  (e: 'send'): void;
  (e: 'stop'): void;
  (e: 'toggleDeepThink'): void;
  (e: 'toggleListening'): void;
  (e: 'removeSkill'): void;
  (e: 'fileSelect', event: Event): void;
  (e: 'removeFile', id: string): void;
  (e: 'previewFile', file: UploadFile): void;
}>();

const fileInputRef = ref<HTMLInputElement | null>(null);

const triggerFileInput = () => {
  fileInputRef.value?.click();
};

const handleEnter = (e: KeyboardEvent) => {
  if (!e.shiftKey) {
    e.preventDefault();
    emit('send');
  }
};
</script>

<template>
  <div class="input-box">
    <input 
      type="file" 
      ref="fileInputRef" 
      style="display: none" 
      @change="(e) => emit('fileSelect', e)"
    />
    <!-- 文件上传列表 -->
    <div v-if="uploadedFiles.length > 0" class="file-list">
      <div v-for="file in uploadedFiles" :key="file.id" class="file-card">
        <div class="file-preview">
          <!-- 图片预览 -->
          <img v-if="file.url" :src="file.url" alt="preview" @click="emit('previewFile', file)" style="cursor: pointer" />
          <!-- 其他文件图标 -->
          <div v-else class="file-icon">
            <!-- Excel 图标 -->
            <div v-if="file.name.endsWith('.xlsx') || file.name.endsWith('.xls')" style="width: 24px; height: 24px" v-html="icons.excel"></div>
            <!-- 默认文件图标 -->
            <div v-else style="width: 24px; height: 24px" v-html="icons.fileDefault"></div>
          </div>
          
          <!-- 上传/解析 遮罩 -->
          <div v-if="file.status !== 'done'" class="upload-mask">
            <div v-if="file.status === 'uploading'" class="progress-ring">
              <svg width="24" height="24" viewBox="0 0 24 24">
                <circle cx="12" cy="12" r="10" fill="none" stroke="rgba(255,255,255,0.3)" stroke-width="2"/>
                <circle cx="12" cy="12" r="10" fill="none" stroke="white" stroke-width="2" 
                        stroke-dasharray="62.83" :stroke-dashoffset="62.83 * (1 - file.progress / 100)"
                        transform="rotate(-90 12 12)"/>
              </svg>
              <span class="progress-text">{{ file.progress }}%</span>
            </div>
            <div v-else-if="file.status === 'parsing'" class="parsing-text">
              解析中...
            </div>
          </div>
        </div>
        
        <div class="file-info">
          <div class="file-name" :title="file.name">{{ file.name }}</div>
          <div class="file-meta">{{ file.status === 'parsing' ? '解析中...' : file.size }}</div>
        </div>

        <button class="remove-file-btn" @click="emit('removeFile', file.id)">
          <span style="width: 12px; height: 12px; display: block" v-html="icons.closeSmall"></span>
        </button>
      </div>
    </div>

    <transition name="fade-slide">
      <div v-if="activeSkill" class="skill-tag-wrapper">
        <div class="skill-tag">
          <span class="skill-tag-icon" v-html="activeSkill.icon"></span>
          <span class="skill-tag-text">{{ activeSkill.label }}</span>
          <span class="skill-tag-close" @click.stop="emit('removeSkill')">
            <span style="width: 12px; height: 12px; display: block" v-html="icons.closeTiny"></span>
          </span>
          <div class="skill-tooltip">点击退出技能 ESC</div>
        </div>
      </div>
    </transition>
    <input 
      type="text" 
      :value="modelValue"
      @input="emit('update:modelValue', ($event.target as HTMLInputElement).value)"
      @keyup.enter="handleEnter"
      @keyup.esc="emit('removeSkill')"
      :disabled="isSending"
      :placeholder="activeSkill ? '请输入内容...' : '发消息 or 输入“/”选择技能'" 
    />
    <div class="input-actions">
      <!-- 上传按钮 -->
      <button class="icon-btn" @click="triggerFileInput">
        <span style="width: 20px; height: 20px; display: block" v-html="icons.attachment"></span>
      </button>
      <!-- 深度思考按钮 -->
      <button 
        class="icon-btn deep-think-btn" 
        :class="{ active: isDeepThinking }" 
        @click="emit('toggleDeepThink')"
        title="深度思考"
      >
        <span style="width: 20px; height: 20px; display: block" v-html="icons.deepThink"></span>
      </button>
      <div class="spacer"></div>
      <button class="icon-btn" :class="{ 'is-listening': isListening }" @click="emit('toggleListening')" title="语音输入">
        <span v-if="isListening" style="width: 20px; height: 20px; display: block" v-html="icons.micListening"></span>
        <span v-else style="width: 20px; height: 20px; display: block" v-html="icons.micNormal"></span>
      </button>
      <button class="send-btn" @click="isSending ? emit('stop') : emit('send')" :disabled="isSending">
        <span v-if="isSending" style="width: 14px; height: 14px; display: block" v-html="icons.sendSending"></span>
        <span v-else style="width: 16px; height: 16px; display: block" v-html="icons.sendNormal"></span>
      </button>
    </div>
  </div>
</template>

<style scoped lang="scss">
.input-box {
  width: 100%;
  background: white;
  border: 1px solid #e5e6eb;
  border-radius: 0.75rem;
  padding: 0.75rem;
  box-shadow: 0 0.25rem 0.625rem rgba(0,0,0,0.05);
  display: flex;
  flex-direction: column;

  .file-list {
    display: flex;
    flex-wrap: wrap;
    gap: 0.75rem;
    padding: 0 0.25rem 0.75rem 0.25rem;

    .file-card {
      position: relative;
      width: 15rem;
      height: 4rem;
      background: #f7f8fa;
      border-radius: 0.75rem;
      display: flex;
      align-items: center;
      padding: 0.5rem;
      border: 1px solid transparent;
      transition: all 0.2s;

      &:hover {
        background: #fff;
        border-color: #e5e6eb;
        box-shadow: 0 0.25rem 0.75rem rgba(0,0,0,0.05);

        .remove-file-btn {
          opacity: 1;
        }
      }

      .file-preview {
        width: 3rem;
        height: 3rem;
        border-radius: 0.5rem;
        overflow: hidden;
        margin-right: 0.75rem;
        position: relative;
        flex-shrink: 0;
        background: white;
        display: flex;
        align-items: center;
        justify-content: center;
        border: 1px solid #f2f3f5;

        img {
          width: 100%;
          height: 100%;
          object-fit: cover;
        }

        .file-icon {
          width: 100%;
          height: 100%;
          display: flex;
          align-items: center;
          justify-content: center;
        }

        .upload-mask {
          position: absolute;
          top: 0;
          left: 0;
          width: 100%;
          height: 100%;
          background: rgba(0,0,0,0.4);
          display: flex;
          align-items: center;
          justify-content: center;
          flex-direction: column;

          .progress-ring {
            position: relative;
            width: 1.5rem;
            height: 1.5rem;
            display: flex;
            align-items: center;
            justify-content: center;

            svg {
              transform: rotate(-90deg);
            }

            .progress-text {
              position: absolute;
              font-size: 0.5rem;
              color: white;
              font-weight: 600;
            }
          }

          .parsing-text {
            color: white;
            font-size: 0.625rem;
            font-weight: 500;
          }
        }
      }

      .file-info {
        flex: 1;
        min-width: 0;
        
        .file-name {
          font-size: 0.875rem;
          color: #1d2129;
          font-weight: 500;
          white-space: nowrap;
          overflow: hidden;
          text-overflow: ellipsis;
          margin-bottom: 0.25rem;
        }

        .file-meta {
          font-size: 0.75rem;
          color: #86909c;
        }
      }

      .remove-file-btn {
        position: absolute;
        top: -0.375rem;
        right: -0.375rem;
        width: 1.125rem;
        height: 1.125rem;
        background: #1d2129;
        border-radius: 50%;
        color: white;
        border: none;
        display: flex;
        align-items: center;
        justify-content: center;
        cursor: pointer;
        opacity: 0;
        transition: opacity 0.2s;
        z-index: 10;

        &:hover {
          background: #4e5969;
        }
      }
    }
  }

  .skill-tag-wrapper {
    display: flex;
    align-items: center;
    margin-bottom: 0.5rem;
    padding-left: 0.125rem;
    
    .skill-tag {
      display: inline-flex;
      align-items: center;
      background-color: #e8f3ff;
      color: #165dff;
      padding: 0.25rem 0.625rem;
      border-radius: 0.375rem;
      font-size: 0.8125rem;
      font-weight: 500;
      position: relative;
      cursor: default;
      transition: all 0.2s ease;
      
      &:hover {
        background-color: #dbeaff;
      }
      
      .skill-tag-icon {
        margin-right: 0.375rem;
        font-size: 0.875rem;
        display: flex;
        align-items: center;
      }

      .skill-tag-text {
        margin-right: 0.5rem;
      }
      
      .skill-tag-close {
        cursor: pointer;
        display: flex;
        align-items: center;
        justify-content: center;
        width: 1rem;
        height: 1rem;
        border-radius: 50%;
        opacity: 0.6;
        transition: all 0.2s;
        
        &:hover { 
          opacity: 1; 
          background-color: rgba(22, 93, 255, 0.1);
        }
      }

      .skill-tooltip {
        position: absolute;
        bottom: calc(100% + 0.5rem);
        left: 50%;
        transform: translateX(-50%);
        background: rgba(0, 0, 0, 0.85);
        color: #fff;
        padding: 0.375rem 0.625rem;
        border-radius: 0.25rem;
        font-size: 0.75rem;
        white-space: nowrap;
        opacity: 0;
        visibility: hidden;
        transition: all 0.2s;
        pointer-events: none;
        z-index: 100;
        box-shadow: 0 0.25rem 0.75rem rgba(0, 0, 0, 0.15);
        
        &::after {
          content: '';
          position: absolute;
          top: 100%;
          left: 50%;
          transform: translateX(-50%);
          border: 0.25rem solid transparent;
          border-top-color: rgba(0, 0, 0, 0.85);
        }
      }
      
      &:hover .skill-tooltip {
        opacity: 1;
        visibility: visible;
        bottom: calc(100% + 0.625rem);
      }
    }
  }

  /* 动画 */
  .fade-slide-enter-active,
  .fade-slide-leave-active {
    transition: all 0.3s ease;
  }

  .fade-slide-enter-from,
  .fade-slide-leave-to {
    opacity: 0;
    transform: translateY(-0.3125rem);
  }
  
  input {
    width: 100%;
    border: none;
    outline: none;
    font-size: 1rem;
    padding: 0.5rem 0;
    margin-bottom: 0.625rem;
  }

  .input-actions {
    display: flex;
    align-items: center;
    gap: 0.25rem; /* 统一图标按钮间距 */
    
    .icon-btn {
      background: none;
      border: none;
      cursor: pointer;
      font-size: 1.125rem;
      padding: 0.375rem;
      border-radius: 0.25rem;
      color: #86909c;
      display: flex;
      align-items: center;
      justify-content: center;
      
      &:hover { background: #f2f3f5; color: #1d2129; }
      
      &.is-listening {
        color: #f56c6c;
        animation: pulse 1.5s infinite;
      }
    }

    /* 深度思考按钮样式（纯图标版） */
    .deep-think-btn {
      &.active {
        color: #165dff;
        background: #e8f3ff;
      }
    }

    @keyframes pulse {
      0% { transform: scale(1); }
      50% { transform: scale(1.2); }
      100% { transform: scale(1); }
    }

    .spacer { flex: 1; }

    .send-btn {
      background: #165dff;
      color: white;
      border: none;
      width: 2rem;
      height: 2rem;
      border-radius: 50%;
      display: flex;
      align-items: center;
      justify-content: center;
      cursor: pointer;
      margin-left: 0.5rem;
      &:hover { background: #0e42d2; }
      &:disabled { background: #94bfff; cursor: not-allowed; }
    }
  }
}
</style>