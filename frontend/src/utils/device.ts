// 文件名：frontend/src/utils/device.ts
// 作者：zcl
// 日期：2026-01-27
// 描述：设备检测工具

// 检测是否为移动端设备
export const isMobile = (): boolean => {
  const userAgent = navigator.userAgent.toLowerCase();
  const mobileAgents = ['android', 'iphone', 'ipad', 'ipod', 'blackberry', 'windows phone'];
  const isMobileAgent = mobileAgents.some((agent) => userAgent.includes(agent));
  
  // 也可以结合屏幕宽度判断
  const isSmallScreen = window.matchMedia('(max-width: 768px)').matches;
  
  return isMobileAgent || isSmallScreen;
};
