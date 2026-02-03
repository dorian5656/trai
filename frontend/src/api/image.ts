// 文件名：frontend/src/api/image.ts
// 作者：zcl
// 日期：2026-02-03
// 描述：图像生成相关接口

import request from '@/utils/request';

/**
 * 图像生成请求参数
 */
export interface ImageGenRequest {
  /** 提示词 */
  prompt: string;
  /** 模型名称 (固定为 "Z-Image") */
  model: string;
  /** 图片尺寸 (默认 1024x1024) */
  size?: string;
  /** 生成数量 (默认 1) */
  n?: number;
}

/**
 * 图像生成响应数据
 */
export interface ImageGenResponse {
  /** 创建时间戳 */
  created: number;
  /** 图片数据列表 */
  data: Array<{
    /** 图片 URL */
    url: string;
  }>;
}

/**
 * 图像生成接口
 * @param data 请求参数
 * @returns 图像生成结果（可能是完整的 ImageGenResponse 或直接的数据数组）
 */
export const generateImage = (data: ImageGenRequest) => {
  return request.post<any, ImageGenResponse | Array<{ url: string }>>('/ai/image/generations', data);
};
