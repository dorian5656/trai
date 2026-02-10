# TRAI 后端服务 (TRAI Backend)

TRAI 核心后端服务仓库，基于 FastAPI + PostgreSQL + AI (PaddleOCR/YOLO/Dify/DeepSeek) 构建。

## 🚀 快速启动 (Quick Start)

### 1. 激活环境

```bash
conda activate trai_31014_whf_pro_20260202
```

### 2. 启动服务

```bash
# 在项目根目录下执行
python backend/run.py
```

> **注意**: 启动脚本会自动检查端口占用情况 (读取 .env 配置)。若端口被占用，脚本会自动尝试结束占用进程 (支持 Windows/Linux/MacOS)。

## 📹 AI 视频生成 (Wan2.1)

项目集成了 Wan2.1-T2V-1.3B 模型，支持文本生成视频。

### 特性
- **文本生成视频**: 支持中文/英文提示词
- **自动封面提取**: 使用 OpenCV 自动提取视频第一帧作为封面
- **飞书通知**: 任务状态变更及生成结果自动推送到飞书群 (支持交互式卡片)
- **异步处理**: 后台异步生成，不阻塞 API 响应

### 接口
`POST /api_trai/v1/ai/video/generations`

### 依赖
- `opencv-python-headless`: 用于视频帧提取
- GPU 显存: 建议 12GB+ (Wan2.1-T2V-1.3B)

## 🕷️ 网络爬虫 (Crawler)

本项目集成了 Scrapy 爬虫框架，用于采集网络公开信息。

### 快速开始

```bash
cd backend/app/crawler/news_crawler
# 默认抓取小米新闻
scrapy crawl keyword_news
# 自定义关键词抓取 (如华为)
scrapy crawl keyword_news -a keyword=Huawei
```

爬取结果将保存至同目录下的 `news_data.csv` 文件。

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
0. conda create -n trai_31014_whf_pro_20260202 python=3.10.14
    conda activate trai_31014_whf_pro_20260202
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
