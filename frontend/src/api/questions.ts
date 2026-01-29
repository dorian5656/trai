// 文件名：frontend/src/api/questions.ts
// 作者：zcl
// 日期：2026-01-28
// 描述：预设问题 API

import request from '@/utils/request';

/**
 * 获取预设问题列表
 */
export const getPresetQuestions = async () => {
  // TODO: 后端尚未迁移 /ai/api/questions/preset 接口，此处使用 Mock
  const defaultQuestions = [
    '驼人集团最近有什么新产品上市?',
    '驼人集团签约合作的医院有哪些?',
    '想咨询掌超产品?怎么联系?',
    '驼人医疗器械科技创新奖怎么报名?',
    '驼人集团是做什么的?',
    '我想经营驼人的产品应该怎么做?',
    '驼人有没有(产品名称)?',
    '驼人的公司地点在哪里?',
    '我是(学校、专业等)有合适的岗位吗?',
    '驼人有哪些岗位在招聘?'
  ];

  return new Promise<{ code: number; data: string[] }>((resolve) => {
    resolve({
      code: 200,
      data: defaultQuestions
    });
  });

  // 待后端就绪后切换为真实调用:
  // return request.get('/ai/api/questions/preset');
};
