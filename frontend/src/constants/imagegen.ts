/*
文件名：frontend/src/constants/imagegen.ts
作者：zcl
日期：2026-02-05
描述：图像生成参数选项常量
*/

export const IMAGEGEN_MODEL_OPTIONS = [
  { label: '月之暗面 V1', value: 'moonshot-v1' },
  { label: '通义千问 2.5', value: 'qwen-2.5' },
  { label: 'OpenAI o4-mini', value: 'o4-mini' },
  { label: 'OpenAI gpt-4.1', value: 'gpt-4.1' },
  { label: 'Claude 3.5', value: 'claude-3.5' },
];

export const RATIO_OPTIONS = [
  { label: '1:1', value: '1:1' },
  { label: '3:4', value: '3:4' },
  { label: '4:3', value: '4:3' },
  { label: '9:16', value: '9:16' },
  { label: '16:9', value: '16:9' },
];

export const STYLE_OPTIONS = [
  { label: '写实', value: 'photorealistic' },
  { label: '像素画', value: 'pixelart' },
  { label: '卡通', value: 'cartoon' },
  { label: '水墨', value: 'ink' },
  { label: '油画', value: 'oil' },
];

export const TEMPLATE_OPTIONS = [
  { label: '风景', value: 'landscape' },
  { label: '人物', value: 'portrait' },
  { label: '动物', value: 'animal' },
  { label: '科幻', value: 'scifi' },
  { label: '建筑', value: 'architecture' },
];
