// 文件名：frontend/src/composables/useFileUpload.ts
// 作者：zcl
// 日期：2026-01-28
// 描述：文件上传逻辑复用

import { ref } from 'vue';
import { ElMessage } from 'element-plus';
import { uploadFile } from '@/api/common';

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

      try {
        const res = await uploadFile(file, 'chat', (percent) => {
          newFile.progress = percent;
        });
        
        newFile.status = 'done';
        if (res.url) {
          newFile.url = res.url; // 更新为远程 URL
        }
      } catch (error) {
        console.error('上传失败:', error);
        newFile.status = 'error';
        ElMessage.error(`${newFile.name} 上传失败`);
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
    if (file.url && file.type.startsWith('image/')) {
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
