<!--
文件名：frontend/src/components/business/DocumentToolDialog.vue
作者：zcl
日期：2026-02-10
描述：文档工具弹窗，选择转换类型并上传文件进行转换
-->
<script setup lang="ts">
import { ref, computed } from 'vue';
import { ElMessage } from 'element-plus';
import {
  mdToPdf,
  wordToPdf,
  imgToPdf,
  excelToPdf,
  pptToPdf,
  htmlToPdf,
  pdfToImages,
  pdfToWord,
  pdfToPpt,
  pdfToPdfA,
  ofdToPdf,
  ofdToImages,
  pdfUnlock,
  pdfToLongImage,
  svgToPdf,
  ebookConvertToPdf,
  type DocConvertSingle,
  type DocConvertMulti,
} from '@/api/doc';

const props = defineProps<{
  visible: boolean;
}>();

const emit = defineEmits<{
  (e: 'update:visible', value: boolean): void;
}>();

type ConvertType =
  | 'md2pdf'
  | 'word2pdf'
  | 'img2pdf'
  | 'excel2pdf'
  | 'ppt2pdf'
  | 'html2pdf'
  | 'pdf2img'
  | 'pdf2word'
  | 'pdf2ppt'
  | 'pdf2pdfa'
  | 'ofd2pdf'
  | 'ofd2img'
  | 'pdf_unlock'
  | 'pdf2longimg'
  | 'svg2pdf'
  | 'ebook_convert_pdf';

const options: Array<{ label: string; value: ConvertType; accept: string }> = [
  { label: 'Markdown 转 PDF', value: 'md2pdf', accept: '.md' },
  { label: 'Word 转 PDF', value: 'word2pdf', accept: '.doc,.docx' },
  { label: '图片 转 PDF', value: 'img2pdf', accept: 'image/*' },
  { label: 'Excel 转 PDF', value: 'excel2pdf', accept: '.xls,.xlsx' },
  { label: 'PPT 转 PDF', value: 'ppt2pdf', accept: '.ppt,.pptx' },
  { label: 'HTML 转 PDF', value: 'html2pdf', accept: '.html,.htm' },
  { label: 'PDF 转 图片', value: 'pdf2img', accept: '.pdf' },
  { label: 'PDF 转 Word', value: 'pdf2word', accept: '.pdf' },
  { label: 'PDF 转 PPT', value: 'pdf2ppt', accept: '.pdf' },
  { label: 'PDF 转 PDF/A', value: 'pdf2pdfa', accept: '.pdf' },
  { label: 'OFD 转 PDF', value: 'ofd2pdf', accept: '.ofd' },
  { label: 'OFD 转 图片', value: 'ofd2img', accept: '.ofd' },
  { label: 'PDF 移除限制', value: 'pdf_unlock', accept: '.pdf' },
  { label: 'PDF 转 长图', value: 'pdf2longimg', accept: '.pdf' },
  { label: 'SVG 转 PDF', value: 'svg2pdf', accept: '.svg' },
  { label: '电子书 转 PDF', value: 'ebook_convert_pdf', accept: '.epub,.mobi,.pdf' },
];

const dialogVisible = computed({
  get: () => props.visible,
  set: (val) => emit('update:visible', val),
});

const loading = ref(false);
const selected = ref<ConvertType>('md2pdf');
const fileRef = ref<File | null>(null);
const resultText = ref<string>('');

const currentAccept = computed(() => {
  const item = options.find(o => o.value === selected.value);
  return item?.accept || '*/*';
});

const onPickFile = (e: Event) => {
  const input = e.target as HTMLInputElement;
  if (input.files && input.files[0]) {
    fileRef.value = input.files[0];
  }
};

const startConvert = async () => {
  if (!fileRef.value) {
    ElMessage.warning('请先选择文件');
    return;
  }
  loading.value = true;
  resultText.value = '正在转换...';
  try {
    let res: DocConvertSingle | DocConvertMulti;
    const f = fileRef.value!;
    switch (selected.value) {
      case 'md2pdf': res = await mdToPdf(f); break;
      case 'word2pdf': res = await wordToPdf(f); break;
      case 'img2pdf': res = await imgToPdf(f); break;
      case 'excel2pdf': res = await excelToPdf(f); break;
      case 'ppt2pdf': res = await pptToPdf(f); break;
      case 'html2pdf': res = await htmlToPdf(f); break;
      case 'pdf2img': res = await pdfToImages(f); break;
      case 'pdf2word': res = await pdfToWord(f); break;
      case 'pdf2ppt': res = await pdfToPpt(f); break;
      case 'pdf2pdfa': res = await pdfToPdfA(f); break;
      case 'ofd2pdf': res = await ofdToPdf(f); break;
      case 'ofd2img': res = await ofdToImages(f); break;
      case 'pdf_unlock': res = await pdfUnlock(f); break;
      case 'pdf2longimg': res = await pdfToLongImage(f); break;
      case 'svg2pdf': res = await svgToPdf(f); break;
      case 'ebook_convert_pdf': res = await ebookConvertToPdf(f); break;
      default: res = await imgToPdf(f); break;
    }
    if ((res as any).urls && Array.isArray((res as any).urls)) {
      const urls: string[] = (res as any).urls;
      resultText.value = urls.map(u => `结果：${u}`).join('\n');
    } else if ((res as any).url) {
      const url: string = (res as any).url;
      resultText.value = `结果：${url}`;
    } else {
      resultText.value = '转换完成，但未返回结果链接';
    }
    ElMessage.success('转换完成');
  } catch (e: any) {
    resultText.value = `转换失败：${e?.message || '未知错误'}`;
    ElMessage.error('转换失败');
  } finally {
    loading.value = false;
  }
};
</script>

<template>
  <el-dialog
    v-model="dialogVisible"
    title="文档工具"
    width="40rem"
    destroy-on-close
  >
    <el-form label-width="7.5rem">
      <el-form-item label="转换类型">
        <el-select v-model="selected" placeholder="请选择转换类型" style="width: 18rem">
          <el-option v-for="opt in options" :key="opt.value" :label="opt.label" :value="opt.value" />
        </el-select>
      </el-form-item>
      <el-form-item label="选择文件">
        <input type="file" :accept="currentAccept" @change="onPickFile" />
      </el-form-item>
      <el-form-item label="转换结果" v-if="resultText">
        <el-card shadow="never">
          <pre>{{ resultText }}</pre>
        </el-card>
      </el-form-item>
    </el-form>
    <template #footer>
      <span class="dialog-footer">
        <el-button @click="dialogVisible = false">关闭</el-button>
        <el-button type="primary" :loading="loading" @click="startConvert">
          {{ loading ? '转换中...' : '开始转换' }}
        </el-button>
      </span>
    </template>
  </el-dialog>
  </template>

<style scoped>
.dialog-footer {
  display: inline-flex;
  gap: 0.75rem;
}
</style>
