import request from '@/utils/request';

// 文件名：frontend/src/api/meeting.ts
// 作者：zcl
// 日期：2026-03-02
// 描述：会议纪要相关接口

export interface Meeting {
  id: string;
  title: string;
  createdAt: string;
  text?: string;
  summary?: string;
}

// Mock data for now
const mockHistory: Meeting[] = [
  { id: '1', title: '第一次周会纪要', createdAt: '2026-02-28', text: '这是第一次周会的详细逐字稿...', summary: '## 周会纪要\n- **决策**: 下周三发布新版本。' },
  { id: '2', title: '项目需求讨论', createdAt: '2026-02-25', text: '关于新功能模块的详细讨论记录...', summary: '## 需求讨论\n- **待办**: @张三 跟进支付接口问题。' },
  { id: '3', title: '移动端UI/UX重构评审', createdAt: '2026-02-22', text: 'UI/UX重构评审会议的完整记录...', summary: '## 评审纪要\n- **风险**: 新设计可能导致老用户不适应。' },
];

export const getMeetingHistory = async (): Promise<{ items: Meeting[], total: number }> => {
  console.log('Fetching mock meeting history');
  return Promise.resolve({ items: mockHistory, total: mockHistory.length });
};

export const getMeetingDetail = async (id: string): Promise<Meeting> => {
  console.log(`Fetching mock meeting detail for id: ${id}`);
  const meeting = mockHistory.find(m => m.id === id);
  if (meeting) {
    return Promise.resolve(meeting);
  }
  return Promise.reject('Meeting not found');
};

export const createMeeting = async (data: { title: string, text: string, summary?: string }): Promise<Meeting> => {
  console.log('Creating mock meeting');
  const newMeeting: Meeting = {
    id: String(Date.now()),
    ...data,
    createdAt: new Date().toISOString().split('T')[0],
  };
  mockHistory.unshift(newMeeting);
  return Promise.resolve(newMeeting);
};
