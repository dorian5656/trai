#!/usr/bin/env python
# -*- coding: utf-8 -*-
# 文件名：backend/app/routers/tools/doc/doc_func.py
# 作者：liuhd
# 日期：2026-02-09 10:30:00
# 描述：文档工具业务逻辑

import time
import shutil
import tempfile
from pathlib import Path
from fastapi import UploadFile, HTTPException
from backend.app.utils.logger import logger
from backend.app.utils.doc_utils import DocUtils
from backend.app.utils.feishu_utils import feishu_bot
from backend.app.utils.upload_utils import UploadUtils

class DocFunc:
    """文档处理业务逻辑"""

    @staticmethod
    async def _generic_convert(
        file: UploadFile, 
        allowed_exts: tuple, 
        convert_func: callable, 
        user_id: str, 
        success_msg_type: str = "转换成功"
    ) -> dict:
        start_time = time.time()
        filename = file.filename
        if not filename.lower().endswith(allowed_exts):
             raise HTTPException(status_code=400, detail=f"不支持的文件类型: {filename}. 仅支持 {allowed_exts}")

        with tempfile.TemporaryDirectory() as temp_dir_str:
            temp_dir = Path(temp_dir_str)
            input_path = temp_dir / filename
            try:
                content = await file.read()
                input_path.write_bytes(content)
            except Exception as e:
                logger.error(f"保存文件失败: {e}")
                raise HTTPException(status_code=500, detail="文件保存失败")

            try:
                result = await convert_func(input_path, user_id=user_id)
                duration = time.time() - start_time
                
                # result might be a list (images) or str (url)
                if isinstance(result, list):
                    feishu_bot.send_webhook_message(f"✅ {success_msg_type}: {filename}\n耗时: {duration:.2f}s\n数量: {len(result)}")
                    return {"code": 200, "msg": "OK", "data": {"urls": result, "duration": f"{duration:.2f}s"}}
                else:
                    # reusing card for convenience, title might be slightly off but acceptable
                    feishu_bot.send_md_conversion_card(filename, result, duration) 
                    return {"code": 200, "msg": "OK", "data": {"url": result, "filename": Path(result).name, "duration": f"{duration:.2f}s"}}
            except Exception as e:
                logger.error(f"转换失败: {e}")
                feishu_bot.send_webhook_message(f"❌ {success_msg_type}失败: {filename}\n错误: {str(e)}")
                raise HTTPException(status_code=500, detail=f"转换失败: {str(e)}")

    @staticmethod
    async def convert_image_to_pdf(file: UploadFile, user_id: str = "system") -> dict:
        return await DocFunc._generic_convert(file, ('.jpg', '.jpeg', '.png'), DocUtils.image_to_pdf, user_id, "图片转PDF")

    @staticmethod
    async def convert_excel_to_pdf(file: UploadFile, user_id: str = "system") -> dict:
        return await DocFunc._generic_convert(file, ('.xlsx', '.xls'), DocUtils.excel_to_pdf, user_id, "Excel转PDF")

    @staticmethod
    async def convert_ppt_to_pdf(file: UploadFile, user_id: str = "system") -> dict:
        return await DocFunc._generic_convert(file, ('.pptx', '.ppt'), DocUtils.ppt_to_pdf, user_id, "PPT转PDF")

    @staticmethod
    async def convert_html_to_pdf(file: UploadFile, user_id: str = "system") -> dict:
        return await DocFunc._generic_convert(file, ('.html', '.htm'), DocUtils.html_to_pdf, user_id, "HTML转PDF")

    @staticmethod
    async def convert_pdf_to_images(file: UploadFile, user_id: str = "system") -> dict:
        return await DocFunc._generic_convert(file, ('.pdf',), DocUtils.pdf_to_images, user_id, "PDF转图片")

    @staticmethod
    async def convert_pdf_to_word(file: UploadFile, user_id: str = "system") -> dict:
        return await DocFunc._generic_convert(file, ('.pdf',), DocUtils.pdf_to_word, user_id, "PDF转Word")

    @staticmethod
    async def convert_pdf_to_ppt(file: UploadFile, user_id: str = "system") -> dict:
        return await DocFunc._generic_convert(file, ('.pdf',), DocUtils.pdf_to_ppt, user_id, "PDF转PPT")
    
    @staticmethod
    async def convert_pdf_to_pdfa(file: UploadFile, user_id: str = "system") -> dict:
        return await DocFunc._generic_convert(file, ('.pdf',), DocUtils.pdf_to_pdfa, user_id, "PDF转PDF/A")

    @staticmethod
    async def convert_ofd_to_pdf(file: UploadFile, user_id: str = "system") -> dict:
        return await DocFunc._generic_convert(file, ('.ofd',), DocUtils.ofd_to_pdf, user_id, "OFD转PDF")

    @staticmethod
    async def convert_ofd_to_images(file: UploadFile, user_id: str = "system") -> dict:
        return await DocFunc._generic_convert(file, ('.ofd',), DocUtils.ofd_to_images, user_id, "OFD转图片")

    @staticmethod
    async def convert_pdf_unlock(file: UploadFile, user_id: str = "system") -> dict:
        return await DocFunc._generic_convert(file, ('.pdf',), DocUtils.pdf_remove_limit, user_id, "PDF移除限制")

    @staticmethod
    async def convert_pdf_to_long_image(file: UploadFile, user_id: str = "system") -> dict:
        return await DocFunc._generic_convert(file, ('.pdf',), DocUtils.pdf_to_long_image, user_id, "PDF转长图")

    @staticmethod
    async def convert_svg_to_pdf(file: UploadFile, user_id: str = "system") -> dict:
        return await DocFunc._generic_convert(file, ('.svg',), DocUtils.svg_to_pdf, user_id, "SVG转PDF")

    @staticmethod
    async def convert_image_format(file: UploadFile, target_fmt: str, user_id: str = "system") -> dict:
        # Wrapper for image_convert with target format
        async def _wrapper(input_path, user_id):
            return await DocUtils.image_convert(input_path, target_fmt, user_id=user_id)
        return await DocFunc._generic_convert(file, ('.jpg', '.jpeg', '.png', '.gif', '.bmp', '.tiff'), _wrapper, user_id, f"图片转{target_fmt.upper()}")

    @staticmethod
    async def convert_ebook(file: UploadFile, output_format: str, user_id: str = "system") -> dict:
        # Wrapper for ebook_convert
        async def _wrapper(input_path, user_id):
            return await DocUtils.ebook_convert(input_path, output_format, user_id=user_id)
        return await DocFunc._generic_convert(file, ('.epub', '.mobi', '.pdf', '.azw3', '.txt'), _wrapper, user_id, f"电子书转{output_format.upper()}")

    @staticmethod
    async def convert_md_to_pdf(file: UploadFile, user_id: str = "system") -> dict:
        """
        将上传的 Markdown 文件转换为 PDF
        :param file: 上传的文件
        :param user_id: 用户ID
        :return: 转换结果信息
        """
        start_time = time.time()
        filename = file.filename
        if not filename.endswith('.md'):
            raise HTTPException(status_code=400, detail="仅支持 .md 文件")

        # 创建临时目录处理文件
        with tempfile.TemporaryDirectory() as temp_dir_str:
            temp_dir = Path(temp_dir_str)
            input_path = temp_dir / filename
            
            # 保存上传的文件
            try:
                content = await file.read()
                input_path.write_bytes(content)
            except Exception as e:
                logger.error(f"保存上传文件失败: {e}")
                raise HTTPException(status_code=500, detail="文件保存失败")

            try:
                # 执行转换 (自动上传 S3 并记录 DB)
                pdf_url = await DocUtils.md_to_pdf(input_path, user_id=user_id)
                
                # 计算耗时
                duration = time.time() - start_time
                
                # 发送飞书通知 (使用 feishu_bot)
                feishu_bot.send_md_conversion_card(filename, pdf_url, duration)
                
                return {
                    "code": 200,
                    "msg": "转换成功",
                    "data": {
                        "url": pdf_url,
                        "filename": Path(pdf_url).name,
                        "duration": f"{duration:.2f}s"
                    }
                }
            except Exception as e:
                logger.error(f"转换失败: {e}")
                # 失败通知
                feishu_bot.send_webhook_message(f"❌ 文档转换失败: {filename}\n错误: {str(e)}")
                raise HTTPException(status_code=500, detail=f"转换失败: {str(e)}")

    @staticmethod
    async def convert_word_to_pdf(file: UploadFile, user_id: str = "system") -> dict:
        """
        将上传的 Word 文件转换为 PDF
        :param file: 上传的文件
        :param user_id: 用户ID
        :return: 转换结果信息
        """
        start_time = time.time()
        filename = file.filename
        if not filename.lower().endswith(('.docx', '.doc')):
            raise HTTPException(status_code=400, detail="仅支持 .docx/.doc 文件")

        # 创建临时目录处理文件
        with tempfile.TemporaryDirectory() as temp_dir_str:
            temp_dir = Path(temp_dir_str)
            input_path = temp_dir / filename
            
            # 保存上传的文件
            try:
                content = await file.read()
                input_path.write_bytes(content)
            except Exception as e:
                logger.error(f"保存上传文件失败: {e}")
                raise HTTPException(status_code=500, detail="文件保存失败")

            try:
                # 执行转换
                pdf_url = await DocUtils.word_to_pdf(input_path, user_id=user_id)
                
                # 计算耗时
                duration = time.time() - start_time
                
                # 发送飞书通知 (复用卡片)
                feishu_bot.send_md_conversion_card(filename, pdf_url, duration)
                
                return {
                    "code": 200,
                    "msg": "转换成功",
                    "data": {
                        "url": pdf_url,
                        "filename": Path(pdf_url).name,
                        "duration": f"{duration:.2f}s"
                    }
                }
            except Exception as e:
                logger.error(f"Word转换失败: {e}")
                # 失败通知
                feishu_bot.send_webhook_message(f"❌ Word文档转换失败: {filename}\n错误: {str(e)}")
                raise HTTPException(status_code=500, detail=f"转换失败: {str(e)}")
