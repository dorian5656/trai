import os
import subprocess
import shutil
from pathlib import Path

def build_exe():
    """
    使用 PyInstaller 打包客户端
    """
    base_dir = Path(__file__).parent
    dist_dir = base_dir / "dist"
    build_dir = base_dir / "build"
    
    # 清理旧文件
    if dist_dir.exists():
        shutil.rmtree(dist_dir)
    if build_dir.exists():
        shutil.rmtree(build_dir)
        
    print("Start packaging...")
    
    # PyInstaller 命令
    # --onefile: 单文件
    # --windowed: 无控制台窗口
    # --name: exe名称
    # --hidden-import: 隐式导入 markdown
    # --icon: 图标
    # --add-data: 资源文件
    cmd = [
        "pyinstaller",
        "--noconfirm",
        "--onefile",
        "--windowed",
        "--name", "TraeAI_Assistant",
        "--hidden-import", "markdown",
        str(base_dir / "main.py")
    ]
    
    # 检查图标是否存在
    icon_path = base_dir / "pppg.ico"
    if icon_path.exists():
        print(f"Adding icon: {icon_path}")
        cmd.extend(["--icon", str(icon_path)])
        # Windows 分隔符为 ;
        cmd.extend(["--add-data", f"{str(icon_path)};."])
    else:
        print(f"Warning: Icon file {icon_path} not found. Skipping icon.")
    
    subprocess.check_call(cmd, cwd=base_dir)
    
    print(f"Build success! EXE location: {dist_dir / 'TraeAI_Assistant.exe'}")

if __name__ == "__main__":
    build_exe()
