<!--
文件名：frontend/src/components/business/MeetingRecorder.vue
作者：whf & zcl
日期：2026-03-02
描述：会议记录组件 (多视图弹窗版)
-->
<script setup lang="ts">
import { ref, onMounted, nextTick, computed, watch } from 'vue';
import { MoreFilled } from '@element-plus/icons-vue';
import { icons } from '@/assets/icons';
import { ElMessage, ElMessageBox } from 'element-plus';
import { getMeetingList, getMeetingDetail, updateMeetingRecord, deleteMeeting, updateMeeting, type Meeting, type MeetingRecord } from '@/api/meeting';
import CreateMeetingView from './CreateMeetingView.vue';

// --- 组件状态 ---
const emit = defineEmits(['close']);
const currentView = ref('history'); // 'history': 历史记录, 'create': 创建, 'detail': 详情
const isLoading = ref(false);
const createViewRef = ref<InstanceType<typeof CreateMeetingView> | null>(null);

// --- 历史视图状态 ---
const historyList = ref<Meeting[]>([]);

// --- 详情视图状态 ---
const meetingDetail = ref<Meeting | null>(null);
const editingRecordId = ref<number | null>(null);
const editingContent = ref('');
const editBubbleRef = ref<HTMLElement | null>(null);

// 将发言记录按发言人分组
const groupedRecords = computed(() => {
  if (!meetingDetail.value || !meetingDetail.value.records) return [];

  const groups: { speaker_name: string; records: MeetingRecord[] }[] = [];
  let currentGroup: { speaker_name: string; records: MeetingRecord[] } | null = null;

  for (const record of meetingDetail.value.records) {
    if (!currentGroup || currentGroup.speaker_name !== record.speaker_name) {
      currentGroup = {
        speaker_name: record.speaker_name,
        records: [record],
      };
      groups.push(currentGroup);
    } else {
      currentGroup.records.push(record);
    }
  }
  return groups;
});

// --- 函数 ---

// 视图导航
const showHistory = async () => {
  isLoading.value = true;
  try {
    const res = await getMeetingList({}) as unknown as { items: Meeting[]; total: number; page: number; size: number };
    historyList.value = res?.items || []; // 确保 res.items 存在
    currentView.value = 'history';
  } catch (e) {
    ElMessage.error('加载历史记录失败');
  } finally {
    isLoading.value = false;
  }
};

const showFabOptions = ref(false);
const fileInputRef = ref<HTMLInputElement | null>(null);

const handleStartRecording = () => {
  showFabOptions.value = false;
  currentView.value = 'create';
  nextTick(() => {
    createViewRef.value?.startMicrophone();
  });
};

const handleStartUpload = () => {
  showFabOptions.value = false;
  fileInputRef.value?.click();
};

const handleFileSelect = (event: Event) => {
  const input = event.target as HTMLInputElement;
  if (input.files && input.files[0]) {
    const selectedFile = input.files[0];
    currentView.value = 'create';
    nextTick(() => {
      createViewRef.value?.setViewState('processing');
      createViewRef.value?.uploadAudioFile(selectedFile, (text) => {
        createViewRef.value?.setViewState('finished');
      });
    });
    input.value = '';
  }
};

const showDetail = async (id: number) => {
  isLoading.value = true;
  try {
    const detail = await getMeetingDetail(id) as unknown as Meeting;
    if (detail) {
      meetingDetail.value = detail;
      currentView.value = 'detail';
    } else {
      ElMessage.error('获取会议详情失败或数据格式错误');
      meetingDetail.value = null; // 清空旧数据
    }
  } catch (e) {
    ElMessage.error('加载详情失败');
  } finally {
    isLoading.value = false;
  }
};

// 编辑功能
const startEditing = (record: MeetingRecord) => {
  editingRecordId.value = record.id;
  editingContent.value = record.content;
};

const cancelEditing = () => {
  editingRecordId.value = null;
  editingContent.value = '';
};

const saveChanges = async () => {
  if (editingRecordId.value === null) return;

  try {
    await updateMeetingRecord({ record_id: editingRecordId.value, content: editingContent.value });
    ElMessage.success('更新成功');
    // 更新视图中的数据，以防用户后续不保存直接取消
    if (meetingDetail.value && meetingDetail.value.records) {
      const record = meetingDetail.value.records.find(r => r.id === editingRecordId.value);
      if (record) {
        record.content = editingContent.value;
      }
    }
    cancelEditing(); // 保存成功后退出编辑模式
  } catch (error) {
    ElMessage.error('更新失败');
  }
};

const handleRename = (meeting: Meeting) => {
  ElMessageBox.prompt('请输入新的会议标题', '重命名', {
    confirmButtonText: '确定',
    cancelButtonText: '取消',
    inputValue: meeting.meeting_title,
    inputValidator: (val) => !!val,
    inputErrorMessage: '标题不能为空',
  }).then(async ({ value }) => {
    try {
      await updateMeeting({ meeting_id: meeting.id, title: value });
      ElMessage.success('重命名成功');
      meeting.meeting_title = value; // 直接更新视图
    } catch (error) {
      ElMessage.error('重命名失败');
    }
  }).catch(() => {});
};

const handleCommand = (command: string, meeting: Meeting) => {
  if (command === 'rename') {
    handleRename(meeting);
  } else if (command === 'delete') {
    handleDelete(meeting.id);
  }
};

const handleDelete = (meetingId: number) => {
  ElMessageBox.confirm('确定要删除这个会议记录吗？此操作不可恢复。', '确认删除', {
    confirmButtonText: '删除',
    cancelButtonText: '取消',
    type: 'warning',
  }).then(async () => {
    try {
      await deleteMeeting(meetingId);
      ElMessage.success('删除成功');
      historyList.value = historyList.value.filter(m => m.id !== meetingId);
    } catch (error) {
      ElMessage.error('删除失败');
    }
  }).catch(() => {});
};

// --- 点击外部退出编辑的逻辑 ---
const handleOutsideClick = (event: MouseEvent) => {
  if (editBubbleRef.value && !editBubbleRef.value.contains(event.target as Node)) {
    cancelEditing();
  }
};

watch(editingRecordId, (newId, oldId) => {
  if (newId !== null && oldId === null) {
    // 进入编辑模式时，添加监听器
    nextTick(() => {
      document.addEventListener('click', handleOutsideClick, true);
    });
  } else if (newId === null && oldId !== null) {
    // 退出编辑模式时，移除监听器
    document.removeEventListener('click', handleOutsideClick, true);
  }
});


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
            <div v-for="item in historyList" :key="item.id" class="history-item">
              <div class="item-info" @click="showDetail(item.id)">
                <div class="item-title">{{ item.meeting_title }}</div>
                <div class="item-date">{{ new Date(item.start_time).toLocaleString() }}</div>
              </div>
              <div class="item-actions">
                <el-dropdown trigger="click" @command="(command) => handleCommand(command, item)">
                  <el-button type="info" :icon="MoreFilled" circle text />
                  <template #dropdown>
                    <el-dropdown-menu>
                      <el-dropdown-item command="rename">重命名</el-dropdown-item>
                      <el-dropdown-item command="delete" divided><span class="danger">删除</span></el-dropdown-item>
                    </el-dropdown-menu>
                  </template>
                </el-dropdown>
              </div>
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
           <h2>{{ meetingDetail.meeting_title }}</h2>
          <small>会议时间: {{ new Date(meetingDetail.start_time).toLocaleString() }}</small>

          <div class="detail-section">
            <h3>会议记录</h3>
            <div v-if="!groupedRecords.length" class="empty-records">
              <p>本次会议暂无发言记录。</p>
            </div>
            <div v-else class="records-list">
              <div v-for="(group, index) in groupedRecords" :key="index" class="speaker-group">
                <div class="speaker-info">
                  <span class="avatar">{{ group.speaker_name.charAt(0) }}</span>
                  <strong class="speaker-name">{{ group.speaker_name }}</strong>
                </div>
                <div class="speech-bubbles">
                  <div v-for="record in group.records" :key="record.id" class="bubble" @click="startEditing(record)">
                    <div v-if="editingRecordId === record.id" ref="editBubbleRef">
                      <el-input
                        v-model="editingContent"
                        type="textarea"
                        autosize
                      />
                      <div class="edit-actions">
                        <el-button type="primary" size="small" @click.stop="saveChanges">保存</el-button>
                        <el-button size="small" @click.stop="cancelEditing">取消</el-button>
                      </div>
                    </div>
                    <p v-else>{{ record.content }}</p>
                  </div>
                </div>
              </div>
            </div>
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
          <button class="fab-create-new" :class="{'rotated': showFabOptions}" @click="showFabOptions = !showFabOptions">
            <span v-html="icons.plus"></span>
          </button>
        </div>
        
        <!-- 文件输入框 -->
        <input type="file" ref="fileInputRef" @change="handleFileSelect" accept="audio/*" style="display: none" />
      </div>
    </div>
  </div>
</template>

<style scoped>
* {
  -webkit-tap-highlight-color: transparent; /* 移除移动端点击高亮 */
}
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
  margin-bottom: 0.75rem; transition: all 0.2s;
  display: flex; align-items: center; justify-content: space-between;
}
.item-info { flex: 1; cursor: pointer; }
.history-item:hover { transform: translateY(-2px); box-shadow: 0 4px 12px rgba(0,0,0,0.08); }

.el-dropdown-menu__item--divided { border-top: 1px solid #f2f3f5; }
.el-dropdown-menu__item:has(span.danger) { color: #f53f3f; }
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

/* 新增的编辑样式 */
.records-list { display: flex; flex-direction: column; gap: 1.5rem; }
.speaker-group { display: flex; gap: 1rem; }
.speaker-info { display: flex; flex-direction: column; align-items: center; gap: 0.5rem; }
.avatar { width: 2.5rem; height: 2.5rem; border-radius: 50%; background-color: #e5e6eb; color: #4e5969; display: flex; align-items: center; justify-content: center; font-weight: 600; }
.speaker-name { font-size: 0.875rem; color: #86909c; max-width: 4rem; text-align: center; }
.speech-bubbles { flex: 1; display: flex; flex-direction: column; gap: 0.5rem; }
.bubble {
  background-color: #f7f8fa;
  padding: 0.75rem 1rem;
  border-radius: 0.5rem;
  cursor: pointer;
  transition: background-color 0.2s;
}
.bubble p { margin: 0; white-space: pre-wrap; line-height: 1.6; }
.bubble:hover { background-color: #f2f3f5; }

.edit-actions {
  display: flex;
  justify-content: flex-end;
  gap: 0.5rem;
  margin-top: 0.75rem;
}
.empty-records { text-align: center; color: #86909c; padding: 4rem 0; }


/* 通用样式 */
.pill-btn { display: inline-flex; align-items: center; gap: 0.375rem; padding: 0.5rem 1rem; border-radius: 999px; border: 1px solid #e5e6eb; background: #ffffff; font-size: 0.875rem; cursor: pointer; }
.pill-btn.primary { border-color: #165dff; background: #165dff; color: #ffffff; }
.pill-btn:disabled { opacity: 0.5; cursor: not-allowed; }
.loading-spinner { width: 1.5rem; height: 1.5rem; border: 0.1875rem solid #165DFF; border-top-color: transparent; border-radius: 50%; animation: spin 1s linear infinite; }
@keyframes spin { to { transform: rotate(360deg); } }
@keyframes blink { 50% { opacity: 0; } }
</style>
