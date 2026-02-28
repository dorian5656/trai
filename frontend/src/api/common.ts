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

export interface ChunkInitResponse {
  upload_id: string;
  uploaded_chunks: number[];
}

export interface ChunkProgressResponse {
  upload_id: string;
  uploaded_chunks: number[];
}

/**
 * 计算文件 SHA-256 指纹
 */
// 目前后端未校验文件哈希，保留占位实现以便后续扩展
// const computeFileHash = async (file: File): Promise<string> => {
//   const buffer = await file.arrayBuffer();
//   const digest = await crypto.subtle.digest('SHA-256', buffer);
//   const bytes = new Uint8Array(digest);
//   return Array.from(bytes).map((b) => b.toString(16).padStart(2, '0')).join('');
// };

/**
 * 分片上传 (断点续传)
 * - 后端接口:
 *   - POST /upload/chunk/init
 *   - GET  /upload/chunk/progress
 *   - POST /upload/chunk/upload
 *   - POST /upload/chunk/merge
 */
export const chunkedUpload = async (
  file: File,
  module: string = 'common',
  onProgress?: (percent: number) => void,
): Promise<UploadResult> => {
  // 1) 初始化
  const initRes = await request.post<any, ChunkInitResponse>('/upload/chunk/init', { filename: file.name });

  const upload_id = initRes.upload_id;
  const chunkSize = 5 * 1024 * 1024; // 默认 5MB
  const totalChunks = Math.ceil(file.size / chunkSize);

  // 2) 查询进度 (可选断点续传)
  let uploadedSet = new Set<number>();
  try {
    const progress = await request.get<any, ChunkProgressResponse>('/upload/chunk/progress', { params: { upload_id } });
    if (progress && Array.isArray(progress.uploaded_chunks)) {
      // 后端 part_number 从 1 开始，统一转换为 0 基
      uploadedSet = new Set(progress.uploaded_chunks.map((n) => n - 1));
    }
  } catch {
    // 无进度也可继续
  }

  // 3) 逐片上传
  for (let index = 0; index < totalChunks; index++) {
    if (uploadedSet.has(index)) {
      const percent = Math.round(((index + 1) * 100) / totalChunks);
      onProgress && onProgress(percent);
      continue;
    }
    const start = index * chunkSize;
    const end = Math.min(file.size, start + chunkSize);
    const chunk = file.slice(start, end);

    const formData = new FormData();
    formData.append('upload_id', upload_id);
    formData.append('part_number', (index + 1).toString()); // 后端从 1 开始
    formData.append('file', new Blob([chunk], { type: file.type || 'application/octet-stream' }));

    await request.post('/upload/chunk/upload', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    });

    const percent = Math.round(((index + 1) * 100) / totalChunks);
    onProgress && onProgress(percent);
  }

  // 4) 合并
  const mergePayload = {
    upload_id,
    total_parts: totalChunks,
    filename: file.name,
    module,
  };
  const mergeRes = await request.post<any, UploadResult>('/upload/chunk/merge', mergePayload);
  onProgress && onProgress(100);
  return mergeRes;
};
