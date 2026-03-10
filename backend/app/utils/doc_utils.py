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
import uuid
import requests
import pypandoc
import shutil
import asyncio
import json
import pandas as pd
from PIL import Image
from pdf2docx import Converter
from xhtml2pdf import pisa
import pypdfium2 as pdfium
import pikepdf
import easyofd
from svglib.svglib import svg2rlg
from reportlab.graphics import renderPDF
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.cidfonts import UnicodeCIDFont
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, A3, landscape
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import ParagraphStyle
from openpyxl import load_workbook
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
                    '-V', 'geometry:margin=1in'
                ]
                
                # 执行转换
                pypandoc.convert_file(
                    str(temp_md), 
                    'pdf', 
                    outputfile=str(output_path), 
                    extra_args=extra_args
                )
                
                if not output_path.exists():
                    raise Exception("PDF 生成失败 (无报错但文件未生成)")
                
                # 5. 上传最终 PDF 到 S3
                final_url = str(output_path) # 默认返回本地路径
                
                if user_id: # 只有关联用户时才上传
                    try:
                        file_bytes = output_path.read_bytes()
                        file_size = output_path.stat().st_size
                        
                        s3_key = f"docs/{user_id}/{output_path.name}"
                        url, key, size = await UploadUtils.save_from_bytes(
                            file_bytes,
                            output_path.name,
                            module="doc_convert",
                            content_type="application/pdf"
                        )
                        final_url = url
                        logger.info(f"PDF已上传S3: {url}")
                        
                        # 6. 记录到 user_docs 表
                        try:
                            insert_sql = """
                            INSERT INTO user_docs (
                                user_id, filename, s3_key, url, size, mime_type, module, source, meta_data, created_at
                            ) VALUES (
                                :user_id, :filename, :s3_key, :url, :size, :mime_type, :module, :source, :meta_data, NOW()
                            )
                            """
                            params = {
                                "user_id": user_id,
                                "filename": output_path.name,
                                "s3_key": key,
                                "url": url,
                                "size": size,
                                "mime_type": "application/pdf",
                                "module": "doc_convert",
                                "source": "converted",
                                "meta_data": json.dumps({"original_file": str(input_path.name), "type": "md2pdf"})
                            }
                            await PGUtils.execute_ddl(insert_sql, params)
                            logger.info(f"PDF记录已保存到DB: {output_path.name}")
                        except Exception as e:
                            logger.error(f"PDF记录保存DB失败: {e}")
                        
                    except Exception as e:
                        logger.error(f"PDF上传S3失败: {e}")
                        # 上传失败降级返回本地路径 (但在容器/无状态环境中可能无法访问)
                        
                return final_url
                
        except Exception as e:
            logger.error(f"Markdown 转 PDF 异常: {e}")
            raise e

    @staticmethod
    async def word_to_pdf(input_path: str | Path, output_path: str | Path = None, user_id: str = None) -> str:
        """
        将 Word (.docx) 文件转换为 PDF 文件 (使用 Pandoc + XeLaTeX)
        
        Args:
            input_path: 输入 .docx 文件路径
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
            
        logger.info(f"开始转换 Word 到 PDF: {input_path} -> {output_path}")
        
        try:
            # 配置 Pandoc 参数
            # 使用 xelatex 引擎以支持中文，需指定 CJK 字体
            # 优先使用 Noto Sans CJK SC，如果系统中已确认存在
            extra_args = [
                    '--pdf-engine=xelatex',
                    '-V', 'mainfont=DejaVu Sans',
                    '-V', 'CJKmainfont=Droid Sans Fallback',
                    '-V', 'CJKmonofont=Droid Sans Fallback',
                    '-V', 'geometry:margin=1in',
                    # 修复中文下划线导致的 soul package error
                    '-V', 'header-includes=\\usepackage[normalem]{ulem}\\let\\ul\\uline'
                ]
            
            # 由于 pypandoc.convert_file 是同步阻塞操作，
            # 在 async 函数中直接调用会阻塞事件循环。
            # 对于大文件，建议 run_in_executor。这里为简化直接调用。
            await asyncio.to_thread(
                pypandoc.convert_file,
                str(input_path),
                'pdf',
                outputfile=str(output_path),
                extra_args=extra_args
            )
            
            if not output_path.exists():
                raise Exception("PDF 生成失败 (无报错但文件未生成)")
                
            # 上传最终 PDF 到 S3
            final_url = str(output_path)
            
            if user_id:
                try:
                    file_bytes = output_path.read_bytes()
                    s3_key = f"docs/{user_id}/{output_path.name}"
                    url, key, size = await UploadUtils.save_from_bytes(
                        file_bytes,
                        output_path.name,
                        module="doc_convert",
                        content_type="application/pdf"
                    )
                    final_url = url
                    logger.info(f"PDF已上传S3: {url}")

                    # 记录到 user_docs 表
                    try:
                        insert_sql = """
                        INSERT INTO user_docs (
                            user_id, filename, s3_key, url, size, mime_type, module, source, meta_data, created_at
                        ) VALUES (
                            :user_id, :filename, :s3_key, :url, :size, :mime_type, :module, :source, :meta_data, NOW()
                        )
                        """
                        params = {
                            "user_id": user_id,
                            "filename": output_path.name,
                            "s3_key": key,
                            "url": url,
                            "size": size,
                            "mime_type": "application/pdf",
                            "module": "doc_convert",
                            "source": "converted",
                            "meta_data": json.dumps({"original_file": str(input_path.name), "type": "word2pdf"})
                        }
                        await PGUtils.execute_ddl(insert_sql, params)
                        logger.info(f"PDF记录已保存到DB: {output_path.name}")
                    except Exception as e:
                        logger.error(f"PDF记录保存DB失败: {e}")
                except Exception as e:
                    logger.error(f"PDF上传S3失败: {e}")
                    
            return final_url
            
        except Exception as e:
            logger.error(f"Word 转 PDF 异常: {e}")
            raise e

    @staticmethod
    async def _upload_and_record(file_path: Path, user_id: str, module: str, source: str, mime_type: str, meta_data: dict) -> str:
        """上传到 S3 并记录到数据库的辅助方法"""
        if not user_id:
            return str(file_path)
            
        try:
            file_bytes = file_path.read_bytes()
            size = file_path.stat().st_size
            # 修复 S3 Key 冲突问题 (添加 UUID)
            s3_key = f"docs/{user_id}/{uuid.uuid4()}_{file_path.name}"
            
            url, key, size = await UploadUtils.save_from_bytes(
                file_bytes,
                file_path.name,
                module=module,
                content_type=mime_type
            )
            
            insert_sql = """
            INSERT INTO user_docs (
                user_id, filename, s3_key, url, size, mime_type, module, source, meta_data, created_at
            ) VALUES (
                :user_id, :filename, :s3_key, :url, :size, :mime_type, :module, :source, :meta_data, NOW()
            )
            """
            params = {
                "user_id": user_id,
                "filename": file_path.name,
                "s3_key": key,
                "url": url,
                "size": size,
                "mime_type": mime_type,
                "module": module,
                "source": source,
                "meta_data": json.dumps(meta_data)
            }
            await PGUtils.execute_ddl(insert_sql, params)
            logger.info(f"文件已记录: {url}")
            return url
        except Exception as e:
            logger.error(f"上传/记录失败: {e}")
            return str(file_path)

    @staticmethod
    async def image_to_pdf(input_path: str | Path, output_path: str | Path = None, user_id: str = None) -> str:
        """将 JPG/PNG 图片转换为 PDF"""
        input_path = Path(input_path).resolve()
        if not input_path.exists():
            raise FileNotFoundError(f"文件未找到: {input_path}")
            
        if output_path is None:
            output_path = input_path.with_suffix('.pdf')
        
        try:
            image = Image.open(input_path)
            if image.mode != 'RGB':
                image = image.convert('RGB')
            
            await asyncio.to_thread(image.save, output_path, "PDF", resolution=100.0)
            
            return await DocUtils._upload_and_record(
                output_path, user_id, "doc_convert", "converted", "application/pdf", 
                {"original_file": input_path.name, "type": "img2pdf"}
            )
        except Exception as e:
            logger.error(f"图片转 PDF 失败: {e}")
            raise e

    @staticmethod
    async def ppt_to_pdf(input_path: str | Path, output_path: str | Path = None, user_id: str = None) -> str:
        """将 PPT/PPTX 转换为 PDF (需要 LibreOffice 或支持 pptx 的 Pandoc)"""
        input_path = Path(input_path).resolve()
        if not input_path.exists():
            raise FileNotFoundError(f"文件未找到: {input_path}")
            
        if output_path is None:
            output_path = input_path.with_suffix('.pdf')
            
        try:
            # 检查 LibreOffice (soffice)
            if shutil.which("soffice"):
                # 使用 LibreOffice 进行转换 (无头模式)
                out_dir = output_path.parent
                cmd = ["soffice", "--headless", "--convert-to", "pdf", "--outdir", str(out_dir), str(input_path)]
                await asyncio.to_thread(subprocess.run, cmd, check=True, capture_output=True)
                
                # LibreOffice 使用原始文件名加 .pdf，确保其与 output_path 匹配
                generated_pdf = input_path.with_suffix('.pdf')
                if generated_pdf != output_path and generated_pdf.exists():
                    generated_pdf.rename(output_path)
            
            # 检查支持 pptx 的 Pandoc
            elif "pptx" in pypandoc.get_pandoc_formats()[0]:
                 extra_args = ['--pdf-engine=xelatex', '-V', 'CJKmainfont=Droid Sans Fallback']
                 await asyncio.to_thread(pypandoc.convert_file, str(input_path), 'pdf', outputfile=str(output_path), extra_args=extra_args)
            
            else:
                 raise NotImplementedError("PPT 转 PDF 需要 LibreOffice (soffice) 或支持 pptx 输入的 Pandoc 版本。")

            if not output_path.exists():
                 raise Exception("PDF 生成失败 (文件未创建)")

            return await DocUtils._upload_and_record(
                output_path, user_id, "doc_convert", "converted", "application/pdf", 
                {"original_file": input_path.name, "type": "ppt2pdf"}
            )
        except Exception as e:
            logger.error(f"PPT 转 PDF 失败: {e}")
            raise e

    @staticmethod
    async def excel_to_pdf(input_path: str | Path, output_path: str | Path = None, user_id: str = None) -> str:
        """Excel 转 PDF (优先 LibreOffice，其次 Pandas -> HTML -> xhtml2pdf)"""
        input_path = Path(input_path).resolve()
        if not input_path.exists():
            raise FileNotFoundError(f"文件未找到: {input_path}")
            
        if output_path is None:
            output_path = input_path.with_suffix('.pdf')
            
        try:
            if shutil.which("soffice"):
                out_dir = output_path.parent
                cmd = ["soffice", "--headless", "--convert-to", "pdf", "--outdir", str(out_dir), str(input_path)]
                await asyncio.to_thread(subprocess.run, cmd, check=True, capture_output=True)

                generated_pdf = input_path.with_suffix('.pdf')
                if generated_pdf != output_path and generated_pdf.exists():
                    generated_pdf.rename(output_path)

                if not output_path.exists():
                    raise Exception("PDF 生成失败 (文件未创建)")
            else:
                try:
                    pdfmetrics.registerFont(UnicodeCIDFont("STSong-Light"))
                    font_family = "STSong-Light"
                except Exception:
                    font_family = "Helvetica"

                wb = load_workbook(input_path, data_only=True)
                ws = wb.active

                def normalize_cell(value: object) -> str:
                    if value is None:
                        return ""
                    s = str(value)
                    if s.lower() in {"nan", "none", "null"}:
                        return ""
                    s = s.replace("\r\n", "\n").replace("\r", "\n")
                    s = re.sub(r"[ \t]+", " ", s).strip()
                    return s

                max_row, max_col = ws.max_row, ws.max_column
                last_row = 0
                for r in range(1, max_row + 1):
                    row_vals = [normalize_cell(ws.cell(r, c).value) for c in range(1, max_col + 1)]
                    if any(row_vals):
                        last_row = r
                last_col = 0
                for c in range(1, max_col + 1):
                    col_vals = [normalize_cell(ws.cell(r, c).value) for r in range(1, max_row + 1)]
                    if any(col_vals):
                        last_col = c
                if last_row == 0 or last_col == 0:
                    raise Exception("Excel 内容为空")

                rows = []
                for r in range(1, last_row + 1):
                    row_vals = [normalize_cell(ws.cell(r, c).value) for c in range(1, last_col + 1)]
                    rows.append(row_vals)

                non_empty_cols = [i for i in range(len(rows[0])) if any(row[i] for row in rows)]
                rows = [[row[i] for i in non_empty_cols] for row in rows]
                rows = [row for row in rows if any(cell for cell in row)]

                title_text = ""
                if rows:
                    first_row_non_empty = [c for c in rows[0] if c]
                    if len(first_row_non_empty) == 1:
                        title_text = first_row_non_empty[0]
                        rows = rows[1:]

                if not rows:
                    raise Exception("Excel 内容为空")

                header_row = rows[0]
                data_rows = rows[1:]

                def wrap_text(value: str) -> str:
                    if not value:
                        return ""
                    text = value.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
                    text = text.replace("\n", "<br/>")
                    return text

                row_count = len(data_rows) + 1
                col_count = len(header_row)

                col_lengths = []
                sample_rows = rows[:200]
                for col_idx in range(len(header_row)):
                    max_len = 1
                    for row in sample_rows:
                        max_len = max(max_len, len(row[col_idx]))
                    col_lengths.append(max_len)

                def compute_col_widths(font_size: float) -> list[float]:
                    widths = []
                    per_char = font_size * 0.62
                    for length in col_lengths:
                        width = min(max(36.0, length * per_char + 12.0), 280.0)
                        widths.append(width)
                    return widths

                def pick_layout() -> tuple[float, object, float, int, int, list[float]]:
                    font_sizes = [9.0, 8.5, 8.0, 7.5, 7.0, 6.5]
                    if col_count >= 8:
                        size_order = [landscape(A3), landscape(A4), A3, A4]
                    elif row_count >= 45:
                        size_order = [A3, landscape(A3), A4, landscape(A4)]
                    else:
                        size_order = [landscape(A4), A4, landscape(A3), A3]

                    for page_size in size_order:
                        for font_size in font_sizes:
                            margin = max(10, round(font_size * 1.9))
                            if row_count >= 45:
                                margin = max(10, margin - 2)
                            doc = SimpleDocTemplate(
                                str(output_path),
                                pagesize=page_size,
                                leftMargin=margin,
                                rightMargin=margin,
                                topMargin=margin,
                                bottomMargin=margin,
                            )
                            col_widths = compute_col_widths(font_size)
                            available_width = doc.width
                            total_width = sum(col_widths)
                            if total_width > available_width:
                                scale = available_width / total_width
                                col_widths = [w * scale for w in col_widths]
                            elif total_width < available_width * 0.85:
                                scale = (available_width * 0.95) / total_width
                                col_widths = [w * scale for w in col_widths]

                            pad_lr = max(3, round(font_size * 0.6))
                            pad_tb = max(2, round(font_size * 0.45))
                            row_height = font_size * 1.35 + pad_tb * 2
                            title_height = font_size * 1.3 + 10 if title_text else 0
                            needed_height = row_count * row_height + title_height + 12
                            if needed_height <= doc.height:
                                return font_size, page_size, margin, pad_lr, pad_tb, col_widths

                    font_size = 6.5
                    page_size = landscape(A3) if col_count >= 8 else A3
                    margin = 10
                    pad_lr = 3
                    pad_tb = 2
                    col_widths = compute_col_widths(font_size)
                    return font_size, page_size, margin, pad_lr, pad_tb, col_widths

                base_font_size, page_size, margin, pad_lr, pad_tb, col_widths = pick_layout()
                body_style = ParagraphStyle(
                    "body",
                    fontName=font_family,
                    fontSize=base_font_size,
                    leading=base_font_size * 1.35,
                )
                header_style = ParagraphStyle(
                    "header",
                    fontName=font_family,
                    fontSize=base_font_size,
                    leading=base_font_size * 1.35,
                )
                title_style = ParagraphStyle(
                    "title",
                    fontName=font_family,
                    fontSize=base_font_size + 3,
                    leading=(base_font_size + 3) * 1.3,
                    alignment=1,
                    spaceAfter=6,
                )

                table_data = []
                table_data.append([Paragraph(wrap_text(c), header_style) for c in header_row])
                for row in data_rows:
                    table_data.append([Paragraph(wrap_text(c), body_style) for c in row])

                doc = SimpleDocTemplate(
                    str(output_path),
                    pagesize=page_size,
                    leftMargin=margin,
                    rightMargin=margin,
                    topMargin=margin,
                    bottomMargin=margin,
                )
                available_width = doc.width
                total_width = sum(col_widths)
                if total_width > available_width:
                    scale = available_width / total_width
                    col_widths = [w * scale for w in col_widths]
                elif total_width < available_width * 0.85:
                    scale = (available_width * 0.95) / total_width
                    col_widths = [w * scale for w in col_widths]

                table = Table(table_data, colWidths=col_widths, repeatRows=1)
                table.setStyle(
                    TableStyle(
                        [
                            ("GRID", (0, 0), (-1, -1), 0.6, colors.black),
                            ("VALIGN", (0, 0), (-1, -1), "TOP"),
                            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#f2f2f2")),
                            ("LEFTPADDING", (0, 0), (-1, -1), pad_lr),
                            ("RIGHTPADDING", (0, 0), (-1, -1), pad_lr),
                            ("TOPPADDING", (0, 0), (-1, -1), pad_tb),
                            ("BOTTOMPADDING", (0, 0), (-1, -1), pad_tb),
                        ]
                    )
                )

                elements = []
                if title_text:
                    elements.append(Paragraph(wrap_text(title_text), title_style))
                elements.append(Spacer(1, 6))
                elements.append(table)
                await asyncio.to_thread(doc.build, elements)
                
            return await DocUtils._upload_and_record(
                output_path, user_id, "doc_convert", "converted", "application/pdf", 
                {"original_file": input_path.name, "type": "excel2pdf"}
            )
        except Exception as e:
            logger.error(f"Excel 转 PDF 失败: {e}")
            raise e

    @staticmethod
    async def html_to_pdf(input_path: str | Path, output_path: str | Path = None, user_id: str = None) -> str:
        """HTML 文件转 PDF"""
        input_path = Path(input_path).resolve()
        if not input_path.exists():
            raise FileNotFoundError(f"文件未找到: {input_path}")
            
        if output_path is None:
            output_path = input_path.with_suffix('.pdf')
            
        try:
            html_content = input_path.read_text(encoding='utf-8')
            with open(output_path, "wb") as f:
                await asyncio.to_thread(pisa.CreatePDF, html_content, dest=f)
                
            return await DocUtils._upload_and_record(
                output_path, user_id, "doc_convert", "converted", "application/pdf", 
                {"original_file": input_path.name, "type": "html2pdf"}
            )
        except Exception as e:
            logger.error(f"HTML 转 PDF 失败: {e}")
            raise e

    @staticmethod
    async def pdf_to_images(input_path: str | Path, output_dir: str | Path = None, user_id: str = None) -> list[str]:
        """PDF 转图片 (返回图片 URL/路径列表)"""
        input_path = Path(input_path).resolve()
        if not input_path.exists():
            raise FileNotFoundError(f"文件未找到: {input_path}")
            
        if output_dir is None:
            output_dir = input_path.parent / f"{input_path.stem}_{uuid.uuid4()}_images"
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
            
        try:
            pdf = pdfium.PdfDocument(str(input_path))
            results = []
            
            for i in range(len(pdf)):
                page = pdf[i]
                image = page.render(scale=2).to_pil()
                image_path = output_dir / f"page_{i+1}.jpg"
                image.save(image_path, "JPEG")
                
                url = await DocUtils._upload_and_record(
                    image_path, user_id, "doc_convert", "converted", "image/jpeg", 
                    {"original_file": input_path.name, "type": "pdf2img", "page": i+1}
                )
                results.append(url)
                
            return results
        except Exception as e:
            logger.error(f"PDF 转图片失败: {e}")
            raise e

    @staticmethod
    async def pdf_to_word(input_path: str | Path, output_path: str | Path = None, user_id: str = None) -> str:
        """PDF 转 Word (.docx)"""
        input_path = Path(input_path).resolve()
        if not input_path.exists():
            raise FileNotFoundError(f"文件未找到: {input_path}")
            
        if output_path is None:
            output_path = input_path.with_suffix('.docx')
            
        try:
            cv = Converter(str(input_path))
            await asyncio.to_thread(cv.convert, str(output_path), start=0, end=None)
            cv.close()
            
            return await DocUtils._upload_and_record(
                output_path, user_id, "doc_convert", "converted", "application/vnd.openxmlformats-officedocument.wordprocessingml.document", 
                {"original_file": input_path.name, "type": "pdf2word"}
            )
        except Exception as e:
            logger.error(f"PDF 转 Word 失败: {e}")
            raise e

    @staticmethod
    async def pdf_to_ppt(input_path: str | Path, output_path: str | Path = None, user_id: str = None) -> str:
        """PDF 转 PPT (通过 PDF->Word->Pandoc)"""
        input_path = Path(input_path).resolve()
        if not input_path.exists():
            raise FileNotFoundError(f"文件未找到: {input_path}")
            
        if output_path is None:
            output_path = input_path.with_suffix('.pptx')
            
        try:
            # 第一步: PDF -> Word
            temp_docx = input_path.with_suffix('.temp.docx')
            cv = Converter(str(input_path))
            await asyncio.to_thread(cv.convert, str(temp_docx), start=0, end=None)
            cv.close()
            
            # 第二步: Word -> PPTX (Pandoc)
            await asyncio.to_thread(pypandoc.convert_file, str(temp_docx), 'pptx', outputfile=str(output_path))
            
            # 清理
            if temp_docx.exists():
                temp_docx.unlink()
                
            return await DocUtils._upload_and_record(
                output_path, user_id, "doc_convert", "converted", "application/vnd.openxmlformats-officedocument.presentationml.presentation", 
                {"original_file": input_path.name, "type": "pdf2ppt"}
            )
        except Exception as e:
            logger.error(f"PDF 转 PPT 失败: {e}")
            raise e

    @staticmethod
    async def pdf_to_excel(input_path: str | Path, output_path: str | Path = None, user_id: str = None) -> str:
        """PDF 转 Excel (占位符 / 基础提取)"""
        # 注意: 完整的 PDF 转 Excel 需要 tabula-py 或 camelot，这些库有较重的依赖 (java 等)
        # 这里我们提供一个存根或基础实现，否则我们可能会跳过或抛出不支持
        # 既然用户要求，我们尝试使用 pdf2docx 获取表格？不，pdf2docx 针对 docx。
        # 目前，我们将抛出 NotImplementedError 或提供一个虚拟文件以指示限制。
        # 或者，我们可以使用 `pypdf` 提取文本并转储到 CSV？
        raise NotImplementedError("PDF 转 Excel 需要当前不可用的专用库 (tabula-py)。")

    @staticmethod
    async def pdf_to_pdfa(input_path: str | Path, output_path: str | Path = None, user_id: str = None) -> str:
        """PDF 转 PDF/A (通过 Ghostscript)"""
        input_path = Path(input_path).resolve()
        if not input_path.exists():
            raise FileNotFoundError(f"文件未找到: {input_path}")
            
        if output_path is None:
            output_path = input_path.with_name(f"{input_path.stem}_pdfa.pdf")
            
        try:
            # 用于 PDF/A-1b 的 Ghostscript 命令
            cmd = [
                "gs",
                "-dPDFA",
                "-dBATCH",
                "-dNOPAUSE",
                "-sProcessColorModel=DeviceCMYK",
                "-sDEVICE=pdfwrite",
                "-sPDFACompatibilityPolicy=1",
                f"-sOutputFile={str(output_path)}",
                str(input_path)
            ]
            
            # 检查 gs 是否存在
            if not shutil.which("gs"):
                raise Exception("未找到 Ghostscript (gs)")
                
            await asyncio.to_thread(subprocess.run, cmd, check=True, capture_output=True)
            
            return await DocUtils._upload_and_record(
                output_path, user_id, "doc_convert", "converted", "application/pdf", 
                {"original_file": input_path.name, "type": "pdf2pdfa"}
            )
        except Exception as e:
            logger.error(f"PDF 转 PDF/A 失败: {e}")
            raise e

    @staticmethod
    async def ofd_to_pdf(input_path: str | Path, output_path: str | Path = None, user_id: str = None) -> str:
        """OFD 转 PDF (通过 easyofd)"""
        input_path = Path(input_path).resolve()
        if not input_path.exists():
            raise FileNotFoundError(f"文件未找到: {input_path}")
            
        if output_path is None:
            output_path = input_path.with_suffix('.pdf')
            
        try:
            # easyofd 转换
            # easyofd.OFD(str(input_path)).del_img() # 示例用法
            # easyofd.OFD(str(input_path)).save(str(output_path), format='pdf') 
            # 注意: easyofd API 可能会有所不同，假设标准用法或如果 CLI 可用则回退到子进程
            # 当前 easyofd (0.5.6) 支持基本提取。
            # 让我们尝试直接使用。如果失败，捕获异常。
            
            await asyncio.to_thread(
                lambda: easyofd.OFD(str(input_path)).save(str(output_path), format='pdf')
            )
            
            return await DocUtils._upload_and_record(
                output_path, user_id, "doc_convert", "converted", "application/pdf", 
                {"original_file": input_path.name, "type": "ofd2pdf"}
            )
        except Exception as e:
            logger.error(f"OFD 转 PDF 失败: {e}")
            raise e

    @staticmethod
    async def ofd_to_images(input_path: str | Path, output_dir: str | Path = None, user_id: str = None) -> list[str]:
        """OFD 转图片"""
        input_path = Path(input_path).resolve()
        if not input_path.exists():
            raise FileNotFoundError(f"文件未找到: {input_path}")
            
        if output_dir is None:
            output_dir = input_path.parent / f"{input_path.stem}_ofd_images"
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
            
        try:
            # easyofd 可以保存为图片
            await asyncio.to_thread(
                lambda: easyofd.OFD(str(input_path)).save(str(output_dir), format='jpg')
            )
            
            results = []
            for img_file in output_dir.glob("*.jpg"):
                 url = await DocUtils._upload_and_record(
                     img_file, user_id, "doc_convert", "converted", "image/jpeg", 
                     {"original_file": input_path.name, "type": "ofd2img"}
                 )
                 results.append(url)
            return results
        except Exception as e:
            logger.error(f"OFD 转图片失败: {e}")
            raise e

    @staticmethod
    async def pdf_remove_limit(input_path: str | Path, output_path: str | Path = None, user_id: str = None) -> str:
        """PDF 移除限制 (权限) (通过 pikepdf)"""
        input_path = Path(input_path).resolve()
        if not input_path.exists():
            raise FileNotFoundError(f"文件未找到: {input_path}")
            
        if output_path is None:
            output_path = input_path.with_name(f"{input_path.stem}_{uuid.uuid4()}_unlocked.pdf")
            
        try:
            def _unlock():
                with pikepdf.open(input_path) as pdf:
                    pdf.save(output_path)
            
            await asyncio.to_thread(_unlock)
            
            return await DocUtils._upload_and_record(
                output_path, user_id, "doc_convert", "converted", "application/pdf", 
                {"original_file": input_path.name, "type": "pdf_unlock"}
            )
        except Exception as e:
            logger.error(f"PDF 解锁失败: {e}")
            raise e

    @staticmethod
    async def pdf_to_long_image(input_path: str | Path, output_path: str | Path = None, user_id: str = None) -> str:
        """PDF 转长图 (拼接)"""
        input_path = Path(input_path).resolve()
        if not input_path.exists():
            raise FileNotFoundError(f"文件未找到: {input_path}")
            
        if output_path is None:
            output_path = input_path.with_suffix('.jpg')
            
        try:
            # 1. 首先转换为图片
            pdf = pdfium.PdfDocument(str(input_path))
            images = []
            total_height = 0
            max_width = 0
            
            for i in range(len(pdf)):
                page = pdf[i]
                img = page.render(scale=2).to_pil()
                images.append(img)
                total_height += img.height
                max_width = max(max_width, img.width)
                
            # 2. 拼接
            long_img = Image.new('RGB', (max_width, total_height), (255, 255, 255))
            y_offset = 0
            for img in images:
                long_img.paste(img, (0, y_offset))
                y_offset += img.height
                
            await asyncio.to_thread(long_img.save, output_path, "JPEG", quality=85)
            
            return await DocUtils._upload_and_record(
                output_path, user_id, "doc_convert", "converted", "image/jpeg", 
                {"original_file": input_path.name, "type": "pdf2longimg"}
            )
        except Exception as e:
            logger.error(f"PDF 转长图失败: {e}")
            raise e

    @staticmethod
    async def image_convert(input_path: str | Path, target_fmt: str = "png", output_path: str | Path = None, user_id: str = None) -> str:
        """图片格式转换 (JPG<->PNG 等)"""
        input_path = Path(input_path).resolve()
        if not input_path.exists():
            raise FileNotFoundError(f"文件未找到: {input_path}")
            
        target_fmt = target_fmt.lower().replace('.', '')
        if output_path is None:
            output_path = input_path.with_suffix(f'.{target_fmt}')
            
        try:
            img = Image.open(input_path)
            # 处理 JPG 的 alpha 通道
            if target_fmt in ['jpg', 'jpeg'] and img.mode in ('RGBA', 'LA'):
                background = Image.new(img.mode[:-1], img.size, (255, 255, 255))
                background.paste(img, img.split()[-1])
                img = background
                
            rgb_im = img.convert('RGB') if target_fmt in ['jpg', 'jpeg'] else img
            await asyncio.to_thread(rgb_im.save, output_path)
            
            mime_map = {'jpg': 'image/jpeg', 'jpeg': 'image/jpeg', 'png': 'image/png', 'gif': 'image/gif'}
            return await DocUtils._upload_and_record(
                output_path, user_id, "doc_convert", "converted", mime_map.get(target_fmt, 'application/octet-stream'), 
                {"original_file": input_path.name, "type": f"img2{target_fmt}"}
            )
        except Exception as e:
            logger.error(f"图片转换失败: {e}")
            raise e

    @staticmethod
    async def svg_to_pdf(input_path: str | Path, output_path: str | Path = None, user_id: str = None) -> str:
        """SVG 转 PDF (通过 svglib)"""
        input_path = Path(input_path).resolve()
        if not input_path.exists():
            raise FileNotFoundError(f"文件未找到: {input_path}")
            
        if output_path is None:
            output_path = input_path.with_suffix('.pdf')
            
        try:
            drawing = svg2rlg(str(input_path))
            await asyncio.to_thread(renderPDF.drawToFile, drawing, str(output_path))
            
            return await DocUtils._upload_and_record(
                output_path, user_id, "doc_convert", "converted", "application/pdf", 
                {"original_file": input_path.name, "type": "svg2pdf"}
            )
        except Exception as e:
            logger.error(f"SVG 转 PDF 失败: {e}")
            raise e

    @staticmethod
    async def ebook_convert(input_path: str | Path, output_format: str, user_id: str = None) -> str:
        """电子书转换 (EPUB/MOBI/PDF 通过 Pandoc)"""
        input_path = Path(input_path).resolve()
        if not input_path.exists():
            raise FileNotFoundError(f"文件未找到: {input_path}")
            
        output_format = output_format.lower().replace('.', '')
        output_path = input_path.with_suffix(f'.{output_format}')
        
        try:
            # Pandoc 处理 epub, markdown, docx 等。
            # 注意: mobi 不是标准的 pandoc 输出 (需要 kindlegen)，但 'epub' 是。
            # 我们将首先尝试 pandoc。
            await asyncio.to_thread(pypandoc.convert_file, str(input_path), output_format, outputfile=str(output_path))
            
            return await DocUtils._upload_and_record(
                output_path, user_id, "doc_convert", "converted", "application/octet-stream", 
                {"original_file": input_path.name, "type": f"ebook2{output_format}"}
            )
        except Exception as e:
            logger.error(f"电子书转换失败: {e}")
            raise e

    @staticmethod
    async def caj_to_pdf(input_path: str | Path, output_path: str | Path = None, user_id: str = None) -> str:
        """CAJ 转 PDF (存根/占位符)"""
        # 需要外部 caj2pdf 工具，在此环境中不容易通过 pip 安装
        raise NotImplementedError("CAJ 转 PDF 需要外部 'caj2pdf' 工具。")

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
