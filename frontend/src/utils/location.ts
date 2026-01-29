// 文件名：frontend/src/utils/location.ts
// 作者：zcl
// 日期：2026-01-28
// 描述：位置与用户ID工具 (去除百度地图API)

import { v4 as uuidv4 } from 'uuid';
import { getCookie, setCookie } from './cookie';

const USER_ID_KEY = 'trai_user_id';

/**
 * 获取或生成用户ID
 * 格式: 随机UUID (已移除省份前缀，因为不再调用地图API)
 */
export async function getLocationBasedUserId(): Promise<{ userId: string; province: string }> {
  let userId = getCookie(USER_ID_KEY);
  const province = '未知'; // 不再获取真实位置

  if (!userId) {
    // 生成新的 ID
    userId = `user_${uuidv4().slice(0, 8)}`;
    setCookie(USER_ID_KEY, userId);
  }

  return { userId, province };
}

export function getUserIdFromCookie(): string | null {
  return getCookie(USER_ID_KEY);
}

export function saveUserIdToCookie(userId: string) {
  setCookie(USER_ID_KEY, userId);
}
