# TRAI 后端项目 (TRAI Backend)

TRAI 核心后端服务仓库，基于 FastAPI + PostgreSQL + AI (PaddleOCR/YOLO/Dify/DeepSeek) 构建。

## 🚀 快速启动 (Quick Start)

### 后端 (Backend)

#### 1. 激活环境
```bash
conda activate trai_31014_whf
```

#### 2. 启动服务3

```bash
# 在项目根目录下执行
python backend/run.py
```

> **注意**: 启动脚本会自动检查端口占用情况 (读取 .env 配置)。若端口被占用，脚本会自动尝试结束占用进程 (支持 Windows/Linux/MacOS)。

### 前端 (Frontend)

#### 1. 安装依赖
```bash
cd frontend
npm install
```

#### 2. 启动开发服务器
```bash
npm run dev
```

#### 3. 打包构建
```bash
# 构建 Web 版本
npm run build

# 构建桌面版 (.exe) - 需先参考 ELECTRON_GUIDE.md 配置
npm run build
```

### 桌面客户端 (Client App)

位于 `backend/client_app`，基于 PyQt5 开发，支持 AI 对话与服务管理。

#### 1. 安装依赖
```bash
pip install PyQt5 pyinstaller requests
```

#### 2. 运行开发版
```bash
python backend/client_app/client_main.py
```

#### 3. 打包 EXE
```bash
python backend/client_app/build.py
```

## 📚 接口文档 (API Docs)

服务启动后，可访问以下地址查看 Swagger UI 交互式文档：

- **本地文档**: [http://localhost:5689/api/v1/docs](http://localhost:5689/api/v1/docs)
- **OpenAPI JSON**: [http://localhost:5689/api/v1/openapi.json](http://localhost:5689/api/v1/openapi.json)

## 🔧 环境依赖 (GPU 版)

本项目深度依赖 GPU 加速 (CUDA)，请根据您的操作系统选择合适的依赖安装方式。

### 💻 Windows 环境 (NVIDIA GeForce RTX 3060)

当前开发环境配置参考：
- **GPU**: NVIDIA GeForce RTX 3060 (12GB)
- **Driver**: 591.74
- **CUDA Toolkit**: 11.8 ~ 12.1 Compatible
- **Python**: 3.10.14

#### 安装步骤
0. conda create -n trai_31014_whf python=3.10.14
    conda activate trai_31014_whf
1. 安装 Python 3.10_14
2. 安装 CUDA 11.8 或 12.1 (推荐)
3. 使用 pip 安装依赖 (已包含 Windows 特定补丁):

```bash
cd backend
pip install -r requirements_windows_gpu.txt
```

> **注意**: Windows 下 `paddlepaddle-gpu` 和 `paddleocr` 存在已知的 DLL 依赖问题 (缺失 `cudnn64_8.dll`)。
> `requirements_windows_gpu.txt` 中包含了一个特定版本的 `nvidia-cudnn-cu11`，且项目代码 (`ocr_utils.py`) 包含自动注入环境变量的补丁。
> 如果遇到 `cudnn64_8.dll not found` 错误，请确保按照此文件安装。

### 🐧 Linux 环境 (CentOS - NVIDIA L20)

当前生产/测试环境配置参考：
- **OS**: CentOS Stream 10
- **GPU**: NVIDIA L20 (48GB)
- **Driver**: 590.44.01
- **CUDA Version**: 13.1
- **Python**: 3.10.14

#### 安装步骤

1. 安装基础依赖:
```bash
yum install -y libGL  # CentOS 必需，否则 OpenCV 报错
```

2. 安装 Python 依赖:
```bash
cd backend
pip install -r requirements_centos.txt -i https://pypi.tuna.tsinghua.edu.cn/simple
```

> **注意**: CentOS 下若 `cv2` 报错 `ImportError: libGL.so.1`，请务必执行 `yum install -y libGL` 或 `yum install mesa-libGL`。

## 📚 开发规范
请务必阅读 `.trae/rules/backend_whf.md` 获取完整的开发规范索引。

- [后端规范索引](.trae/rules/backend_whf.md)
- [前端规范索引](.trae/rules/frontend_zcl.md)



## 📝 更新日志
### 2026_01_29_1730
- **后端**: 优化端口管理, 启动时自动检测并释放占用端口 (支持 Windows/Linux/MacOS).
- **后端**: 完善网络工具类 `NetUtils`, 统一中文注释与跨平台支持.
- **后端**: 规范化 git 配置, 移除 `.env` 版本控制.

### 2026_01_29_1636
- **后端**: 规范化环境配置加载逻辑 (`.env.example`), 明确 `PORT` 和 `ENV` 的配置方式.
- **后端**: 重启服务并验证生产环境配置 (Port: 5789).

### 2026_01_29_1612
- **后端**: 优化服务启动配置, 支持 CentOS 环境.
  - 端口分离: `.env` 配置区分开发 (`ENV_DEV_PORT`) 与生产 (`ENV_PORT`) 端口.
  - 启动优化: `run.py` 简化端口判断逻辑, 增加启动横幅 (Banner) 显示服务状态.
  - 依赖管理: 生成 CentOS 专用依赖文件 `requirements_centos.txt`, 修复 OpenCV 库缺失问题.
- **文档**: 更新生产环境部署文档 (CentOS 10 + L20 GPU).

### 2026_01_29_1537
- **后端**: 新增环境配置同步机制 (`sys_env_logs`), 启动时自动备份 `.env` 配置及机器信息.
- **客户端**: 
  - 架构重构: 将单一脚本拆分为 `ui`, `logic`, `utils` 模块化结构.
  - 功能增强: 新增自动登录、系统托盘、退出/注销选项.
  - 图像识别: 修复 S3 上传路径错误, 增加拖拽上传与多模态对话功能.
  - 打包优化: `build.py` 支持自动包含图标 (`pppg.ico`).

### 2026_01_29_1353
- **前端**: 优化官网助手对话框样式, 修复气泡宽度与换行问题, 统一使用 Flex 布局.

### 2026_01_29_1150
- **客户端**: 新增 PyQt5 桌面客户端 (`backend/client_app`), 支持 DeepSeek/Dify 对话及服务管理, 可打包为 EXE.
- **后端**: 优化 `ChatRouter` 路由, 接入 `AIManager` 统一入口, 支持 Qwen-VL 多模态模型调用.

### 2026_01_29_1120
- **文档**: 修复前端规范文档链接 (`frontend_zcl.md`).
- **后端**: 
  - 集成 `ModelScopeUtils` 实现多模态模型 (Qwen-VL) 的本地管理.
  - 优化推理队列，支持多卡调度与显存保护.

### 2026_01_29_1110
- **后端**: 实现本地多模态模型 (ModelScope/Qwen-VL) 的统一管理与异步推理队列.
  - 新增 `ModelScopeUtils`: 支持多卡自动调度、显存自动管理 (OOM 保护)、异步推理锁.
  - 重构 `chat_func.py`: 统一对话入口，自动路由本地模型与远程 API.
  - 优化 `run.py`: 启动时自动检测本地模型状态.
- **文档**: 更新快速启动指南，补充前端与 Electron 打包说明.

### 2026_01_29_1015
- **后端**: Dify 接口增强与配置更新.
  - 增强 `DifyApp.chat_messages` 支持显式传入 `api_key` 和 `mode` 参数.
  - 修复 Dify 接口 401 认证问题, 更新 `.env` 配置.
  - 完善 API 参数定义, 支持 `chat`, `workflow`, `completion` 多种模式.

### 2026_01_29_0941
- **后端**: 实现图片上传记录持久化 (user_images表), 添加图片列表与删除接口, 修复表结构自动初始化逻辑.

### 2026_01_29_0831
- **后端**: 优化服务启动流程与路由配置.
  - 启动脚本 (`run.py`) 增强: 增加环境变量加载日志与 Dify 配置检查.
  - 路由重构 (`backend/app/routers`): 规范化路由模块结构, 分离业务逻辑 (`_func.py`) 与路由定义 (`_router.py`).
  - 新增 `requirements_windows_gpu.txt` 依赖: 添加 AI 图像生成相关库 (`diffusers`, `transformers`, `accelerate`).

### 2026_01_28_1729
- **后端**: 医保码数据同步流程适配 PostgreSQL 数据库.
  - `yibao_code.py`: 完成 MySQL 到 PostgreSQL 的迁移, 包括数据存储与日志记录.
  - `post_fxcrm.py`: 优化 CRM 同步逻辑, 移除冗余表检查, 仅保留 `medical_consumables` 同步.
- **脚本**: 增强 `run_yibao_merge_fxcrm.sh` 跨平台兼容性.
  - 新增 Windows PowerShell 原生运行支持.
  - 优化 WSL/Git Bash 环境下的 Conda 解释器路径检测与自动切换.
### 2026_01_28_1618
- **前端**: 重构代码架构, 提取业务逻辑至 `Composables` (如 `useChatLogic`, `useSkills`), 提升代码复用性.
- **前端**: 重构聊天输入框组件 (`ChatInput`), 抽离 SVG 图标至独立资源文件.
- **前端**: 新增 `SmartAssistant` 智能助手页面及 `ContactForm` 组件.
- **前端**: 更新 API 模块及请求工具类, 优化类型定义与错误处理.


### 2026_01_28_1529
- **前端**: 修复 PC 端聊天界面输入框被遮挡的问题, 优化布局结构.
- **前端**: 全面规范化 CSS 单位, 强制使用相对单位 (rem/vw/vh) 替换 px.
- **文档**: 更新前端基础规范 (`11_frontend_base_zcl.md`), 明确样式单位强制要求.

### 2026_01_28_1022
- **后端**: 新增 AI 本地模型扫描功能.
  - 启动时自动扫描 `backend/app/models` 目录下的模型.
  - 针对 `Z-Image-Turbo` 等大显存模型增加启动警告提示.
  - 更新 `requirements_windows_gpu.txt` 添加 `diffusers`, `transformers` 等图像生成依赖.

### 2026_01_28_0919
- **后端**: 重构 Dify 集成配置, 支持多应用实例 (官网/财务).
  - 更新 `.env` 配置: 废弃 `DIFY_API_KEY`, 新增 `DIFY_GUANWANG_API_KEY` 和 `DIFY_CAIWU_API_KEY`.
  - 更新接口: Dify 相关 API 及工具类支持 `app_name` 参数 (默认 `guanwang`).
  - 启动检查: 服务启动时自动检测并打印已配置的 Dify 应用.

### 2026_01_28_0900
- **后端**: 集成 Dify AI 平台.
  - 新增 `DifyApp` 工具类 (`app/utils/dify_utils.py`), 封装对话与会话管理 API.
  - 新增 Dify 路由模块 (`app/routers/dify`), 提供 `/api/v1/dify/chat` 流式对话接口.
  - 配置项: `DIFY_API_BASE_URL` 和 `DIFY_API_KEY`.

### 2026_01_27_1745
- **后端**: 实现企业微信组织架构自动同步功能.
  - 支持启动时自动同步 (`WECOM_SYNC_ON_STARTUP=true`).
  - 实现部门树形结构 (`sys_departments`) 与人员信息 (`sys_users`) 的全量同步.
  - 自动处理离职人员状态 (标记 `is_active=False`).
  - 修复部门 ID 类型匹配问题, 确保用户准确关联到所属部门.
- **后端**: 优化企业微信 API 调用, 封装 `WeComService` 业务逻辑.
- **后端**: 清理冗余测试脚本, 规范化项目结构.

### 2026_01_27_1735
- **后端**: 生成 Linux GPU 环境依赖文件 (`backend/requirements_linux_gpu.txt`), 明确指定 PyTorch, PaddlePaddle, YOLO 等核心库版本.
- **后端**: 验证 `rrdsppg` 智能预测接口, 确认 OCR 与 YOLO 组合逻辑在 Linux 环境下的可用性.

### 2026_01_27_1732
- **前端**: 完成登录功能闭环与 UI 优化.
  - 新增登录页面 (`Login.vue`) 与路由配置, 支持 OAuth2 登录接口对接.
  - 新增用户状态管理 (`stores/user.ts`), 实现自动获取用户信息与状态持久化.
  - 首页 (`PC` & `Mobile`) 集成登录/退出功能, 侧边栏同步显示用户信息.
  - 优化 `SimilarityDialog` 组件, 支持图片拖拽上传与预览, 并修复大整数精度问题.
  - 修正 Axios 拦截器以兼容非标准 OAuth2 响应格式 (`access_token`).

### 2026_01_27_1620
- **后端**: 优化 `heart_like` 相关业务逻辑, 将 OCR 相似度触发阈值从 0.6 调整为 0.55, 提升准确率.

### 2026_01_27_1547
- **后端**: 修复 PaddleOCR 并发调用导致的 Tensor 内存错误 (添加线程锁).
- **后端**: 优化 `/rrdsppg/predict` 接口，增强请求参数校验与日志记录.
- **后端**: 更新文本清洗规则，增加去除 `★` 和 `√` 符号.

### 2026_01_27_1158
- **后端**: 增强 S3 对象存储功能。
  - 新增文件代理下载接口 (`/api/v1/upload/files/{path}`), 解决内网 S3 无法直接访问的问题。
  - 自动配置 S3 存储桶的 CORS 策略与公开读权限。
  - 更新依赖 `requirements_windows_gpu.txt` (新增 `aioboto3` 等)。

### 2026_01_27_1056
- **后端**: 增加 S3 对象存储支持。
  - 集成 `aioboto3` 实现异步文件上传。
  - 更新 `UploadUtils` 支持本地/S3 双模式切换。
  - 新增 S3 相关配置 (`S3_ENABLED`, `S3_ACCESS_KEY` 等)。

### 2026_01_27_1049
- **前端**: 新增相似度识别功能入口及弹窗组件.
  - 首页技能列表增加 `相似度识别` 选项.
  - 新增 `SimilarityDialog` 业务组件, 支持公众号/服务号类型选择及双图上传.
  - 封装 `/rrdsppg/predict` 接口调用逻辑.

### 2026_01_27_1036
- **后端**: 完善 DeepSeek API 集成，全面支持流式 (SSE) 与非流式对话。
- **后端**: 优化 `RequestLogMiddleware`，支持流式响应内容的自动合并与完整入库 (JSON 格式)。
- **后端**: 代码规范化重构，将 `ai_toolkit.py` 重命名为 `ai_utils.py` 并统一引用。
- **后端**: 更新 `.env.example`，补充 JWT、企业微信、飞书及 DeepSeek 等关键配置项。

### 2026_01_27_0957
- **前端**: 所有源代码文件统一添加标准文件头注释 (文件名, 作者, 日期, 描述).
- **文档**: 更新前端基础规范 (`11_frontend_base_zcl.md`), 强制要求添加文件头.

### 2026_01_27_0947
- **后端**: 重构 AI 模块，将 `routers/chat` 迁移至 `routers/ai`。
- **后端**: 集成 DeepSeek API 对话接口 (`/api/v1/ai/chat/completions`)。
  - 支持流式/非流式对话 (目前默认非流式)。
  - 需要在 `.env` 中配置 `DEEPSEEK_API_KEY`。
- **后端**: 修复 `test_ai_chat.py` 验证脚本及相关依赖。

### 2026_01_27_0930
- **后端**: 实现用户注册与认证系统。
  - 支持 `A0001-A9999` 格式用户名校验及 6 位以上密码。
  - 注册采用审核制，需超级管理员审核通过后方可登录。
  - 初始化超级管理员 `A6666` (密码 `123456`)。
  - 支持 JWT Token 认证及密码加密存储 (bcrypt)。
  - 实现个人中心获取用户信息、管理员审核用户、用户修改密码 (含修改理由) 等接口。

### 2026_01_27_0912
- **后端**: 增强 `db_init.py` 迁移鲁棒性, 支持 `sys_users` 表 `source` 字段自动迁移及关联表时间字段 (`created_at`/`updated_at`) 的强制修复.
- **后端**: 集成飞书机器人通知 (`FeishuBot`), 支持动态 Token 及环境变量 `FEISHU_TRAI_WEBHOOK_TOKEN` 配置.
- **文档**: 更新 `.trae/rules/00_backend_workflow_whf.md`, 明确 `git push` 为手动操作步骤.

### 2026_01_27_0844
- **后端**: 初始化 RBAC 权限管理系统表结构 (sys_users, sys_roles, sys_permissions, sys_departments), 支持用户、角色、权限及企业微信组织架构同步.
- **后端**: 集成企业微信机器人通知功能 (`WeComBot`), 统一管理 webhook 配置.

### 2026_01_27_0824
- **后端**: 修复 `ai_models_func.py` 和 `predict_func.py` 中模型加载的路径逻辑错误, 将硬编码的相对路径修正为基于 `BASE_DIR` 的绝对路径, 解决启动时找不到 YOLO 模型文件的问题.

### 2026_01_27_0809
- **后端**: 修复配置文件 (`config.py`) 中缺失的 RRDSPPG 环境变量定义, 解决启动时的 Pydantic 校验错误.

### 2026_01_27_0804
- **前端**: 提交 frontend 整个文件夹代码.

### 2026_01_27_0015
- **后端**: 优化启动日志的可读性, 将数据库检查、元数据更新、模型加载及同步等关键步骤的日志级别调整为 `SUCCESS`, 并补充详细的状态信息 (如加载的模型名、扫描数量).

### 2026_01_27_0007
- **后端**: 增加静态资源目录 (`backend/static`) 自动创建与挂载逻辑, 并在启动日志中体现状态.

### 2026_01_27_0003
- **文档**: 更新后端工作流规范 (`00_backend_workflow_whf.md`), 将文档关键步骤小标题规范调整为**四级标题** (`####`).
- **文档**: 优化 `README.md` 结构, 将 "安装步骤" 升级为四级标题, 以便在大纲中清晰展示.

### 2026_01_27_0002
- **文档**: 更新后端工作流规范 (`00_backend_workflow_whf.md`), 补充文档关键步骤小标题 (如 `**安装步骤**:`) 的格式规范.

### 2026_01_26_2353
- **文档**: 更新后端工作流规范 (`00_backend_workflow_whf.md`), 明确禁止手动预估提交时间, 强制要求使用系统时间; 增加 README 标点符号规范.
- **文档**: 更新数据库规范 (`04_backend_postgres_whf.md`), 明确时间字段必须使用 `TIMESTAMP(0)` 以统一格式.

### 2026_01_26_2355
- **后端**: 增强 OCR 工具类 (`ocr_utils.py`) 鲁棒性, 优化对 PaddleOCR 返回空结果的处理逻辑.
- **后端**: 统一 API 响应格式 (`response.py`), 标准化时间戳字段 `ts` 为 `YYYY-MM-DD HH:MM:SS`.

### 2026_01_26_2345
- **后端**: 完善 OCR 文本清洗规则, 增加多关键词支持、后缀截断及标点符号过滤, 提升相似度比对准确率.
- **后端**: 优化临时文件清理策略, 仅删除当前请求相关文件, 解决高并发下的文件冲突问题.
- **后端**: 修复清洗逻辑中的缩进错误及重复代码块, 提升代码质量.

### 2026_01_26_2330
- **后端**: 调整 OCR 预测接口 (itzx=1) 返回值为经过清洗规则处理后的文本, 确保比对结果一致性.
- **后端**: 修正 OCR 接口 debug 模式 (itzx=2), 明确返回原始未处理文本 (Raw Text) 以供调试.

### 2026_01_26_2322
- **后端**: 新增 rrdsppg 智能预测路由 (`/predict`), 支持根据任务类型自动分发.
- **后端**: 实现视频号组合预测逻辑 (Composite), 串行执行 OCR (>0.6) 与 YOLO (分类匹配), 确保高精度判定.
- **后端**: 将 OCR 过滤规则与 YOLO 分类配置移至 `.env` 环境变量, 提升配置灵活性.

### 2026_01_26_2300
- **后端**: 优化请求日志中间件 (LogMiddleware), 支持自动提取 JSON 响应中的业务错误信息 (msg/detail).
- **后端**: 增强错误识别逻辑, 将非 200 业务状态码 (code!=200) 统一记录为异常日志.

### 2026_01_26_2255
- **后端**: 升级 YOLO 预测接口, 支持 URL 自动下载与预测 (targetPath), 兼容 JSON/Form 请求.
- **后端**: 修复 YOLO 工具类中的路径类型错误, 增强下载模块的鲁棒性.
- **后端**: 统一预测接口参数规范, 增加 Pydantic 模型支持.

### 2026_01_26_2245
- **后端**: 优化 rrdsppg OCR 接口, 支持通过环境变量配置文本清洗规则 (去除字符/关键词截断).
- **后端**: 修复请求日志记录时间问题, 统一使用北京时间 (TIMESTAMP) 记录, 消除时区偏差.
- **数据库**: 调整 request_logs 表结构, 时间字段修正为 TIMESTAMP(0) 并迁移历史数据.

### 2026_01_26_2117
- **后端**: 重构 monitor, rrdsppg, chat 模块, 实现路由(_router)与逻辑(_func)分离.
- **后端**: 规范化文件名, 统一使用 _router.py 和 _func.py 后缀.
- **文档**: 更新后端开发规范, 明确路由包结构要求.

### 2026_01_26_2015
- **后端**: 新增 AI 模型注册表 (ai_model_registry), 支持模型自动扫描与入库.
- **后端**: 实现模型动态加载与 GPU 配置 (ModelService), 支持通过数据库开关模型.
- **后端**: 集成 `/monitor/models` 接口, 实时展示模型加载状态与配置.

### 2026_01_26_1955
- **后端**: 添加 GPU 环境监控接口 `/monitor/env/gpu` 与系统资源监控.
- **后端**: 修复 OCR 服务启动自检逻辑, 从 CPU 迁移至 GPU 环境 (PyTorch+Paddle).
- **后端**: 优化 PaddleOCR 初始化参数与显存管理.

### 2026_01_26_1908
- **后端**: 实现数据库自动初始化与元数据注册 (DBInitializer).
- **后端**: 新增请求日志中间件 (RequestLogMiddleware), 支持 Body 记录与设备识别.
- **后端**: 封装统一日志管理类 (LogManager), 优化日志格式与轮转策略.
- **文档**: 更新后端开发规范 (封装、命名、日志).

### 2026_01_26_1837
- **后端**: 初始化后端核心架构与路由.
- **构建**: 添加依赖配置与忽略文件.
- **文档**: 更新后端工作流与规范体系, 重命名工作流文件.

### 2026_01_26_1732
- **文档**: 拆分并优化前端工程化规范, 建立模块化规则体系.
- **前端**: 初始化 Vue3+TS+Vite 项目架构, 配置路径别名与基础样式.
- **前端**: 实现 PC/Mobile 端路由自动映射与设备检测.
- **前端**: 完成 PC 端侧边栏交互（收起/展开）与聊天界面开发.
- **前端**: 完成移动端抽屉式导航与自适应布局开发.

### 2026_01_26_1644
- **后端**: 初始化后端项目结构, 创建 `.env`、`run.py` 及 FastAPI 入口 `main.py`.

### 2026_01_26_1610
- **后端**: 完善工作流规范, 增加日志分类要求（后端/前端/数据库）.

### 2026_01_26_1604
- **后端**: 完善工作流规范, 明确分文件夹提交、中文日志及标准推送流程.

### 2026_01_26_1600
- **后端**: 在工作流规范中补充了时间戳生成命令, 方便日志记录.

### 2026_01_26_1558
- **后端**: 重构后端规范体系 (`00`~`06`), 明确提交/API核心规则; 精简文档内容.
- **数据库**: 强制PG+Vector+注释; 明确通用字段标准注释要求.
