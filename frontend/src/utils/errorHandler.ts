// 文件名：frontend/src/utils/errorHandler.ts
// 作者：zcl
// 日期：2026-02-03
// 描述：统一错误处理器

import { ElMessage } from 'element-plus';
import { ErrorType } from './errorTypes';
import type { AppError } from './errorTypes';

/**
 * 错误处理器类
 */
export class ErrorHandler {
  /**
   * 处理 HTTP 错误
   * @param error 原始错误对象
   * @returns 应用错误对象
   */
  static handleHttpError(error: any): AppError {
    // 处理有响应的错误
    if (error.response) {
      const status = error.response.status;
      
      switch (status) {
        case 401:
          return this.createError(ErrorType.UNAUTHORIZED, '登录状态已过期，请重新登录', error, status);
        case 403:
          return this.createError(ErrorType.FORBIDDEN, '没有操作权限', error, status);
        case 404:
          return this.createError(ErrorType.NOT_FOUND, '请求的资源不存在', error, status);
        case 400:
          return this.createError(ErrorType.BAD_REQUEST, '请求参数错误', error, status);
        case 500:
          return this.createError(ErrorType.SERVER_ERROR, '服务器内部错误', error, status);
        default:
          return this.createError(ErrorType.NETWORK_ERROR, '请求失败', error, status);
      }
    }
    
    // 处理网络错误（如断网）
    if (error.message) {
      // 处理各种错误消息格式
      if (error.message.includes('Request failed')) {
        const statusCode = error.message.match(/\d+/);
        if (statusCode && statusCode[0]) {
          const code = parseInt(statusCode[0]);
          switch (code) {
            case 401:
              return this.createError(ErrorType.UNAUTHORIZED, '登录状态已过期，请重新登录', error, code);
            case 404:
              return this.createError(ErrorType.NOT_FOUND, '请求的资源不存在', error, code);
            case 500:
              return this.createError(ErrorType.SERVER_ERROR, '服务器内部错误', error, code);
            default:
              return this.createError(ErrorType.NETWORK_ERROR, '请求失败', error, code);
          }
        }
      }
    }
    
    // 其他网络错误
    return this.createError(ErrorType.NETWORK_ERROR, '网络连接异常', error);
  }

  /**
   * 处理业务错误
   * @param code 错误码
   * @param message 错误消息
   * @returns 应用错误对象
   */
  static handleBusinessError(code: number, message: string): AppError {
    // 过滤掉可能的敏感信息
    const safeMsg = message.replace(/[^\u4e00-\u9fa5a-zA-Z0-9，。！？；："'()（）【】\[\]\s]/g, '');
    const errorMessage = safeMsg.length > 0 ? safeMsg : '业务处理失败';
    
    return this.createError(ErrorType.BUSINESS_ERROR, errorMessage);
  }

  /**
   * 显示错误提示
   * @param appError 应用错误对象
   */
  static showError(appError: AppError): void {
    ElMessage.error(appError.message);
  }

  /**
   * 创建错误对象
   * @param type 错误类型
   * @param message 错误消息
   * @param originalError 原始错误对象（可选）
   * @param statusCode HTTP 状态码（可选）
   * @returns 应用错误对象
   */
  private static createError(type: ErrorType, message: string, originalError?: any, statusCode?: number): AppError {
    return {
      type,
      message,
      originalError,
      statusCode
    };
  }
}
