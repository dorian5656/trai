// 文件名：frontend/src/api/customer.ts
// 作者：zcl
// 日期：2026-01-28
// 描述：客户留资 API

import request from '@/utils/request';

export interface CustomerData {
  name: string;
  phone: string;
  product: string;
  zona: string; // 保持与旧代码字段名一致
  region?: string;
}

/**
 * 提交客户留资信息
 */
export const submitCustomerInfo = async (data: CustomerData) => {
  // TODO: 后端尚未迁移 /customer/submit 接口，此处使用 Mock
  console.log('Mock submit customer info:', data);
  
  return new Promise<{ success: boolean; message: string }>((resolve) => {
    setTimeout(() => {
      resolve({
        success: true,
        message: '提交成功 (Mock)'
      });
    }, 1000);
  });

  // 待后端就绪后切换为真实调用:
  // return request.post('/customer/submit', data);
};
