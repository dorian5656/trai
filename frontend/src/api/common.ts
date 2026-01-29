// 文件名：frontend/src/api/common.ts
// 作者：zcl
// 日期：2026-01-27
// 描述：通用接口 (如文件上传)

import request from '@/utils/request';

export interface UploadResult {
  url: string;
  filename: string;
  size: number;
  content_type: string;
  local_path?: string;
}

/**
 * 通用文件上传
 * @param file 文件对象
 * @param module 模块名称 (默认 common)
 */
export const uploadFile = (file: File, module: string = 'common', onProgress?: (percent: number) => void) => {
  const formData = new FormData();
  formData.append('file', file);
  formData.append('module', module);

  return request.post<any, UploadResult>('/upload/common', formData, {
    headers: {
      'Content-Type': 'multipart/form-data', 
    },
    onUploadProgress: (progressEvent) => {
      if (progressEvent.total && onProgress) {
        const percent = Math.round((progressEvent.loaded * 100) / progressEvent.total);
        onProgress(percent);
      }
    },
  });
};
