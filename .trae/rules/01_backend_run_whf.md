# TRAI 后端启动说明
> **后端规则**: 本文件属于python3规范体系, 适用于所有后端开发人员.

## 1. 环境准备
- **环境**: Py `3.10.14`; Conda `trai_31014_whf_pro_20260202`; Pip清华源.
- **命令**: `conda create -n trai_31014_whf_pro_20260202 python=3.10.14 -y && conda activate trai_31014_whf_pro_20260202`
- **安装**: `pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple` (优先使用清华源或阿里源)

## 2. 启动与注意

- **端口清理**: 每次启动前，脚本会**自动检测并清理**端口 (优先读取 `.env` 中的 `ENV_PORT`, 如 5789)。
  - **机制**: `run.py` 启动时调用 `NetUtils.check_and_release_port`，若端口占用则尝试自动 Kill 进程 (支持 Win/Linux/Mac)。
  - **注意**: 若自动清理失败，请手动检查权限或残留进程。
- **运行 (必须分步执行)**: 
  1. **激活环境**: `conda activate trai_31014_whf_pro_20260202` (严禁使用 `conda run` 混合命令)
  2. **启动服务**: `python run.py --host 0.0.0.0` (自动读取 `.env` 配置的端口)
- **Windows**: 禁`&&`; 路径用`pathlib`.
