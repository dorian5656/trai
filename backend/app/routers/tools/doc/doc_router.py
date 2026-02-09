#!/usr/bin/env python
# -*- coding: utf-8 -*-
# 文件名：backend/app/routers/tools/doc/doc_router.py
# 作者：liuhd
# 日期：2026-02-09 10:35:00
# 描述：文档工具路由定义

from fastapi import APIRouter, UploadFile, File, Form, Depends
from backend.app.routers.tools.doc.doc_func import DocFunc
from backend.app.utils.dependencies import get_current_active_user

router = APIRouter()

@router.post("/md2pdf", summary="Markdown 转 PDF", description="上传 Markdown 文件，转换为 PDF 并返回下载链接")
async def convert_md_to_pdf(
    file: UploadFile = File(..., description="Markdown 文件 (.md)"),
    current_user = Depends(get_current_active_user)
):
    """
    Markdown 转 PDF 接口
    - 自动处理 Mermaid 图表
    - 上传结果到 S3
    - 发送飞书通知
    """
    # 使用当前登录用户的 username 作为 user_id
    user_id = current_user.username if hasattr(current_user, 'username') else "system"
    return await DocFunc.convert_md_to_pdf(file, user_id=user_id)

@router.post("/word2pdf", summary="Word 转 PDF", description="上传 Word 文件 (.docx/.doc)，转换为 PDF 并返回下载链接")
async def convert_word_to_pdf(
    file: UploadFile = File(..., description="Word 文件 (.docx/.doc)"),
    current_user = Depends(get_current_active_user)
):
    """
    Word 转 PDF 接口
    - 支持 .docx/.doc
    - 上传结果到 S3
    - 记录到数据库
    - 发送飞书通知
    """
    # 使用当前登录用户的 username 作为 user_id
    user_id = current_user.username if hasattr(current_user, 'username') else "system"
    return await DocFunc.convert_word_to_pdf(file, user_id=user_id)

@router.post("/img2pdf", summary="图片转 PDF", description="上传图片(JPG/PNG)，转换为 PDF")
async def convert_image_to_pdf(
    file: UploadFile = File(..., description="图片文件 (JPG/PNG)"),
    current_user = Depends(get_current_active_user)
):
    """
    图片转 PDF 接口
    - 支持 JPG, PNG 等常见格式
    - 自动调整尺寸与颜色模式
    """
    user_id = current_user.username if hasattr(current_user, 'username') else "system"
    return await DocFunc.convert_image_to_pdf(file, user_id=user_id)

@router.post("/excel2pdf", summary="Excel转 PDF", description="上传Excel，转换为 PDF")
async def convert_excel_to_pdf(
    file: UploadFile = File(..., description="Excel 文件 (.xlsx/.xls)"),
    current_user = Depends(get_current_active_user)
):
    """
    Excel 转 PDF 接口
    - 支持 .xlsx, .xls
    - 保持表格格式
    """
    user_id = current_user.username if hasattr(current_user, 'username') else "system"
    return await DocFunc.convert_excel_to_pdf(file, user_id=user_id)

@router.post("/ppt2pdf", summary="PPT转 PDF", description="上传PPT，转换为 PDF")
async def convert_ppt_to_pdf(
    file: UploadFile = File(..., description="PPT 文件 (.pptx/.ppt)"),
    current_user = Depends(get_current_active_user)
):
    """
    PPT 转 PDF 接口
    - 支持 .pptx, .ppt
    - 依赖 LibreOffice 或 Pandoc
    """
    user_id = current_user.username if hasattr(current_user, 'username') else "system"
    return await DocFunc.convert_ppt_to_pdf(file, user_id=user_id)

@router.post("/html2pdf", summary="HTML转 PDF", description="上传HTML，转换为 PDF")
async def convert_html_to_pdf(
    file: UploadFile = File(..., description="HTML 文件 (.html/.htm)"),
    current_user = Depends(get_current_active_user)
):
    """
    HTML 转 PDF 接口
    - 支持标准 HTML5
    - 自动渲染样式
    """
    user_id = current_user.username if hasattr(current_user, 'username') else "system"
    return await DocFunc.convert_html_to_pdf(file, user_id=user_id)

@router.post("/pdf2img", summary="PDF转图片", description="上传PDF，转换为图片列表")
async def convert_pdf_to_images(
    file: UploadFile = File(..., description="PDF 文件"),
    current_user = Depends(get_current_active_user)
):
    """
    PDF 转图片接口
    - 将每一页转换为 JPG 图片
    - 返回图片 URL 列表
    """
    user_id = current_user.username if hasattr(current_user, 'username') else "system"
    return await DocFunc.convert_pdf_to_images(file, user_id=user_id)

@router.post("/pdf2word", summary="PDF转Word", description="上传PDF，转换为Word")
async def convert_pdf_to_word(
    file: UploadFile = File(..., description="PDF 文件"),
    current_user = Depends(get_current_active_user)
):
    """
    PDF 转 Word 接口
    - 转换为可编辑的 .docx 文件
    - 尽量保持排版
    """
    user_id = current_user.username if hasattr(current_user, 'username') else "system"
    return await DocFunc.convert_pdf_to_word(file, user_id=user_id)

@router.post("/pdf2ppt", summary="PDF转PPT", description="上传PDF，转换为PPT")
async def convert_pdf_to_ppt(
    file: UploadFile = File(..., description="PDF 文件"),
    current_user = Depends(get_current_active_user)
):
    """
    PDF 转 PPT 接口
    - 转换为演示文稿 .pptx
    """
    user_id = current_user.username if hasattr(current_user, 'username') else "system"
    return await DocFunc.convert_pdf_to_ppt(file, user_id=user_id)

@router.post("/pdf2pdfa", summary="PDF转PDF/A", description="上传PDF，转换为PDF/A")
async def convert_pdf_to_pdfa(
    file: UploadFile = File(..., description="PDF 文件"),
    current_user = Depends(get_current_active_user)
):
    """
    PDF 转 PDF/A 接口
    - 用于长期归档的标准格式 (PDF/A-1b)
    """
    user_id = current_user.username if hasattr(current_user, 'username') else "system"
    return await DocFunc.convert_pdf_to_pdfa(file, user_id=user_id)

@router.post("/ofd2pdf", summary="OFD转PDF", description="上传OFD，转换为PDF")
async def convert_ofd_to_pdf(
    file: UploadFile = File(..., description="OFD 文件"),
    current_user = Depends(get_current_active_user)
):
    """
    OFD 转 PDF 接口
    - 支持国产版式文档 OFD 格式
    """
    user_id = current_user.username if hasattr(current_user, 'username') else "system"
    return await DocFunc.convert_ofd_to_pdf(file, user_id=user_id)

@router.post("/ofd2img", summary="OFD转图片", description="上传OFD，转换为图片列表")
async def convert_ofd_to_images(
    file: UploadFile = File(..., description="OFD 文件"),
    current_user = Depends(get_current_active_user)
):
    """
    OFD 转图片接口
    - 将 OFD 页面转换为图片
    """
    user_id = current_user.username if hasattr(current_user, 'username') else "system"
    return await DocFunc.convert_ofd_to_images(file, user_id=user_id)

@router.post("/pdf_unlock", summary="PDF移除限制", description="上传PDF，移除编辑限制")
async def convert_pdf_unlock(
    file: UploadFile = File(..., description="受限 PDF 文件"),
    current_user = Depends(get_current_active_user)
):
    """
    PDF 移除限制接口
    - 移除打印、复制等权限限制
    """
    user_id = current_user.username if hasattr(current_user, 'username') else "system"
    return await DocFunc.convert_pdf_unlock(file, user_id=user_id)

@router.post("/pdf2longimg", summary="PDF转长图", description="上传PDF，转换为单张长图")
async def convert_pdf_to_long_image(
    file: UploadFile = File(..., description="PDF 文件"),
    current_user = Depends(get_current_active_user)
):
    """
    PDF 转长图接口
    - 将所有页面拼接为一张长图片
    """
    user_id = current_user.username if hasattr(current_user, 'username') else "system"
    return await DocFunc.convert_pdf_to_long_image(file, user_id=user_id)

@router.post("/svg2pdf", summary="SVG转PDF", description="上传SVG，转换为PDF")
async def convert_svg_to_pdf(
    file: UploadFile = File(..., description="SVG 文件"),
    current_user = Depends(get_current_active_user)
):
    """
    SVG 转 PDF 接口
    - 矢量图转换
    """
    user_id = current_user.username if hasattr(current_user, 'username') else "system"
    return await DocFunc.convert_svg_to_pdf(file, user_id=user_id)

@router.post("/img_convert", summary="图片格式转换", description="支持 jpg/png/gif/bmp/tiff 互转")
async def convert_image_format(
    target_fmt: str = Form(..., description="目标格式 (png, jpg, gif 等)"),
    file: UploadFile = File(..., description="源图片文件"), 
    current_user = Depends(get_current_active_user)
):
    """
    图片格式转换接口
    - 支持多种图片格式互转
    """
    user_id = current_user.username if hasattr(current_user, 'username') else "system"
    return await DocFunc.convert_image_format(file, target_fmt, user_id=user_id)

@router.post("/ebook_convert", summary="电子书格式转换", description="支持 epub/mobi/pdf 互转")
async def convert_ebook(
    target_fmt: str = Form(..., description="目标格式 (pdf, epub, mobi)"),
    file: UploadFile = File(..., description="源电子书文件"), 
    current_user = Depends(get_current_active_user)
):
    """
    电子书格式转换接口
    - 支持 epub, mobi, pdf 之间的转换
    """
    user_id = current_user.username if hasattr(current_user, 'username') else "system"
    return await DocFunc.convert_ebook(file, target_fmt, user_id=user_id)
