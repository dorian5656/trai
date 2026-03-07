// 文件名：frontend/src/api/speech.ts
// 作者：zcl
// 日期：2026-03-06
// 描述：语音识别相关API接口

import request from '@/utils/request';

/**
 * 语音识别结果列表参数
 */
export interface TranscriptionsParams {
  page?: number;
  size?: number;
  start_time?: string;
  end_time?: string;
  status?: string;
}

/**
 * 语音识别结果项
 */
export interface TranscriptionItem {
  id: string;
  audio_url: string;
  s3_key?: string;
  recognition_text: string;
  duration?: number;
  model_version: string;
  status: string;
  error_msg?: string;
  created_at: string;
  updated_at: string;
}

/**
 * 语音识别结果列表响应
 */
export interface TranscriptionsResponse {
  code: number;
  msg: string;
  data: {
    items: TranscriptionItem[];
    page: number;
    size: number;
    total: number;
  };
}

/**
 * 语音识别结果详情响应
 */
export interface TranscriptionDetailResponse {
  code: number;
  msg: string;
  data: TranscriptionItem;
}

/**
 * 获取语音识别结果列表
 */
export const getTranscriptions = (params: TranscriptionsParams) => {
  return request.get<TranscriptionsResponse>('/speech/transcriptions', { params });
};

/**
 * 获取单个语音识别结果详情
 */
export const getTranscription = (transcriptionId: string) => {
  return request.get<TranscriptionDetailResponse>(`/speech/transcriptions/${transcriptionId}`);
};
