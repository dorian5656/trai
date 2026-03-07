import request from '@/utils/request';

// 文件名：frontend/src/api/meeting.ts
// 作者：zcl & whf
// 日期：2026-03-07
// 描述：会议纪要相关接口

export interface Meeting {
  id: string;
  title: string;
  createdAt: string;
  text?: string;
  summary?: string;
}

/**
 * 获取会议记录列表
 */
export const getMeetingHistory = async (): Promise<{ items: Meeting[], total: number }> => {
  const res: any = await request.get('/meeting/list');
  return {
    items: res.items || [],
    total: res.total || 0
  };
};

/**
 * 获取会议记录详情
 */
export const getMeetingDetail = async (id: string): Promise<Meeting> => {
  const res: any = await request.get(`/meeting/detail/${id}`);
  return {
    id: res.id,
    title: res.title,
    text: res.text,
    summary: res.summary,
    createdAt: res.created_at
  };
};

/**
 * 创建会议记录
 */
export const createMeeting = async (data: { title: string, text: string, summary?: string }): Promise<Meeting> => {
  const res: any = await request.post('/meeting/create', data);
  return {
    id: res.id,
    title: res.title,
    text: res.text,
    summary: res.summary,
    createdAt: res.created_at
  };
};

/**
 * 删除会议记录
 */
export const deleteMeeting = async (id: string): Promise<void> => {
  await request.delete(`/meeting/delete/${id}`);
};
