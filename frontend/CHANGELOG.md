### 2026_02_11_1230
- **前端-内容**: 深度代码重构: 创建 `useHomeLogic` 聚合主页业务逻辑; 抽离 PC 端侧边栏为 `Sidebar.vue`，抽离移动端侧边栏为 `MobileSidebar.vue`; 大幅精简 `pc/Home.vue` 与 `mobile/Home.vue` 代码行数; 修复 `useSkills` 状态共享问题.

### 2026_02_11_1120
- **前端-内容**: 样式规范统一: 强制将 ChatInput, MessageList, SimilarityDialog, LoginModal, MeetingRecorder 等组件中的 `px` 单位替换为 `rem` 等相对单位，以符合前端强制规范; 更新前端规范文档。
- **前端-内容**: 代码重构与功能调整: 移除图像生成相关功能; 重构 PC 与 Mobile 端 Home 页，抽离会话管理 (`useChatSession`) 与布局状态 (`useLayoutState`) 逻辑至 composables，显著减少代码冗余; 影响文件: frontend/src/views/pc/Home.vue, frontend/src/views/mobile/Home.vue, frontend/src/composables/*.

### 2026_02_11_1050
- **前端-内容**: 修复自动切会话异常: 首会话切换增加健壮性与错误捕获, 避免 await 报错中断; 影响文件: frontend/src/views/pc/Home.vue。

### 2026_02_11_1049
- **前端-内容**: 加载态样式优化: 覆盖层改为纯白并在加载中隐藏输入区, 保证视觉一致不透底; 影响文件: frontend/src/views/pc/Home.vue。

### 2026_02_11_1046
- **前端-内容**: 会话消息加载态: 切换会话时聊天区域显示“正在加载历史消息...”覆盖层, 加载完成后自动恢复; 影响文件: frontend/src/views/pc/Home.vue。

### 2026_02_11_1043
- **前端-内容**: 优化登录与会话体验: 初始化时从 Token 解析用户, 减少“未登录”闪烁; 加载会话列表后自动切到第一条会话并显示聊天布局, 即使历史消息为空也不再出现空白界面; 影响文件: frontend/src/stores/user.ts, frontend/src/views/pc/Home.vue。

### 2026_02_11_0959
- **前端-内容**: 新对话创建防抖: 仅保留一个空会话; 重复点击“新对话”不再生成多条空会话; 影响文件: frontend/src/stores/chat.ts。

### 2026_02_11_0957
- **前端-内容**: 登录过期处理调整: 401 静默清理、不弹窗; 移除到期前提醒; 请求拦截器移除自动弹窗; 错误处理 401 不提示; 影响文件: frontend/src/utils/request.ts, frontend/src/stores/user.ts, frontend/src/utils/errorHandler.ts。

### 2026_02_10_1657
- **前端-内容**: 新增“文档工具”弹窗; 集成 PC/Mobile; 点击技能未登录弹登录窗; 完成转换接口封装; 类型检查与构建通过。

### 2026_02_10_1413
- **前端-内容**: 更新技能配置: 将“深入研究”替换为“文档工具”; 调整技能位置至“帮我写作”; 新增占位文案; 实现文档转换接口封装与聊天呈现; 扩展上传保存原始文件引用。

### 2026_02_10_0812
- **前端-内容**: 更新技能配置，将“AI 播客”替换为“发票识别”；更换票据样式图标；同步更新输入占位文案（支持识别抬头、金额、税率等）。
