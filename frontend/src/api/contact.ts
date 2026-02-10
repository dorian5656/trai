// 文件名：frontend/src/api/contact.ts
// 作者：zcl
// 日期：2026-02-03
// 描述：联系/线索接口封装

import request from '@/utils/request';
import { v4 as uuidv4 } from 'uuid';

export interface ContactLeadRequest {
  name: string;
  phone: string;
  product: string;
  region: string;
  submissionId: string;
}

export interface ContactLeadResponse {
  code: number;
  msg: string;
  data: {
    id: number;
  };
}

/**
 * 提交联系线索
 * @param data 联系线索数据
 * @returns 提交结果
 * 
 * 说明：
 * - submissionId 会自动生成唯一 UUID
 * - 如果返回 "重复提交"，说明 submissionId 重复
 * - 使用 AxiosResponse 来获取完整的响应
 */
export const submitContactLead = async (data: Omit<ContactLeadRequest, 'submissionId'>): Promise<ContactLeadResponse> => {
  const requestData: ContactLeadRequest = {
    ...data,
    submissionId: uuidv4()
  };

  // 使用 AxiosResponse 来获取完整的响应
  return new Promise((resolve, reject) => {
    request.post<ContactLeadRequest, any>('/contact/lead', requestData).then(response => {
      // 如果是 error，说明是通过拦截器 reject 的
      if (response instanceof Error) {
        reject(response);
        return;
      }

      // 检查是否有 msg 字段
      if (response && typeof response === 'object' && 'msg' in response) {
        resolve({
          code: 200,
          msg: response.msg || '提交成功',
          data: response.data || response
        });
      } else {
        // 拦截器已自动解包，说明是成功
        resolve({
          code: 200,
          msg: '提交成功',
          data: response || { id: 0 }
        });
      }
    }).catch(error => {
      // 检查错误响应
      if (error.response && error.response.data) {
        const { msg, code } = error.response.data;
        if (msg && msg.includes('重复提交')) {
          resolve({
            code: code || 400,
            msg: msg || '重复提交',
            data: { id: 0 }
          });
        } else {
          resolve({
            code: code || 500,
            msg: msg || '提交失败',
            data: { id: 0 }
          });
        }
      } else {
        reject(error);
      }
    });
  });
};
