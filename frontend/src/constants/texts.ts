/*
文件名：frontend/src/constants/texts.ts
作者：zcl
日期：2026-02-05
描述：通用文案常量（欢迎文案、占位符、菜单与移动端侧边栏）
*/

export const PLACEHOLDER_TEXT = {
  default: '发消息 or 输入“/”选择技能',
  withSkillDefault: '请输入内容...',
  imageGen: '描述你所想象的画面、角色、情绪、场景、风格…',
};

export const SKILL_PLACEHOLDERS: Record<string, string> = {
  '图片识别': '上传图片或描述你要识别的内容',
  '图像生成': '描述你所想象的画面、角色、情绪、场景、风格…',
  '会议记录': '开始会议要点记录，支持语音与附件',
  '帮我写作': '说明写作主题、风格、受众与字数需求',
  '相似度识别': '粘贴两段文本或上传两个文件进行相似度比较',
  '数据分析': '描述数据问题，上传文件或粘贴样本',
  '深入研究': '描述研究问题、目标与期望输出',
  '发票识别': '上传发票图片或PDF，识别抬头、金额、税率等',
  'PPT 生成': '输入主题与大纲要求，自动生成PPT结构',
  '视频生成': '描述画面、脚本、时长与风格',
  '解题答疑': '粘贴题目，说明已知与疑惑点',
  '更多': '选择更多技能以体验',
};

export const MOBILE_TEXT = {
  welcomeTitle: '你好，我是驼人GPT',
  header: {
    newChatPill: '📝 新对话',
    login: '登录',
    logout: '退出',
  },
  sidebar: {
    usernameFallback: '驼人GPT',
    newChatBtn: '📝 新对话',
    recentSectionTitle: '最近对话',
    aboutBtn: 'ℹ️ 关于驼人GPT',
    closeBtn: '✕',
    menuItems: ['帮我写作', 'AI 创作', '更多'],
  },
};

export const PC_TEXT = {
  topBar: {
    welcomePrefix: '欢迎, ',
    login: '登录',
    logout: '退出',
  },
  sidebarFooter: '关于驼人GPT',
};
