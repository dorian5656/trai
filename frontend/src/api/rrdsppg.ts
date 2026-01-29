// 文件名：frontend/src/api/rrdsppg.ts
// 作者：zcl
// 日期：2026-01-27
// 描述：人人都是品牌官 - 智能预测接口

import request from '@/utils/request';

export interface PredictResult {
  // 根据后端返回定义，暂时使用宽松类型
  [key: string]: any;
}

export interface PredictRequest {
  taskId: number | string;
  userId: number | string;
  type: number | string;
  templatePath: string;
  targetPath: string;
  itzx?: number | string;
  // text?: string; // commented out in screenshot
}

/**
 * 智能预测接口
 * @param data 表单数据 (FormData) 或 JSON 对象 (PredictRequest)
 */
export const predictSimilarity = (data: FormData | PredictRequest) => {
  if (data instanceof FormData) {
    return request.post<any, PredictResult>('/rrdsppg/predict', data, {
      headers: {
        'Content-Type': 'multipart/form-data',
      },
    });
  } else {
    return request.post<any, PredictResult>('/rrdsppg/predict', data);
  }
};
