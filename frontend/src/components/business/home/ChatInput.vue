<!--
文件名：frontend/src/components/business/home/ChatInput.vue
作者：zcl
日期：2026-01-28
描述：聊天输入框组件
-->
<script setup lang="ts">
import { ref, computed } from 'vue';
import type { UploadFile } from '@/composables/useFileUpload';
import type { Skill } from '@/composables/useSkills';
import { icons } from '@/assets/icons';
import { PLACEHOLDER_TEXT, SKILL_PLACEHOLDERS } from '@/constants/texts';
import ChatFileList from './ChatFileList.vue';

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

const placeholderText = computed(() => {
  const skill = props.activeSkill;
  if (skill && skill.label) {
    return SKILL_PLACEHOLDERS[skill.label] ?? PLACEHOLDER_TEXT.withSkillDefault;
  }
  return PLACEHOLDER_TEXT.default;
});
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
    <ChatFileList
      :uploaded-files="uploadedFiles"
      @remove-file="(id) => emit('removeFile', id)"
      @preview-file="(file) => emit('previewFile', file)"
    />

    <transition name="fade-slide">
      <div v-if="activeSkill" class="skill-tag-wrapper">
        <div class="skill-tag">
          <span class="skill-tag-icon" v-html="activeSkill.icon"></span>
          <span class="skill-tag-text">{{ activeSkill.label }}</span>
          <span class="skill-tag-close" @click.stop="emit('removeSkill')">
            <span style="width: 0.75rem; height: 0.75rem; display: block" v-html="icons.closeTiny"></span>
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
      :placeholder="placeholderText" 
    />
    <div class="input-actions">
      <!-- 上传按钮 -->
      <button class="icon-btn" @click="triggerFileInput">
        <span style="width: 1.25rem; height: 1.25rem; display: block" v-html="icons.attachment"></span>
      </button>
      <!-- 深度思考按钮 -->
      <button 
        class="icon-btn deep-think-btn" 
        :class="{ active: isDeepThinking }" 
        @click="emit('toggleDeepThink')"
        title="深度思考"
      >
        <span style="width: 1.25rem; height: 1.25rem; display: block" v-html="icons.deepThink"></span>
      </button>
      <div class="spacer"></div>
      <button class="icon-btn" :class="{ 'is-listening': isListening }" @click="emit('toggleListening')" title="语音输入">
        <span v-if="isListening" style="width: 1.25rem; height: 1.25rem; display: block" v-html="icons.micListening"></span>
        <span v-else style="width: 1.25rem; height: 1.25rem; display: block" v-html="icons.micNormal"></span>
      </button>
      <button class="send-btn" @click="isSending ? emit('stop') : emit('send')" :disabled="isSending">
        <span v-if="isSending" style="width: 0.875rem; height: 0.875rem; display: block" v-html="icons.sendSending"></span>
        <span v-else style="width: 1rem; height: 1rem; display: block" v-html="icons.sendNormal"></span>
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
  
  .param-bar {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    padding: 0.25rem 0.375rem;
    
    .chip {
      display: inline-flex;
      align-items: center;
      gap: 0.375rem;
      height: 1.875rem;
      padding: 0 0.625rem;
      border: 1px solid #e5e6eb;
      background: #f7f8fa;
      color: #4e5969;
      border-radius: 1.25rem;
      cursor: pointer;
      transition: all 0.2s;
      
      &:hover {
        background: #fff;
        box-shadow: 0 0.125rem 0.5rem rgba(0,0,0,0.06);
      }
      
      &.active {
        background: #eef2ff;
        border-color: #d0d4ff;
        color: #1d2129;
      }
      
      .chip-icon {
        width: 1rem;
        height: 1rem;
        display: flex;
        align-items: center;
        justify-content: center;
      }
      .chip-text {
        font-size: 0.8125rem;
        white-space: nowrap;
      }
      .chip-chevron {
        width: 0.75rem;
        height: 0.75rem;
        display: flex;
        align-items: center;
        justify-content: center;
        color: #86909c;
      }
    }

    .param-select {
      display: flex;
      align-items: center;
      gap: 0.375rem;
      padding: 0.3125rem 0.625rem;
      border: 1px solid #e5e6eb;
      border-radius: 1.25rem;
      background: #fff;
      transition: box-shadow 0.2s, border-color 0.2s;
      height: 1.875rem;
      
      &:hover {
        border-color: #d0d1d6;
        box-shadow: 0 0.125rem 0.5rem rgba(0,0,0,0.06);
      }
      
      .select-text {
        font-size: 0.8125rem;
        color: #4e5969;
        white-space: nowrap;
      }

      .el-select {
        width: 7.5rem;
        
        .el-input__wrapper {
          box-shadow: none;
          background: transparent;
          border-radius: 0.875rem;
          padding: 0 0.25rem;
          height: 1.375rem;
          
          .el-input__inner {
            font-size: 0.8125rem;
          }
        }
      }
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
.chip-popover {
  padding: 0.5rem !important;
  border-radius: 0.75rem !important;
  background: #fff !important;
  border: 1px solid #e5e6eb !important;
  box-shadow: 0 0.25rem 0.75rem rgba(0, 0, 0, 0.12) !important;
  
  .popover-list {
    display: flex;
    flex-direction: column;
  }
  .popover-item {
    font-size: 0.875rem;
    color: #1d2129;
    padding: 0.375rem 0.5rem;
    border-radius: 0.5rem;
    cursor: pointer;
    display: flex;
    align-items: center;
    justify-content: space-between;
  }
  .popover-item:hover {
    background: #f2f3f5;
  }
  .popover-item.active {
    background: #eef2ff;
    color: #165dff;
  }
  .popover-item .item-check {
    width: 1rem;
    height: 1rem;
    flex-shrink: 0;
    display: inline-flex;
  }
}
</style>
