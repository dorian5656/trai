<script setup lang="ts">
import { ref, reactive, onMounted } from 'vue';
import { ElMessage, ElImageViewer } from 'element-plus';
import { generateImage, getImageHistory, type ImageGenRequest, type ImageGenResponse } from '@/api/image';
import { IMAGEGEN_MODEL_OPTIONS, RATIO_OPTIONS, STYLE_OPTIONS } from '@/constants/imagegen';
import { useChatStore } from '@/stores/chat';

const props = defineProps<{
  visible: boolean;
}>();

const emit = defineEmits<{
  (e: 'update:visible', visible: boolean): void;
}>();

const chatStore = useChatStore();

const loading = ref(false);
const loadingHistory = ref(false);
const historyList = ref<ImageGenResponse[]>([]);
const historyDialogVisible = ref(false);
const historyDialogLoading = ref(false);
const historyDialogList = ref<ImageGenResponse[]>([]);
const historyPagination = reactive({
  page: 1,
  size: 20,
  total: 0
});

const viewerVisible = ref(false);
const viewerUrlList = ref<string[]>([]);
const viewerInitialIndex = ref(0);

const form = reactive({
  prompt: '',
  ratio: '1:1',
  style: 'photorealistic',
  n: 1
});

const fetchPreviewHistory = async () => {
  loadingHistory.value = true;
  try {
    const res = await getImageHistory({ page: 1, size: 10 });
    if (res && res.items) {
      historyList.value = res.items;
    }
  } catch (error) {
    console.error('获取历史记录失败:', error);
  } finally {
    loadingHistory.value = false;
  }
};

const getHistoryImageUrl = (item: ImageGenResponse): string => {
  return item.data?.[0]?.url || item.url || '';
};

const fetchDialogHistory = async (page?: number) => {
  if (typeof page === 'number') {
    historyPagination.page = page;
  }
  historyDialogLoading.value = true;
  try {
    const res = await getImageHistory({
      page: historyPagination.page,
      size: historyPagination.size
    });
    if (res && res.items) {
      historyDialogList.value = res.items;
      historyPagination.total = res.total;
    }
  } catch (error) {
    console.error('获取全部历史记录失败:', error);
  } finally {
    historyDialogLoading.value = false;
  }
};

const useHistory = (item: ImageGenResponse) => {
  if (item.prompt) form.prompt = item.prompt;
  // if (item.ratio) form.ratio = item.ratio;
  // if (item.style) form.style = item.style;
};

const openPreviewFromPreviewList = (index: number) => {
  if (!historyList.value.length) return;
  const urls: string[] = [];
  let initialIndex = 0;
  historyList.value.forEach((item, idx) => {
    const url = getHistoryImageUrl(item);
    if (!url) return;
    if (idx === index) {
      initialIndex = urls.length;
    }
    urls.push(url);
  });
  if (!urls.length) return;
  viewerUrlList.value = urls;
  viewerInitialIndex.value = initialIndex;
  viewerVisible.value = true;
};

const openPreviewFromDialogList = (index: number) => {
  if (!historyDialogList.value.length) return;
  const urls: string[] = [];
  let initialIndex = 0;
  historyDialogList.value.forEach((item, idx) => {
    const url = getHistoryImageUrl(item);
    if (!url) return;
    if (idx === index) {
      initialIndex = urls.length;
    }
    urls.push(url);
  });
  if (!urls.length) return;
  viewerUrlList.value = urls;
  viewerInitialIndex.value = initialIndex;
  viewerVisible.value = true;
};

const openHistoryDialog = async () => {
  historyDialogVisible.value = true;
  if (!historyDialogList.value.length) {
    await fetchDialogHistory(1);
  }
};

const handleHistoryPageChange = (page: number) => {
  fetchDialogHistory(page);
};

const handleReuseFromDialog = (item: ImageGenResponse) => {
  useHistory(item);
  historyDialogVisible.value = false;
  ElMessage.success('已使用该历史记录的参数');
};

onMounted(() => {
  fetchPreviewHistory();
});

const handleClose = () => {
  emit('update:visible', false);
};

const submit = async () => {
  if (!form.prompt.trim()) {
    ElMessage.warning('请输入画面描述');
    return;
  }

  loading.value = true;
  
  // 添加用户消息到聊天记录
  const userContent = `生成图片：${form.prompt} (模型: Z-Image, 比例: ${form.ratio}, 风格: ${form.style})`;
  chatStore.addMessage('user', userContent);
  chatStore.addMessage('assistant', '正在生成图片...');
  
  // 关闭弹窗
  handleClose();

  try {
    // 转换比例为尺寸
    let size = '1024x1024';
    if (form.ratio === '16:9') size = '1024x576';
    else if (form.ratio === '9:16') size = '576x1024';
    else if (form.ratio === '4:3') size = '1024x768';
    else if (form.ratio === '3:4') size = '768x1024';

    // 组合 Prompt (加入风格)
    const styleLabel = STYLE_OPTIONS.find(s => s.value === form.style)?.label || '';
    const fullPrompt = styleLabel ? `${styleLabel}风格。${form.prompt}` : form.prompt;

    const requestData: ImageGenRequest = {
      prompt: fullPrompt,
      model: 'Z-Image',
      size: size,
      n: form.n
    };

    const result = await generateImage(requestData);
    
    // 处理返回结果 (支持多张图片)
    const urls: string[] = [];
    
    if (result && (result as any).data && Array.isArray((result as any).data)) {
      (result as any).data.forEach((item: any) => {
        if (item && typeof item.url === 'string') {
          urls.push(item.url);
        }
      });
    } else if (Array.isArray(result)) {
      (result as any).forEach((item: any) => {
        if (item && typeof item.url === 'string') {
          urls.push(item.url);
        }
      });
    }
    
    if (urls.length > 0) {
      const markdown = urls.map((url) => `![生成的图片](${url})`).join(' ');
      chatStore.updateLastMessage(markdown);
    } else {
      chatStore.updateLastMessage('❌ 生成失败：未返回有效的图片 URL');
    }
  } catch (error: any) {
    console.error('图像生成失败:', error);
    chatStore.updateLastMessage(`❌ 生成失败：${error.message || '未知错误'}`);
  } finally {
    loading.value = false;
  }
};
</script>

<template>
  <el-dialog
    :model-value="visible"
    @update:model-value="(val: boolean) => emit('update:visible', val)"
    title="图像生成"
    width="37.5rem"
    destroy-on-close
    class="image-gen-dialog"
  >
    <el-form label-position="top">
      <el-form-item label="画面描述">
        <el-input
          v-model="form.prompt"
          type="textarea"
          :rows="4"
          placeholder="描述你所想象的画面、角色、情绪、场景、风格…"
          resize="none"
        />
      </el-form-item>

      <div class="options-grid">
        <el-form-item label="图片比例">
          <el-select v-model="form.ratio" placeholder="选择比例">
            <el-option
              v-for="item in RATIO_OPTIONS"
              :key="item.value"
              :label="item.label"
              :value="item.value"
            />
          </el-select>
        </el-form-item>

        <el-form-item label="艺术风格">
          <el-select v-model="form.style" placeholder="选择风格">
            <el-option
              v-for="item in STYLE_OPTIONS"
              :key="item.value"
              :label="item.label"
              :value="item.value"
            />
          </el-select>
        </el-form-item>
        
        <el-form-item label="生成数量">
           <el-input-number v-model="form.n" :min="1" :max="4" />
        </el-form-item>
      </div>
    </el-form>

    <template #footer>
      <div class="footer-wrapper">
        <div class="dialog-actions">
          <el-button @click="handleClose">取消</el-button>
          <el-button type="primary" @click="submit" :loading="loading">
            开始生成
          </el-button>
        </div>

        <div v-if="historyList.length > 0" class="history-area">
          <div class="history-header">
            <div class="history-title">
              <span class="history-title-text">历史记录</span>
              <span class="history-subtitle">最近 10 条</span>
            </div>
            <button class="history-more-btn" type="button" @click="openHistoryDialog">
              查看全部
            </button>
          </div>
          <div v-if="loadingHistory" class="history-loading">
            正在加载历史记录...
          </div>
          <div v-else class="history-list">
            <div 
              v-for="(item, index) in historyList" 
              :key="item.id || index" 
              class="history-item"
              :title="item.prompt"
            >
              <img v-if="getHistoryImageUrl(item)" :src="getHistoryImageUrl(item)" class="history-img" />
              <div class="history-hover-info">
                <span class="prompt-text">{{ item.prompt || '无描述' }}</span>
                <div class="history-actions">
                  <button
                    type="button"
                    class="history-action-btn"
                    @click.stop="openPreviewFromPreviewList(index)"
                  >
                    预览
                  </button>
                  <button
                    type="button"
                    class="history-action-btn"
                    @click.stop="useHistory(item)"
                  >
                    重用
                  </button>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </template>
  </el-dialog>

  <el-dialog
    v-model="historyDialogVisible"
    title="全部历史记录"
    width="50rem"
    destroy-on-close
    append-to-body
    class="image-history-dialog"
  >
    <div class="history-dialog-content">
      <div v-if="historyDialogLoading" class="history-dialog-loading">
        正在加载历史记录...
      </div>
      <template v-else>
        <div v-if="historyDialogList.length === 0" class="history-dialog-empty">
          暂无历史记录
        </div>
        <div v-else class="history-dialog-grid">
          <div
            v-for="(item, index) in historyDialogList"
            :key="item.id || index"
            class="history-dialog-item"
          >
            <img
              v-if="getHistoryImageUrl(item)"
              :src="getHistoryImageUrl(item)"
              class="history-dialog-img"
            />
            <div class="history-dialog-mask">
              <div class="history-dialog-prompt">
                {{ item.prompt || '无描述' }}
              </div>
              <div class="history-dialog-meta">
                <span class="meta-time">{{ item.created_at || '' }}</span>
                <span v-if="item.model" class="meta-model">{{ item.model }}</span>
              </div>
              <div class="history-dialog-actions">
                <el-button
                  size="small"
                  text
                  @click.stop="openPreviewFromDialogList(index)"
                >
                  预览
                </el-button>
                <el-button
                  size="small"
                  type="primary"
                  text
                  @click.stop="handleReuseFromDialog(item)"
                >
                  重用参数
                </el-button>
              </div>
            </div>
          </div>
        </div>
        <div
          v-if="historyPagination.total > historyPagination.size"
          class="history-dialog-pagination"
        >
          <el-pagination
            background
            layout="prev, pager, next"
            :page-size="historyPagination.size"
            :current-page="historyPagination.page"
            :total="historyPagination.total"
            @current-change="handleHistoryPageChange"
          />
        </div>
      </template>
    </div>
  </el-dialog>

  <ElImageViewer
    v-if="viewerVisible"
    :url-list="viewerUrlList"
    :initial-index="viewerInitialIndex"
    @close="viewerVisible = false"
  />
</template>

<style scoped lang="scss">
.footer-wrapper {
  display: flex;
  flex-direction: column;
  gap: 1.25rem;
}

.dialog-actions {
  display: flex;
  justify-content: flex-end;
  gap: 0.75rem;
}

.history-area {
  border-top: 1px solid #e5e6eb;
  padding-top: 1rem;
  
  .history-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    margin-bottom: 0.75rem;
  }

  .history-title {
    display: flex;
    align-items: baseline;
    gap: 0.5rem;

    .history-title-text {
      font-size: 0.875rem;
      font-weight: 600;
      color: #1d2129;
    }

    .history-subtitle {
      font-size: 0.75rem;
      color: #86909c;
    }
  }

  .history-more-btn {
    border: none;
    background: transparent;
    padding: 0;
    font-size: 0.75rem;
    color: #165dff;
    cursor: pointer;
  }

  .history-loading {
    font-size: 0.75rem;
    color: #86909c;
  }

  .history-list {
    display: flex;
    gap: 0.75rem;
    overflow-x: auto;
    padding-bottom: 0.5rem;
    
    &::-webkit-scrollbar {
      height: 4px;
    }
    &::-webkit-scrollbar-thumb {
      background: #e5e6eb;
      border-radius: 2px;
    }

    .history-item {
      flex-shrink: 0;
      width: 6.25rem;
      height: 6.25rem;
      cursor: pointer;
      border: 1px solid #e5e6eb;
      border-radius: 0.5rem;
      overflow: hidden;
      transition: all 0.2s;
      position: relative;

      &:hover {
        border-color: #165dff;
        transform: translateY(-2px);
        
        .history-hover-info {
          opacity: 1;
        }
      }

      .history-img {
        width: 100%;
        height: 100%;
        object-fit: cover;
        display: block;
      }

      .history-hover-info {
        position: absolute;
        bottom: 0;
        left: 0;
        right: 0;
        background: rgba(0, 0, 0, 0.75);
        color: #ffffff;
        padding: 0.25rem 0.375rem;
        font-size: 0.75rem;
        opacity: 0;
        transition: opacity 0.2s;
        display: flex;
        flex-direction: column;
        gap: 0.25rem;
        
        .prompt-text {
          display: block;
          white-space: nowrap;
          overflow: hidden;
          text-overflow: ellipsis;
        }

        .history-actions {
          display: flex;
          justify-content: flex-end;
          gap: 0.25rem;
        }

        .history-action-btn {
          border: none;
          padding: 0.125rem 0.375rem;
          border-radius: 0.25rem;
          font-size: 0.6875rem;
          cursor: pointer;
          background: rgba(0, 0, 0, 0.6);
          color: #ffffff;
        }

        .history-action-btn:last-child {
          background: #165dff;
        }
      }
    }
  }
}

.image-history-dialog {
  :deep(.el-dialog__body) {
    padding-top: 0.75rem;
  }
}

.history-dialog-content {
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
}

.history-dialog-loading,
.history-dialog-empty {
  font-size: 0.875rem;
  color: #86909c;
  text-align: center;
  padding: 1.5rem 0;
}

.history-dialog-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(7.5rem, 1fr));
  gap: 0.75rem;
}

.history-dialog-item {
  position: relative;
  cursor: pointer;
  border-radius: 0.5rem;
  overflow: hidden;
  border: 1px solid #e5e6eb;
  transition: transform 0.2s, border-color 0.2s;

  &:hover {
    transform: translateY(-2px);
    border-color: #165dff;

    .history-dialog-mask {
      opacity: 1;
    }
  }
}

.history-dialog-img {
  width: 100%;
  height: 9.375rem;
  object-fit: cover;
  display: block;
}

.history-dialog-mask {
  position: absolute;
  left: 0;
  right: 0;
  bottom: 0;
  padding: 0.375rem 0.5rem;
  background: linear-gradient(to top, rgba(0, 0, 0, 0.75), transparent);
  color: #ffffff;
  opacity: 0;
  transition: opacity 0.2s;
  display: flex;
  flex-direction: column;
  gap: 0.25rem;
}

.history-dialog-prompt {
  font-size: 0.75rem;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.history-dialog-meta {
  display: flex;
  justify-content: space-between;
  align-items: center;
  font-size: 0.6875rem;

  .meta-model {
    padding: 0 0.25rem;
    border-radius: 0.25rem;
    background: rgba(22, 93, 255, 0.2);
  }
}

.history-dialog-actions {
  display: flex;
  justify-content: flex-end;
}

.history-dialog-pagination {
  margin-top: 0.5rem;
  display: flex;
  justify-content: center;
}

.options-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 1.25rem;
}

:deep(.el-dialog__body) {
  padding-top: 0.625rem;
  padding-bottom: 0.625rem;
}

:deep(.el-textarea__inner) {
  padding: 0.75rem;
  border-radius: 0.5rem;
}

@media (max-width: 48rem) {
  .options-grid {
    grid-template-columns: 1fr;
    gap: 0;
  }
  
  :deep(.el-dialog) {
    width: 90% !important;
    margin-top: 10vh !important;
  }
}
</style>
