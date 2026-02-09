#!/usr/bin/env python
# -*- coding: utf-8 -*-

# 文件名：backend/app/utils/doc_utils.py
# 作者：liuhd
# 日期：2026-02-09 16:00:00
# 描述：文档处理工具类，提供文件格式转换等功能

import os
import re
import tempfile
import hashlib
import subprocess
import base64
import requests
import pypandoc
import shutil
import asyncio
from pathlib import Path
from loguru import logger
from backend.app.utils.upload_utils import UploadUtils
from backend.app.utils.pg_utils import PGUtils

class DocUtils:
    """文档处理工具类"""

    @staticmethod
    def _process_mermaid_diagrams(content: str, temp_dir: Path) -> str:
        """
        识别 Mermaid 代码块并转换为图片引用
        策略:
        1. 优先尝试本地 mmdc (Node.js) - 速度快，无需联网，无长度限制
           - 自动搜索 PATH 中的 mmdc 命令
        2. 降级使用 mermaid.ink (Python/Online) - 纯 Python 环境可用，需联网
        """
        # 非贪婪匹配 mermaid 代码块
        mermaid_pattern = re.compile(r'```mermaid(.*?)```', re.DOTALL)
        
        # 自动搜索 mmdc 可执行文件 (优先搜索 PATH)
        mmdc_path = shutil.which("mmdc")
        
        use_local_mmdc = mmdc_path is not None
        if not use_local_mmdc:
            logger.info("未在 PATH 中找到 mmdc，将使用 mermaid.ink 在线服务进行转换")
        else:
            logger.debug(f"使用本地 mmdc: {mmdc_path}")

        def replace_func(match):
            code = match.group(1).strip()
            if not code:
                return match.group(0)

            # 使用哈希生成唯一文件名
            code_hash = hashlib.md5(code.encode('utf-8')).hexdigest()
            png_file = temp_dir / f"{code_hash}.png"
            
            # 如果图片已存在，直接返回
            if png_file.exists():
                return f"![Mermaid Diagram]({png_file})"

            success = False
            
            # 策略1: 本地转换
            if use_local_mmdc:
                mmd_file = temp_dir / f"{code_hash}.mmd"
                try:
                    mmd_file.write_text(code, encoding='utf-8')
                    # --puppeteer-configFile 只有在需要自定义配置时才加，这里使用默认
                    # 只有在 root 用户且没有配置沙箱时可能需要 --no-sandbox，但全局安装通常能处理
                    # 为了兼容性，我们可以尝试传递 --no-sandbox 参数给 puppeteer
                    
                    # 构建 puppeteer 配置文件 (临时)
                    puppeteer_config = temp_dir / "puppeteer-config.json"
                    puppeteer_config.write_text('{"args": ["--no-sandbox"]}', encoding='utf-8')
                    
                    cmd = [
                        mmdc_path, 
                        "-i", str(mmd_file), 
                        "-o", str(png_file),
                        "-p", str(puppeteer_config),
                        "-b", "white"
                    ]

                    subprocess.run(cmd, check=True, capture_output=True)
                    logger.debug(f"本地 Mermaid 转换成功: {png_file}")
                    success = True
                except Exception as e:
                    logger.warning(f"本地 Mermaid 转换失败，尝试在线转换: {e}")
                    # 失败后继续尝试在线转换

            # 策略2: 在线转换 (如果本地不可用或失败)
            if not success:
                try:
                    # Mermaid.ink 需要 base64 编码
                    base64_str = base64.urlsafe_b64encode(code.encode("utf-8")).decode("utf-8")
                    url = f"https://mermaid.ink/img/{base64_str}?bgColor=FFFFFF"
                    
                    response = requests.get(url, timeout=30)
                    if response.status_code == 200:
                        png_file.write_bytes(response.content)
                        logger.debug(f"在线 Mermaid 转换成功: {png_file}")
                        success = True
                    else:
                        logger.error(f"在线 Mermaid 请求失败: {response.status_code}")
                except Exception as e:
                    logger.error(f"在线 Mermaid 转换异常: {e}")

            if success:
                return f"![Mermaid Diagram]({png_file})"
            else:
                return match.group(0) # 转换失败保留原样

        new_content = mermaid_pattern.sub(replace_func, content)
        return new_content

    @staticmethod
    async def md_to_pdf(input_path: str | Path, output_path: str | Path = None, user_id: str = None) -> str:
        """
        将 Markdown 文件转换为 PDF 文件 (使用 Pandoc + XeLaTeX + Mermaid CLI)
        并自动上传生成的图片和PDF到S3 (如果有配置)
        
        Args:
            input_path: 输入 Markdown 文件路径
            output_path: 输出 PDF 文件路径（可选，默认同名.pdf）
            user_id: 用户ID (用于归属记录)
            
        Returns:
            str: 生成的 PDF 文件的 URL (如果启用S3) 或 本地绝对路径
        """
        input_path = Path(input_path).resolve()
        if not input_path.exists():
            error_msg = f"文件不存在: {input_path}"
            logger.error(error_msg)
            raise FileNotFoundError(error_msg)
        
        if output_path is None:
            output_path = input_path.with_suffix('.pdf')
        else:
            output_path = Path(output_path).resolve()
        
        logger.info(f"开始转换 Markdown 到 PDF: {input_path} -> {output_path}")
        
        try:
            # 创建临时目录用于存放生成的 Mermaid 图片和临时 Markdown
            with tempfile.TemporaryDirectory() as temp_dir_str:
                temp_dir = Path(temp_dir_str)
                
                # 1. 读取原始内容
                original_content = input_path.read_text(encoding='utf-8')
                
                # 2. 预处理 Mermaid 图表
                processed_content = DocUtils._process_mermaid_diagrams(original_content, temp_dir)
                
                # NEW: 上传 Mermaid 图片到 S3 并记录
                # 遍历生成的 png
                for img_file in temp_dir.glob("*.png"):
                    try:
                        img_bytes = img_file.read_bytes()
                        # 上传
                        url, key, size = await UploadUtils.save_from_bytes(
                            img_bytes, 
                            img_file.name, 
                            module="mermaid", 
                            content_type="image/png"
                        )
                        # 记录 DB
                        if user_id: 
                            sql = """
                                INSERT INTO user_images (user_id, filename, s3_key, url, size, mime_type, module, source)
                                VALUES (:user_id, :filename, :s3_key, :url, :size, :mime_type, :module, :source)
                            """
                            params = {
                                "user_id": user_id,
                                "filename": img_file.name,
                                "s3_key": key,
                                "url": url,
                                "size": size,
                                "mime_type": "image/png",
                                "module": "mermaid",
                                "source": "generated"
                            }
                            await PGUtils.execute_update(sql, params)
                            logger.debug(f"Mermaid图片已归档: {url}")
                    except Exception as e:
                        logger.warning(f"Mermaid图片上传/记录失败: {e}")

                # 3. 写入临时 Markdown 文件
                # 保持文件名一致以便 pandoc 处理可能的其他相对引用
                temp_md = temp_dir / input_path.name
                temp_md.write_text(processed_content, encoding='utf-8')
                
                # 4. 配置 Pandoc 参数
                # 确保能找到相对于 Markdown 文件的图片资源
                input_dir = input_path.parent
                
                extra_args = [
                    '--pdf-engine=xelatex',
                    '-V', 'CJKmainfont=Droid Sans Fallback',
                    '-V', 'CJKmonofont=Droid Sans Fallback', # 避免 mono 字体缺失警告
                    '-V', 'geometry:margin=1cm',
                    '-V', 'geometry:landscape',  # 横向布局以适应宽表格
                    '--highlight-style=tango',   # 代码高亮风格
                    # 资源查找路径：临时目录(含Mermaid图片) + 原文件目录(含原图片) + 当前目录
                    f'--resource-path=.:{temp_dir}:{input_dir}' 
                ]
                
                pypandoc.convert_file(
                    str(temp_md),
                    'pdf',
                    outputfile=str(output_path),
                    extra_args=extra_args
                )
            
            logger.info(f"PDF 生成成功: {output_path}")
            
            # NEW: 上传 PDF 到 S3
            try:
                pdf_bytes = output_path.read_bytes()
                
                url, key, size = await UploadUtils.save_from_bytes(
                    pdf_bytes, 
                    output_path.name, 
                    module="docs", 
                    content_type="application/pdf"
                )
                
                # 记录 DB
                if user_id:
                    sql = """
                        INSERT INTO sys_files (user_id, filename, s3_key, url, size, mime_type, module)
                        VALUES (:user_id, :filename, :s3_key, :url, :size, :mime_type, :module)
                    """
                    params = {
                        "user_id": user_id,
                        "filename": output_path.name,
                        "s3_key": key,
                        "url": url,
                        "size": size,
                        "mime_type": "application/pdf",
                        "module": "docs"
                    }
                    await PGUtils.execute_update(sql, params)
                
                logger.info(f"PDF 已上传并归档: {url}")
                
                # 返回 URL
                return url
                
            except Exception as e:
                logger.error(f"PDF 上传/归档失败: {e}")
                # 如果上传失败，返回本地路径
                return str(output_path)
            
        except Exception as e:
            logger.error(f"转换 PDF 失败: {e}")
            raise

if __name__ == "__main__":
    # 测试代码
    async def main():
        try:
            test_file = Path("/home/code_dev/trai/CONDA_ENV_STATUS.md")
            if test_file.exists():
                print(f"正在转换: {test_file}")
                # 假设 user_id="system" 进行测试
                pdf_path = await DocUtils.md_to_pdf(test_file, user_id="system")
                print(f"转换成功: {pdf_path}")
            else:
                print(f"测试文件不存在: {test_file}")
        except Exception as e:
            print(f"转换出错: {e}")

    asyncio.run(main())
