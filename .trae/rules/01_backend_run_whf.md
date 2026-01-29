# TRAI 后端启动说明
> **后端规则**: 本文件属于python3规范体系, 适用于所有后端开发人员.

## 1. 环境准备
- **环境**: Py `3.10.14`; Conda `trai_31014_whf`; Pip清华源.
- **命令**: `conda create -n trai_31014_whf python=3.10.14 -y && conda activate trai_31014_whf`
- **安装**: `pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple` (优先使用清华源或阿里源)

## 2. 启动与注意
- **端口清理**: 每次启动前，必须确保端口 (优先读取 `.env` 中的 `ENV_PORT`, 如 5789) 未被占用。
  - **Windows**: `netstat -ano | findstr :<PORT>` (如 `:5789`) 查找 PID -> `taskkill /PID <PID> /F`。
  - **注意**: 若 `run.py` 报错端口占用，必须手动执行清理。
- **运行 (必须分步执行)**: 
  1. **激活环境**: `conda activate trai_31014_whf` (严禁使用 `conda run` 混合命令)
  2. **启动服务**: `python run.py --host 0.0.0.0` (自动读取 `.env` 配置的端口)
- **Windows**: 禁`&&`; 路径用`pathlib`.
