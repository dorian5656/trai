// 文件名：frontend/src/api/doc.ts
// 作者：zcl
// 日期：2026-02-10
// 描述：文档工具接口封装 (前端调用后端 /tools/doc 路由)
import request from '@/utils/request';

export interface DocConvertSingle {
  url: string;
  filename?: string;
  duration?: string;
}

export interface DocConvertMulti {
  urls: string[];
  duration?: string;
}

const postFile = async (path: string, file: File, extra?: Record<string, string>) => {
  const form = new FormData();
  form.append('file', file);
  if (extra) {
    Object.entries(extra).forEach(([k, v]) => form.append(k, v));
  }
  return request.post<any, DocConvertSingle | DocConvertMulti>(`/tools/doc${path}`, form, {
    headers: { 'Content-Type': 'multipart/form-data' },
  });
};

export const mdToPdf = (file: File) => postFile('/md2pdf', file);
export const wordToPdf = (file: File) => postFile('/word2pdf', file);
export const imgToPdf = (file: File) => postFile('/img2pdf', file);
export const excelToPdf = (file: File) => postFile('/excel2pdf', file);
export const pptToPdf = (file: File) => postFile('/ppt2pdf', file);
export const htmlToPdf = (file: File) => postFile('/html2pdf', file);
export const pdfToImages = (file: File) => postFile('/pdf2img', file);
export const pdfToWord = (file: File) => postFile('/pdf2word', file);
export const pdfToPpt = (file: File) => postFile('/pdf2ppt', file);
export const pdfToPdfA = (file: File) => postFile('/pdf2pdfa', file);
export const ofdToPdf = (file: File) => postFile('/ofd2pdf', file);
export const ofdToImages = (file: File) => postFile('/ofd2img', file);
export const pdfUnlock = (file: File) => postFile('/pdf_unlock', file);
export const pdfToLongImage = (file: File) => postFile('/pdf2longimg', file);
export const svgToPdf = (file: File) => postFile('/svg2pdf', file);
export const ebookConvertToPdf = (file: File) => postFile('/ebook_convert', file, { target_fmt: 'pdf' });

export const convertByExt = async (file: File): Promise<DocConvertSingle | DocConvertMulti> => {
  const name = file.name.toLowerCase();
  if (name.endsWith('.md')) return mdToPdf(file);
  if (name.endsWith('.doc') || name.endsWith('.docx')) return wordToPdf(file);
  if (name.endsWith('.jpg') || name.endsWith('.jpeg') || name.endsWith('.png')) return imgToPdf(file);
  if (name.endsWith('.xlsx') || name.endsWith('.xls')) return excelToPdf(file);
  if (name.endsWith('.ppt') || name.endsWith('.pptx')) return pptToPdf(file);
  if (name.endsWith('.html') || name.endsWith('.htm')) return htmlToPdf(file);
  if (name.endsWith('.svg')) return svgToPdf(file);
  if (name.endsWith('.ofd')) return ofdToPdf(file);
  if (name.endsWith('.epub') || name.endsWith('.mobi')) return ebookConvertToPdf(file);
  if (name.endsWith('.pdf')) return pdfToImages(file);
  return imgToPdf(file);
};

