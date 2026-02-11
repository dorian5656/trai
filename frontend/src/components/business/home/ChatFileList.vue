<!--
文件名：frontend/src/components/business/home/ChatFileList.vue
作者：zcl
日期：2026-02-11
描述：聊天输入框文件列表子组件
-->
<script setup lang="ts">
import type { UploadFile } from '@/composables/useFileUpload';
import { icons } from '@/assets/icons';

const props = defineProps<{
  uploadedFiles: UploadFile[];
}>();

const emit = defineEmits<{
  (e: 'removeFile', id: string): void;
  (e: 'previewFile', file: UploadFile): void;
}>();
</script>

<template>
  <div v-if="props.uploadedFiles.length > 0" class="file-list">
    <div
      v-for="file in props.uploadedFiles"
      :key="file.id"
      class="file-card"
    >
      <div class="file-preview">
        <img
          v-if="file.url && file.type.startsWith('image/')"
          :src="file.url"
          alt="preview"
          @click="emit('previewFile', file)"
          style="cursor: pointer"
        />
        <div v-else class="file-icon">
          <div
            v-if="file.name.endsWith('.xlsx') || file.name.endsWith('.xls')"
            style="width: 1.5rem; height: 1.5rem"
            v-html="icons.excel"
          />
          <div
            v-else-if="
              file.name.endsWith('.mp3') ||
              file.name.endsWith('.wav') ||
              file.name.endsWith('.m4a') ||
              file.type.startsWith('audio/')
            "
            style="width: 1.5rem; height: 1.5rem"
            v-html="icons.audio"
          />
          <div
            v-else
            style="width: 1.5rem; height: 1.5rem"
            v-html="icons.fileDefault"
          />
        </div>

        <div v-if="file.status !== 'done'" class="upload-mask">
          <div v-if="file.status === 'uploading'" class="progress-ring">
            <svg width="24" height="24" viewBox="0 0 24 24">
              <circle
                cx="12"
                cy="12"
                r="10"
                fill="none"
                stroke="rgba(255,255,255,0.3)"
                stroke-width="2"
              />
              <circle
                cx="12"
                cy="12"
                r="10"
                fill="none"
                stroke="white"
                stroke-width="2"
                stroke-dasharray="62.83"
                :stroke-dashoffset="62.83 * (1 - file.progress / 100)"
                transform="rotate(-90 12 12)"
              />
            </svg>
            <span class="progress-text">{{ file.progress }}%</span>
          </div>
          <div v-else-if="file.status === 'parsing'" class="parsing-text">
            解析中...
          </div>
        </div>
      </div>

      <div class="file-info">
        <div class="file-name" :title="file.name">
          {{ file.name }}
        </div>
        <div class="file-meta">
          {{ file.status === 'parsing' ? '解析中...' : file.size }}
        </div>
      </div>

      <button
        class="remove-file-btn"
        @click="emit('removeFile', file.id)"
      >
        <span
          style="width: 0.75rem; height: 0.75rem; display: block"
          v-html="icons.closeSmall"
        />
      </button>
    </div>
  </div>
</template>

<style scoped lang="scss">
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
      box-shadow: 0 0.25rem 0.75rem rgba(0, 0, 0, 0.05);

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
        background: rgba(0, 0, 0, 0.4);
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
</style>

