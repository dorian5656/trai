// 文件名：frontend/src/composables/useFileUpload.ts
// 作者：zcl
// 日期：2026-01-28
// 描述：文件上传逻辑复用

import { ref } from 'vue';
import { ElMessage } from 'element-plus';
import { chunkedUpload } from '@/api/common';
import { ErrorHandler } from '@/utils/errorHandler';

export interface UploadFile {
  id: string;
  name: string;
  size: string;
  type: string;
  progress: number;
  status: 'uploading' | 'parsing' | 'done' | 'error';
  url?: string;
}

export function useFileUpload() {
  const uploadedFiles = ref<UploadFile[]>([]);
  
  // 图片预览相关状态
  const showViewer = ref(false);
  const previewUrlList = ref<string[]>([]);
  const initialIndex = ref(0);

  const formatSize = (bytes: number) => {
    if (bytes === 0) return '0 B';
    const k = 1024;
    const sizes = ['B', 'KB', 'MB', 'GB', 'TB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(1)) + ' ' + sizes[i];
  };

  const handleFileSelect = async (event: Event) => {
    const target = event.target as HTMLInputElement;
    if (target.files && target.files.length > 0) {
      const file = target.files[0];
      if (!file) return;
      
      const newFile: UploadFile = {
        id: Date.now().toString(),
        name: file.name,
        size: formatSize(file.size),
        type: file.type,
        progress: 0,
        status: 'uploading',
      };

      if (file.type.startsWith('image/')) {
        newFile.url = URL.createObjectURL(file); // 先用本地预览
      }

      uploadedFiles.value.push(newFile);
      target.value = ''; // 重置 input

      // 获取响应式对象引用，确保后续修改能触发视图更新
      const activeFile = uploadedFiles.value.find(f => f.id === newFile.id)!;

      try {
        const res = await chunkedUpload(file, 'chat', (percent) => {
          activeFile.progress = percent;
        });
        
        activeFile.status = 'done';
        if (res.url) {
          activeFile.url = res.url; // 更新为远程 URL
        }
        // 强制设置进度为 100%，防止 onUploadProgress 未触发最后一次
        activeFile.progress = 100;
      } catch (error: any) {
        console.error('上传失败:', error);
        activeFile.status = 'error';
        const appError = ErrorHandler.handleHttpError(error);
        ElMessage.error(`${activeFile.name} 上传失败: ${appError.message}`);
      }
    }
  };

  const removeFile = (id: string) => {
    const index = uploadedFiles.value.findIndex(f => f.id === id);
    if (index !== -1) {
      uploadedFiles.value.splice(index, 1);
    }
  };

  const handlePreview = (file: UploadFile) => {
    // 允许预览所有 image 类型文件，即使还在上传中（因为有本地 blob URL）
    if (file.url && file.type.startsWith('image/')) {
      // 收集所有可预览的图片 URL
      const images = uploadedFiles.value
        .filter(f => f.url && f.type.startsWith('image/'))
        .map(f => f.url as string);
      
      const index = images.indexOf(file.url);
      
      if (index !== -1) {
        previewUrlList.value = images;
        initialIndex.value = index;
        showViewer.value = true;
      }
    }
  };

  const closeViewer = () => {
    showViewer.value = false;
  };

  const clearFiles = () => {
    uploadedFiles.value = [];
  };

  return {
    uploadedFiles,
    showViewer,
    previewUrlList,
    initialIndex,
    handleFileSelect,
    removeFile,
    handlePreview,
    closeViewer,
    clearFiles
  };
}
