# TRAI 桌面客户端 (pyqt_app)

TRAI 桌面客户端是基于 **PyQt6** 构建的现代化 AI 工具箱，旨在为用户提供便捷的 AI 服务入口与系统管理工具。项目采用扁平化 UI 设计，支持异步任务处理与模块化扩展。

## ✨ 核心功能 (Features)

- **👤 用户中心**: 支持账号登录与注册，基于 JWT 的权限管理。
- **💬 DeepSeek 对话**: 集成 DeepSeek 大模型，支持流式对话、上下文记忆、图片粘贴与文件附件上传。
- **📚 文档工具箱**: 提供 Markdown/Word/Excel/PPT/图片 转 PDF，以及 PDF 转图片/Word/PPT、PDF 转换、长图拼接等 17+ 种文档处理工具。
- **📊 系统监控**: 实时监控 GPU (显存/温度)、CPU、内存与磁盘状态，支持一键系统健康诊断。
- **🎨 AI 创作**:
  - **文生图**: 调用后端 API 生成高质量图像。
  - **图片解析**: 基于多模态模型解析图片内容。
- **🛠️ ModelScope 工具**: 本地模型管理的上传与下载。
- **📝 业务工具**: "rrdsppg" 业务模块集成 (核心: paddleocr和yolo)。

## 🧩 技术栈 (Tech Stack)

- **GUI 框架**: PyQt6 (6.4.2)
- **编程语言**: Python 3.11.14
- **网络请求**: Requests (RESTful API)
- **异步处理**: QThread (PyQt 原生多线程)
- **界面样式**: QSS (CSS-like 样式表)
- **日志系统**: Loguru
- **打包部署**: Conda 环境管理

## 🚀 快速启动 (Quick Start)

### 1. 环境准备

确保已安装 Python 3.11.14。建议使用 Conda 环境。

```bash
# 激活项目环境 (与后端共用或独立创建)
conda activate pyqt6
# 或其他环境

# 安装依赖
pip install -r requirements_pyqt.txt -i https://pypi.tuna.tsinghua.edu.cn/simple
```

### 2. 运行程序

进入 `backend/pyqt_app` 目录并运行启动脚本：

```bash
cd backend/pyqt_app
python run.py
```

## 📦 打包发布 (Packaging)

项目提供一键打包脚本，可将 Python 源码打包为独立的 Windows 可执行文件 (.exe)。

### 1. 安装 PyInstaller

如果尚未安装打包工具，请运行：

```bash
pip install pyinstaller -i https://pypi.tuna.tsinghua.edu.cn/simple
```

### 2. 执行打包

在 `backend/pyqt_app` 目录下运行 `build_onefile.py` 或 `build_onedir.py` 脚本：

```bash
cd backend/pyqt_app
python build_onefile.py
```

### 3. 打包EXE

打包完成后，可执行文件位于 `dist` 目录下，提供两种部署方式：

#### 方式一：单文件 (OneFile)
- **路径**: `dist/TraiClient.exe`
- **特点**: 单个文件，方便分发，即点即用。
- **配置**: 程序内置默认配置。如需修改，可在 `TraiClient.exe` 同级目录下创建 `config.json` 文件进行覆盖。

#### 方式二：文件夹 (OneDir)
- **路径**: `dist/TraiClient/TraiClient.exe`
- **特点**: 启动速度快，易于排查问题。
- **配置**: 直接修改目录下的 `config.json` 文件即可。

> **注意**: 首次运行时，若需要连接远程服务器，请手动创建/修改 `config.json` 或确保本地后端服务已启动 (默认连接 localhost)。

## ⚙️ 配置说明 (Configuration)

客户端配置文件位于 `pages/config.json`，用于管理后端 API 地址与默认参数。

```json
{
    "login": {
        "api_url": "http://127.0.0.1:5789/api_trai/v1/auth/login/json",
        ...
    },
    "deepseek": {
        "chat_url": "http://127.0.0.1:5789/api_trai/v1/ai/chat/completions",
        ...
    },
    ...
}
```

> **注意**: 首次运行前，请确保 将`config.json.example` 修改为 `config.json` 并将其中的 API 地址指向正确的后端服务 IP (默认为 `127.0.0.1` 或 `localhost`)。

## 📂 目录结构 (Structure)

```text
pyqt_app/
├── run.py                  # [入口] 程序启动脚本
├── main_window.py          # [核心] 主窗口逻辑与侧边栏导航
├── pages/                  # [页面] 功能模块页面
│   ├── config.json         # [配置] API 接口配置
│   ├── config_loader.py    # [工具] 配置加载单例
│   ├── login_page.py       # [页面] 登录/注册
│   ├── deepseek_page.py    # [页面] AI 对话
│   ├── doc_tools_page.py   # [页面] 文档工具箱
│   ├── system_monitor_page.py # [页面] 系统监控
│   └── ...
├── styles/
│   └── style.qss           # [UI] 全局 QSS 样式表
└── icon/                   # [资源] 应用图标
```

## 🛠️ 开发指南 (Development Guide)

### 1. 项目结构

- **`run.py`**: 程序入口，初始化主窗口。
- **`main_window.py`**: 主窗口类，包含侧边栏导航与页面栈管理。
- **`pages/`**: 功能模块页面目录，每个模块对应一个 `.py` 文件。
- **`styles/`**: 全局 QSS 样式表目录。
- **`icon/`**: 应用图标目录。

### 2. 新增页面

1. **新建页面**: 在 `pages/` 目录下创建新的 `.py` 文件，继承 `QWidget`。
2. **注册页面**:
   - 在 `pages/__init__.py` 中导出新页面类。
   - 在 `main_window.py` 中导入，并在 `init_ui` 中添加到 `QStackedWidget`。
   - 使用 `add_sidebar_item` 添加侧边栏入口。
3. **异步处理**: 耗时操作（如网络请求）**必须**使用 `QThread` (Worker) 放到后台执行，通过 `Signal` 更新 UI，防止界面卡死。

## 📝 更新日志 (Changelog)

### 2026_02_11_1725

- **优化**: 优化exe文件可以同时打开多个的问题
- **优化**: 优化修改配置文件需要重启的问题
- **优化**: 优化配置修改展示，只展示IP和端口，取消重置选项
- **优化**: 优化检查更新，只检查exe文件的更新
- **优化**: 打包时，自动将exe文件上传至服务器

### 2026_02_11_1047

- **新增**: 增加系统设置，可以手动更改API配置
- **优化**: 文档转换工具，转换成功后，可以选择直接打开文件或跳转至文件保存路径
- **优化**: 优化关闭程序逻辑，直接退出程序或最小化至系统托盘

### 2026_02_10_1546

- **新增**: 实现文档工具箱模块包括但不限于电子书转换 (`ebook_convert`)、OFD 转 PDF/图片 (`ofd2pdf`, `ofd2img`)、SVG 转 PDF (`svg2pdf`)、图片格式转换 (`img_convert`) 等核心功能逻辑及 API 对接。
- **优化**: 微调文档工具页 (`DocToolsPage`) 布局 (卡片尺寸 200x130)，优化视觉体验并消除横向滚动条。

### 2026_02_10_1016

- **新增**: 文档工具箱模块 (`DocToolsPage`)，包含 17 种文档转换功能入口。
- **优化**: 完善项目文档 README.md。

### 2026_02_09_1530

- **新增**: 系统监控模块，支持 GPU/系统资源实时检测。
- **优化**: DeepSeek 对话支持图片粘贴上传。
