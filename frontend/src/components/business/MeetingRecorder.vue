<!--
文件名：frontend/src/components/business/MeetingRecorder.vue
作者：whf & zcl
日期：2026-03-02
描述：会议记录组件 (多视图弹窗版)
-->
<script setup lang="ts">
import { ref, onMounted, nextTick } from 'vue';
import { icons } from '@/assets/icons';
import { ElMessage } from 'element-plus';
import { getMeetingHistory, getMeetingDetail, type Meeting } from '@/api/meeting';
import CreateMeetingView from './CreateMeetingView.vue';

// --- 组件状态 ---
const emit = defineEmits(['close']);
const currentView = ref('history'); // 'history': 历史记录, 'create': 创建, 'detail': 详情
const selectedMeetingId = ref<string | null>(null);
const isLoading = ref(false);
const createViewRef = ref<InstanceType<typeof CreateMeetingView> | null>(null);


// --- 历史视图状态 ---
const historyList = ref<Meeting[]>([]);

// --- 详情视图状态 ---
const meetingDetail = ref<Meeting | null>(null);

// --- 函数 ---

// 视图导航
const showHistory = async () => {
  isLoading.value = true;
  try {
    const res = await getMeetingHistory();
    historyList.value = res.items;
    currentView.value = 'history';
  } catch (e) {
    ElMessage.error('加载历史记录失败');
  } finally {
    isLoading.value = false;
  }
};

const showFabOptions = ref(false);

const handleStartRecording = () => {
  showFabOptions.value = false;
  currentView.value = 'create';
  nextTick(() => {
    createViewRef.value?.startMicrophone();
  });
};

const handleStartUpload = () => {
  showFabOptions.value = false;
  currentView.value = 'create';
  nextTick(() => {
    createViewRef.value?.triggerFileUpload();
  });
};

const showDetail = async (id: string) => {
  selectedMeetingId.value = id;
  isLoading.value = true;
  try {
    meetingDetail.value = await getMeetingDetail(id);
    currentView.value = 'detail';
  } catch (e) {
    ElMessage.error('加载详情失败');
  } finally {
    isLoading.value = false;
  }
};

// 生命周期
onMounted(() => {
  showHistory();
});
</script>

<template>
  <div class="meeting-recorder-overlay" @click.self="emit('close')">
    <div class="recorder-card">
      <!-- 通用头部 -->
      <div class="card-header">
        <div class="title">
          <button v-if="currentView !== 'history'" class="back-btn" @click="showHistory">
            <span v-html="icons.arrowLeft"></span>
          </button>
          <span v-if="currentView === 'history'" class="item-title">会议记录</span>
          <span v-if="currentView === 'create'" class="item-title">创建新纪要</span>
          <span v-if="currentView === 'detail'" class="item-title">纪要详情</span>
        </div>
        <button class="close-btn" @click="emit('close')">
          <span v-html="icons.closeSmall"></span>
        </button>
      </div>

      <!-- 加载遮罩 -->
      <div v-if="isLoading" class="loading-overlay">
        <span class="loading-spinner"></span>
        <p>加载中...</p>
      </div>

      <!-- 视图 -->
      <div v-else class="card-body">
        <!-- 1. 历史视图 -->
        <div v-if="currentView === 'history'" class="history-view">
          <div v-if="!historyList.length" class="empty-history">
            <p>还没有会议记录</p>
            <p>点击右下角“+”按钮，开始创建你的第一份会议纪要吧！</p>
          </div>
          <div v-else>
            <div v-for="item in historyList" :key="item.id" class="history-item" @click="showDetail(item.id)">
              <div class="item-title">{{ item.title }}</div>
              <div class="item-date">{{ item.createdAt }}</div>
            </div>
          </div>
        </div>

        <!-- 2. 创建视图 -->
        <CreateMeetingView
          v-if="currentView === 'create'"
          ref="createViewRef"
          @back="showHistory"
          @saved="showDetail"
        />

        <!-- 3. 详情视图 -->
        <div v-if="currentView === 'detail' && meetingDetail" class="detail-view">
           <h2>{{ meetingDetail.title }}</h2>
          <small>创建于: {{ meetingDetail.createdAt }}</small>

          <div v-if="meetingDetail.summary" class="detail-section">
            <h3>会议纪要</h3>
            <div class="summary-content" v-html="meetingDetail.summary"></div>
          </div>

          <div class="detail-section">
            <h3>逐字稿</h3>
            <p>{{ meetingDetail.text }}</p>
          </div>
        </div>

        <!-- 历史视图的悬浮操作按钮 -->
        <div v-if="currentView === 'history'" class="fab-container">
          <transition name="fab-options">
            <div v-if="showFabOptions" class="fab-options">
              <div class="fab-option-item" @click="handleStartRecording">
                <div class="fab-option-icon">
                  <span v-html="icons.micNormal"></span>
                </div>
                <span class="fab-option-label">实时录音</span>
              </div>
              <div class="fab-option-item" @click="handleStartUpload">
                <div class="fab-option-icon">
                  <span v-html="icons.attachment"></span>
                </div>
                <span class="fab-option-label">上传音频</span>
              </div>
            </div>
          </transition>
          <button class="fab-create-new" :class="{ 'rotated': showFabOptions }" @click="showFabOptions = !showFabOptions">
            <span v-html="icons.plus"></span>
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.meeting-recorder-overlay {
  position: fixed;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
  background: rgba(0, 0, 0, 0.4);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 2000;
}

.recorder-card {
  width: 95vw;
  max-width: 50rem;
  height: 85vh;
  max-height: 60rem;
  background: #fff;
  border-radius: 0.875rem;
  box-shadow: 0 0.5rem 1.5rem rgba(0, 0, 0, 0.1);
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.card-header {
  padding: 1rem 1.5rem;
  border-bottom: 1px solid #f2f3f5;
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.card-header .title {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  font-size: 1.125rem;
  font-weight: 600;
}

.card-header .icon {
  color: #f53f3f;
}

.card-header .icon,
.close-btn span {
  width: 1.25rem;
  height: 1.25rem;
  display: flex;
  align-items: center;
}

.close-btn {
  background: none; border: none; cursor: pointer; padding: 0.25rem;
  border-radius: 50%;
}
.close-btn:hover { background: #f2f3f5; }

.back-btn {
  background: none; border: none; cursor: pointer; padding: 0.25rem;
  display: flex; align-items: center; justify-content: center;
  border-radius: 50%;
}
.back-btn:hover { background: #f2f3f5; }
.back-btn span { width: 1.25rem; height: 1.25rem; }

.card-body {
  flex: 1;
  overflow-y: auto;
  overflow-x: hidden; /* 防止水平滚动条 */
  position: relative; /* 用于悬浮按钮定位 */
  background: #f7f8fa;
}

.loading-overlay {
  display: flex; flex-direction: column; align-items: center; justify-content: center;
  height: 100%; gap: 1rem; color: #86909c;
}

/* 历史视图 */
.history-view {
  padding: 1rem;
  padding-bottom: 8rem; /* 添加内边距以避免悬浮按钮重叠 */
}
.empty-history {
  text-align: center;
  color: #86909c;
  padding-top: 6rem;
  font-size: 0.9375rem;
  line-height: 1.6;
}
.history-item {
  background-color: #fff; padding: 1rem; border-radius: 0.5rem;
  margin-bottom: 0.75rem; cursor: pointer; transition: all 0.2s;
}
.history-item:hover { transform: translateY(-2px); box-shadow: 0 4px 12px rgba(0,0,0,0.08); }
.item-title { font-weight: 600; color: #1d2129; margin-bottom: 0.25rem; }
.item-date { font-size: 0.875rem; color: #86909c; }
.fab-container {
  position: absolute;
  bottom: 4rem;
  right: 3rem;
}

.fab-options {
  position: absolute;
  bottom: calc(100% + 1rem);
  left: 50%;
  transform: translateX(-50%);
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 1rem;
}

.fab-option-item {
  display: flex;
  align-items: center;
  cursor: pointer;
}

.fab-option-label {
  background: rgba(0, 0, 0, 0.7);
  color: white;
  padding: 0.25rem 0.625rem;
  border-radius: 0.25rem;
  margin-left: 0.75rem;
  font-size: 0.8125rem;
  box-shadow: 0 2px 5px rgba(0,0,0,0.2);
  white-space: nowrap;
}

.fab-option-icon {
  width: 2.75rem;
  height: 2.75rem;
  border-radius: 50%;
  background: #fff;
  display: flex;
  align-items: center;
  justify-content: center;
  box-shadow: 0 2px 8px rgba(0,0,0,0.15);
  color: #165dff;
  transition: transform 0.2s;
}

.fab-option-icon span {
  width: 1.375rem;
  height: 1.375rem;
  display: flex;
  align-items: center;
  justify-content: center;
}

.fab-option-item:hover .fab-option-icon {
  transform: scale(1.1);
}

.fab-create-new {
  width: 3.5rem; height: 3.5rem;
  border-radius: 50%; background-color: #165dff; color: white; border: none;
  font-size: 2rem; 
  display: flex; align-items: center; justify-content: center;
  cursor: pointer;
  box-shadow: 0 4px 12px rgba(22, 93, 255, 0.3);
  transition: transform 0.2s, background-color 0.2s;
}

.fab-create-new :deep(span) {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 1.375rem;
  height: 1.375rem;
  transition: transform 0.2s ease-out;
}

.fab-create-new.rotated :deep(span) {
  transform: rotate(-45deg);
}

/* 过渡效果 */
.fab-options-enter-active,
.fab-options-leave-active {
  transition: all 0.3s cubic-bezier(0.175, 0.885, 0.32, 1.275);
}

.fab-options-enter-from,
.fab-options-leave-to {
  transform: translateY(20px) scale(0.9);
  opacity: 0;
}

/* 创建视图 */
.create-view { display: flex; flex-direction: column; height: 100%; padding: 1rem; gap: 1rem; }
.main-content { flex: 1; overflow-y: auto; background: #fff; padding: 1rem; border-radius: 0.5rem; }
.placeholder { text-align: center; color: #86909c; padding-top: 4rem; }
.text-content { white-space: pre-wrap; line-height: 1.7; }
.final { color: #1d2129; }
.interim { color: #86909c; }
.cursor { animation: blink 1s step-end infinite; }
.summary-section { padding: 1rem; background: #fff; border-radius: 0.5rem; }
.create-footer { display: flex; justify-content: space-around; padding-top: 1rem; border-top: 1px solid #f2f3f5; }

/* 详情视图 */
.detail-view { padding: 1.5rem; background: #fff; height: 100%;}
.detail-view h2 { font-size: 1.25rem; margin-bottom: 0.25rem; }
.detail-view small { color: #86909c; margin-bottom: 1.5rem; display: block; }
.detail-section { margin-top: 1.5rem; }
.detail-section h3 { font-size: 1rem; font-weight: 600; margin-bottom: 0.5rem; }
.detail-section p { line-height: 1.7; color: #4e5969; white-space: pre-wrap; }

/* 通用样式 */
.pill-btn { display: inline-flex; align-items: center; gap: 0.375rem; padding: 0.5rem 1rem; border-radius: 999px; border: 1px solid #e5e6eb; background: #ffffff; font-size: 0.875rem; cursor: pointer; }
.pill-btn.primary { border-color: #165dff; background: #165dff; color: #ffffff; }
.pill-btn:disabled { opacity: 0.5; cursor: not-allowed; }
.loading-spinner { width: 1.5rem; height: 1.5rem; border: 0.1875rem solid #165DFF; border-top-color: transparent; border-radius: 50%; animation: spin 1s linear infinite; }
@keyframes spin { to { transform: rotate(360deg); } }
@keyframes blink { 50% { opacity: 0; } }
</style>
