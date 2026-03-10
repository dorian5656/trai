
// 文件名：frontend/src/api/meeting.ts
// 作者：zcl & whf
// 日期：2026-03-09 (重构)
// 描述：会议模块相关接口

import request from '@/utils/request';

// 会议记录（发言）的TypeScript接口
export interface MeetingRecord {
  id: number;
  speaker_name: string;
  content: string;
  record_time: string;
  audio_duration?: number;
}

// 会议主信息的TypeScript接口
export interface Meeting {
  id: number;
  meeting_title: string;
  meeting_no: string;
  start_time: string;
  end_time?: string;
  user_id: string; // 关联 sys_users.username
  status: number;
  records?: MeetingRecord[]; // 详情中包含发言记录
}

// --- API 请求函数 ---

/**
 * 创建新会议
 * @param data 包含会议标题和开始时间
 */
export const createMeeting = (data: { title: string; start_time: string }) => {
  return request.post<Meeting>('/meeting/create', data);
};

/**
 * 获取当前用户主持的会议列表
 * @param params 分页参数
 */
export const getMeetingList = (params: { page?: number; size?: number; status?: number; title?: string }) => {
  return request.get<{ items: Meeting[]; total: number; page: number; size: number }>('/meeting/list', { params });
};

/**
 * 获取会议详情，包括所有发言记录
 * @param meetingId 会议ID
 */
export const getMeetingDetail = (meetingId: number) => {
  return request.get<Meeting>(`/meeting/detail/${meetingId}`);
};

/**
 * 删除会议（逻辑删除）
 * @param meetingId 会议ID
 */
export const deleteMeeting = (meetingId: number) => {
  return request.post<void>(`/meeting/delete/${meetingId}`);
};

/**
 * 添加一条发言记录
 * @param data 发言记录的详细信息
 */
export const addMeetingRecord = (data: {
  meeting_id: number;
  user_id: string;
  speaker_name: string;
  content: string;
  record_time: string;
  audio_file_key?: string;
  audio_file_url?: string;
  audio_duration?: number;
  audio_format?: string;
  audio_size?: number;
  parent_id?: number;
}) => {
  return request.post<{ record_id: number }>('/meeting/record/add', data);
};

/**
 * 更新一条发言记录的内容
 * @param data 包含记录ID和新内容
 */
export const updateMeetingRecord = (data: { record_id: number; content: string }) => {
  return request.post<void>('/meeting/record/update', data);
};

/**
 * 更新会议的属性
 * @param data 包含会议ID和要更新的字段
 */
export const updateMeeting = (data: { meeting_id: number; title?: string }) => {
  return request.post<void>('/meeting/update', data);
};
