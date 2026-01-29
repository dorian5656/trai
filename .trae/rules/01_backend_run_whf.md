# TRAI 后端启动说明
> **后端规则**: 本文件属于python3规范体系, 适用于所有后端开发人员.

## 1. 环境准备
- **环境**: Py `3.10.14`; Conda `trai_31014_whf`; Pip清华源.
- **命令**: `conda create -n trai_31014_whf python=3.10.14 -y && conda activate trai_31014_whf`
- **安装**: `pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple` (优先使用清华源或阿里源)

## 2. 启动与注意
- **端口清理**: 每次启动前，必须确保端口 (默认 5689) 未被占用。
  - **Windows**: `netstat -ano | findstr :5689` 查找 PID -> `taskkill /PID <PID> /F`。
  - **注意**: 若 `run.py` 报错端口占用，必须手动执行清理。
- **运行**: `python run.py --host 0.0.0.0 --port 5689` (需在conda环境).
- **Windows**: 禁`&&`; 路径用`pathlib`.
