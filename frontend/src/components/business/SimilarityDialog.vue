<!--
文件名：frontend/src/components/business/SimilarityDialog.vue
作者：zcl
日期：2026-01-27
描述：相似度识别弹窗组件 (Element Plus Refactor)
-->

<script setup lang="ts">
import { ref, watch, computed, reactive } from 'vue';
import { predictSimilarity, type PredictRequest } from '@/api/rrdsppg';
import { uploadFile } from '@/api/common';
import { ElMessage, type UploadRequestOptions, type UploadFile } from 'element-plus';
import { UploadFilled } from '@element-plus/icons-vue';
import { isMobile } from '@/utils/device';

const props = defineProps<{
  visible: boolean;
}>();

const emit = defineEmits<{
  (e: 'update:visible', value: boolean): void;
}>();

const type = ref<1 | 2>(1); // 1: 公众号, 2: 服务号

// 定义每个类型的独立状态接口
interface StateItem {
  targetUrl: string;
  templateUrl: string;
  result: any;
  loading: boolean;
  targetLoading: boolean;
  templateLoading: boolean;
}

// 状态 Map：key 为 type 值
const stateMap = reactive<Record<1 | 2, StateItem>>({
  1: {
    targetUrl: '',
    templateUrl: '',
    result: null,
    loading: false,
    targetLoading: false,
    templateLoading: false,
  },
  2: {
    targetUrl: '',
    templateUrl: '',
    result: null,
    loading: false,
    targetLoading: false,
    templateLoading: false,
  }
});

// 当前激活的状态
const currentState = computed<StateItem>(() => stateMap[type.value]);

const dialogVisible = computed({
  get: () => props.visible,
  set: (val) => emit('update:visible', val),
});

const dialogWidth = computed(() => (isMobile() ? '90vw' : '50rem'));

// 监听弹窗关闭，重置数据
watch(() => props.visible, (newVal) => {
  if (!newVal) {
    // 遍历所有状态进行重置
    Object.values(stateMap).forEach(state => {
      state.result = null;
      state.loading = false;
      state.targetUrl = '';
      state.templateUrl = '';
      state.targetLoading = false;
      state.templateLoading = false;
    });
    // 重置为默认 tab
    type.value = 1;
  }
});

// 自定义上传处理
const handleUploadTarget = async (options: UploadRequestOptions) => {
  const state = currentState.value;
  state.targetLoading = true;
  try {
    // 明确传递 module='rrdsppg' 参数
    const res = await uploadFile(options.file as File, 'rrdsppg');
    state.targetUrl = res.url;
    ElMessage.success('目标图片上传成功');
  } catch (error) {
    console.error(error);
    ElMessage.error('目标图片上传失败');
  } finally {
    state.targetLoading = false;
  }
};

const handleUploadTemplate = async (options: UploadRequestOptions) => {
  const state = currentState.value;
  state.templateLoading = true;
  try {
    // 明确传递 module='rrdsppg' 参数
    const res = await uploadFile(options.file as File, 'rrdsppg');
    state.templateUrl = res.url;
    ElMessage.success('模板图片上传成功');
  } catch (error) {
    console.error(error);
    ElMessage.error('模板图片上传失败');
  } finally {
    state.templateLoading = false;
  }
};

const submit = async () => {
  const state = currentState.value;
  if (!state.targetUrl || !state.templateUrl) {
    ElMessage.warning('请先上传目标图片和模板图片');
    return;
  }

  state.loading = true;
  state.result = null;

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
      templatePath: state.templateUrl.trim(),
      targetPath: state.targetUrl.trim(),
      itzx: 0
    };

    const res = await predictSimilarity(payload);
    state.result = res;
    ElMessage.success('识别成功');
  } catch (error) {
    // 错误已在 request.ts 中统一处理，此处仅需处理 loading
    console.error(error);
  } finally {
    state.loading = false;
  }
};
</script>

<template>
  <el-dialog
    v-model="dialogVisible"
    title="相似度识别"
    :width="dialogWidth"
    destroy-on-close
  >
    <el-form label-width="6.25rem">
      <el-form-item label="类型选择">
        <el-radio-group v-model="type">
          <el-radio :value="1">公众号转发</el-radio>
          <el-radio :value="2">视频号</el-radio>
        </el-radio-group>
      </el-form-item>

      <div class="image-sections">
        <div class="image-section">
          <div class="section-label">目标图片</div>
          <div class="upload-container">
            <el-upload
              class="upload-demo"
              drag
              action="#"
              :http-request="handleUploadTarget"
              :show-file-list="false"
              accept="image/*"
            >
              <div v-if="currentState.targetUrl" class="preview-box">
                <img :src="currentState.targetUrl" class="preview-img" />
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
            <div v-if="currentState.targetLoading" class="loading-text">上传中...</div>
            <el-input 
              v-model="currentState.targetUrl" 
              placeholder="请输入图片URL" 
              class="url-input" 
              clearable
            />
          </div>
        </div>

        <div class="image-section">
          <div class="section-label">模板图片</div>
          <div class="upload-container">
            <el-upload
              class="upload-demo"
              drag
              action="#"
              :http-request="handleUploadTemplate"
              :show-file-list="false"
              accept="image/*"
            >
              <div v-if="currentState.templateUrl" class="preview-box">
                <img :src="currentState.templateUrl" class="preview-img" />
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
            <div v-if="currentState.templateLoading" class="loading-text">上传中...</div>
            <el-input 
              v-model="currentState.templateUrl" 
              placeholder="请输入图片URL" 
              class="url-input" 
              clearable
            />
          </div>
        </div>
      </div>

      <div v-if="currentState.result" class="result-box">
        <h4>识别结果:</h4>
        <div class="similarity-score" v-if="currentState.result.similarity_score !== undefined">
          相似度：<span class="score-value">{{ (currentState.result.similarity_score * 100).toFixed(2) }}%</span>
        </div>
        <el-card v-else shadow="never" class="json-card">
          <pre>{{ JSON.stringify(currentState.result, null, 2) }}</pre>
        </el-card>
      </div>
    </el-form>

    <template #footer>
      <span class="dialog-footer">
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" @click="submit" :loading="currentState.loading">
          {{ currentState.loading ? '识别中...' : '开始识别' }}
        </el-button>
      </span>
    </template>
  </el-dialog>
</template>

<style scoped>
.image-sections {
  display: flex;
  justify-content: space-between;
  gap: 1.25rem;
  margin-bottom: 1.25rem;
}
.image-section {
  flex: 1;
  display: flex;
  flex-direction: column;
}
.section-label {
  font-weight: bold;
  margin-bottom: 0.625rem;
  color: #606266;
}
.url-input {
  margin-top: 0.625rem;
}
.similarity-score {
  font-size: 1.5rem;
  font-weight: bold;
  color: #303133;
  margin-top: 0.625rem;
}
.score-value {
  color: #409eff;
}
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

@media (max-width: 768px) {
  :deep(.el-dialog) {
    margin: 0 !important;
  }
  .image-sections {
    flex-direction: column;
  }
  .preview-img {
    max-height: 30vh;
  }
  :deep(.el-form-item__label) {
    font-size: 0.875rem;
  }
  :deep(.el-button) {
    font-size: 0.875rem;
    padding: 0.5rem 0.75rem;
    border-radius: 0.5rem;
  }
}
</style>
