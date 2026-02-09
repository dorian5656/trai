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
from backend.app.utils.notify_utils import NotifyUtils
from backend.app.utils.upload_utils import UploadUtils

class DocFunc:
    """文档处理业务逻辑"""

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
                
                # 发送飞书通知 (使用 NotifyUtils)
                NotifyUtils.send_md_conversion_card(filename, pdf_url, duration)
                
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
                NotifyUtils.send_text(f"❌ 文档转换失败: {filename}\n错误: {str(e)}")
                raise HTTPException(status_code=500, detail=f"转换失败: {str(e)}")
