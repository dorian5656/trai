<!--
文件名：frontend/src/components/business/SimilarityDialog.vue
作者：zcl
日期：2026-01-27
描述：相似度识别弹窗组件 (Element Plus Refactor)
-->

<script setup lang="ts">
import { ref, watch, computed } from 'vue';
import { predictSimilarity, type PredictRequest } from '@/api/rrdsppg';
import { uploadFile } from '@/api/common';
import { ElMessage, type UploadRequestOptions, type UploadFile } from 'element-plus';
import { UploadFilled } from '@element-plus/icons-vue';

const props = defineProps<{
  visible: boolean;
}>();

const emit = defineEmits<{
  (e: 'update:visible', value: boolean): void;
}>();

const type = ref(1); // 1: 公众号, 2: 服务号
const targetUrl = ref('');
const templateUrl = ref('');
const loading = ref(false);
const result = ref<any>(null);

// 上传状态
const targetLoading = ref(false);
const templateLoading = ref(false);

const dialogVisible = computed({
  get: () => props.visible,
  set: (val) => emit('update:visible', val),
});

// 监听弹窗关闭，重置数据
watch(() => props.visible, (newVal) => {
  if (!newVal) {
    result.value = null;
    loading.value = false;
    targetUrl.value = '';
    templateUrl.value = '';
    targetLoading.value = false;
    templateLoading.value = false;
  }
});

// 自定义上传处理
const handleUploadTarget = async (options: UploadRequestOptions) => {
  targetLoading.value = true;
  try {
    // 明确传递 module='rrdsppg' 参数
    const res = await uploadFile(options.file as File, 'rrdsppg');
    targetUrl.value = res.url;
    ElMessage.success('目标图片上传成功');
  } catch (error) {
    console.error(error);
    ElMessage.error('目标图片上传失败');
  } finally {
    targetLoading.value = false;
  }
};

const handleUploadTemplate = async (options: UploadRequestOptions) => {
  templateLoading.value = true;
  try {
    // 明确传递 module='rrdsppg' 参数
    const res = await uploadFile(options.file as File, 'rrdsppg');
    templateUrl.value = res.url;
    ElMessage.success('模板图片上传成功');
  } catch (error) {
    console.error(error);
    ElMessage.error('模板图片上传失败');
  } finally {
    templateLoading.value = false;
  }
};

const submit = async () => {
  if (!targetUrl.value || !templateUrl.value) {
    ElMessage.warning('请先上传目标图片和模板图片');
    return;
  }

  loading.value = true;
  result.value = null;

  try {
    // 2. 构造 JSON 请求
    // 注意: type 需要根据实际业务映射
    // 1996827967950909442 视频号
    // 1997929948761825282 公众号转发
    // 使用字符串以避免 JS 大整数精度丢失
    let typeVal = "0";
    if (type.value === 1) {
      // 公众号转发
      typeVal = "1997929948761825282";
    } else if (type.value === 2) {
      // 视频号
      typeVal = "1996827967950909442";
    }

    const payload: PredictRequest = {
      taskId: 1222, // 示例值
      userId: 221,  // 示例值
      type: typeVal,
      templatePath: templateUrl.value.trim(),
      targetPath: targetUrl.value.trim(),
      itzx: 0
    };

    const res = await predictSimilarity(payload);
    result.value = res;
    ElMessage.success('识别成功');
  } catch (error) {
    // 错误已在 request.ts 中统一处理，此处仅需处理 loading
    console.error(error);
  } finally {
    loading.value = false;
  }
};
</script>

<template>
  <el-dialog
    v-model="dialogVisible"
    title="相似度识别"
    width="37.5rem"
    destroy-on-close
  >
    <el-form label-width="6.25rem">
      <el-form-item label="类型选择">
        <el-radio-group v-model="type">
          <el-radio :value="1">公众号转发</el-radio>
          <el-radio :value="2">视频号</el-radio>
        </el-radio-group>
      </el-form-item>

      <el-form-item label="目标图片">
        <div class="upload-container">
          <el-upload
            class="upload-demo"
            drag
            action="#"
            :http-request="handleUploadTarget"
            :show-file-list="false"
            accept="image/*"
          >
            <div v-if="targetUrl" class="preview-box">
              <img :src="targetUrl" class="preview-img" />
              <div class="re-upload-mask">
                <el-icon class="el-icon--upload"><upload-filled /></el-icon>
                <div class="el-upload__text">点击或拖拽替换</div>
              </div>
            </div>
            <div v-else class="upload-placeholder">
              <el-icon class="el-icon--upload"><upload-filled /></el-icon>
              <div class="el-upload__text">
                拖拽上传或 <em>点击上传</em>
              </div>
            </div>
          </el-upload>
          <div v-if="targetLoading" class="loading-text">上传中...</div>
        </div>
      </el-form-item>

      <el-form-item label="模板图片">
        <div class="upload-container">
          <el-upload
            class="upload-demo"
            drag
            action="#"
            :http-request="handleUploadTemplate"
            :show-file-list="false"
            accept="image/*"
          >
            <div v-if="templateUrl" class="preview-box">
              <img :src="templateUrl" class="preview-img" />
              <div class="re-upload-mask">
                <el-icon class="el-icon--upload"><upload-filled /></el-icon>
                <div class="el-upload__text">点击或拖拽替换</div>
              </div>
            </div>
            <div v-else class="upload-placeholder">
              <el-icon class="el-icon--upload"><upload-filled /></el-icon>
              <div class="el-upload__text">
                拖拽上传或 <em>点击上传</em>
              </div>
            </div>
          </el-upload>
          <div v-if="templateLoading" class="loading-text">上传中...</div>
        </div>
      </el-form-item>

      <div v-if="result" class="result-box">
        <h4>识别结果:</h4>
        <el-card shadow="never" class="json-card">
          <pre>{{ JSON.stringify(result, null, 2) }}</pre>
        </el-card>
      </div>
    </el-form>

    <template #footer>
      <span class="dialog-footer">
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" @click="submit" :loading="loading">
          {{ loading ? '识别中...' : '开始识别' }}
        </el-button>
      </span>
    </template>
  </el-dialog>
</template>

<style scoped>
.result-box {
  margin-top: 1.25rem;
}
.json-card {
  max-height: 18.75rem;
  overflow-y: auto;
  background-color: #f5f7fa;
}
.upload-container {
  width: 100%;
}
.preview-box {
  position: relative;
  width: 100%;
  height: 100%;
  display: flex;
  justify-content: center;
  align-items: center;
  overflow: hidden;
}
.preview-img {
  max-width: 100%;
  max-height: 11.25rem;
  object-fit: contain;
}
.re-upload-mask {
  position: absolute;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
  background-color: rgba(0, 0, 0, 0.5);
  color: #fff;
  display: flex;
  flex-direction: column;
  justify-content: center;
  align-items: center;
  opacity: 0;
  transition: opacity 0.3s;
}
.preview-box:hover .re-upload-mask {
  opacity: 1;
}
.loading-text {
  text-align: center;
  font-size: 0.75rem;
  color: #909399;
  margin-top: 0.3125rem;
}
</style>
