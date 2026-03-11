// 文件名：frontend/src/utils/errorTypes.ts
// 作者：zcl
// 日期：2026-02-03
// 描述：错误类型定义

/**
 * 错误类型常量对象 (替代 enum 以支持 erasableSyntaxOnly)
 */
export const ErrorType = {
  /** 网络错误 */
  NETWORK_ERROR: 'NETWORK_ERROR',
  /** 未授权（401） */
  UNAUTHORIZED: 'UNAUTHORIZED',
  /** 禁止访问（403） */
  FORBIDDEN: 'FORBIDDEN',
  /** 资源不存在（404） */
  NOT_FOUND: 'NOT_FOUND',
  /** 请求参数错误（400） */
  BAD_REQUEST: 'BAD_REQUEST',
  /** 服务器内部错误（500） */
  SERVER_ERROR: 'SERVER_ERROR',
  /** 业务逻辑错误 */
  BUSINESS_ERROR: 'BUSINESS_ERROR'
} as const;

export type ErrorType = typeof ErrorType[keyof typeof ErrorType];

/**
 * 应用错误接口
 */
export interface AppError {
  /** 错误类型 */
  type: ErrorType;
  /** 错误消息 */
  message: string;
  /** 原始错误对象（可选） */
  originalError?: any;
  /** HTTP 状态码（可选） */
  statusCode?: number;
}
