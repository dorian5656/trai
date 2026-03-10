// 文件名：frontend/src/composables/useWebSocketSpeech.ts
// 作者：whf
// 日期：2026-02-03
// 描述：WebSocket 语音识别 (实时麦克风 + 文件流式)

import { ref } from 'vue';
import { ErrorHandler } from '@/utils/errorHandler';
import request from '@/utils/request';
import { WS_BASE_URL, API_BASE_URL } from '@/config';
import { ElMessage } from 'element-plus';

const WS_URL = `${WS_BASE_URL}${API_BASE_URL}/speech/ws/transcribe`;

export function useWebSocketSpeech(endpoint: string = '/speech/ws/transcribe') {
  const isConnected = ref(false);
  const isRecording = ref(false);
  const isPaused = ref(false); // 新增暂停状态
  const isConnecting = ref(false);
  const isProcessingFile = ref(false);
  const resultText = ref('');
  const interimText = ref('');
  const errorMsg = ref('');

  let ws: WebSocket | null = null;
  let audioContext: AudioContext | null = null;
  let workletNode: AudioWorkletNode | null = null;
  let stream: MediaStream | null = null;
  let source: MediaStreamAudioSourceNode | null = null;
  let heartbeatInterval: any = null; // 心跳定时器

  // 初始化 WebSocket
  const connectWebSocket = (): Promise<void> => {
    const candidates = (() => {
      const proto = location.protocol === 'https:' ? 'wss' : 'ws';
      const sameOrigin = `${proto}://${location.host}${API_BASE_URL}${endpoint}`;
      const primary = `${WS_BASE_URL}${API_BASE_URL}${endpoint}`;
      const arr = [primary, sameOrigin];
      return Array.from(new Set(arr));
    })();

    const tryIndex = (idx: number, resolve: () => void, reject: (e: any) => void) => {
      if (idx >= candidates.length) {
        reject(new Error('WebSocket 连接错误'));
        return;
      }
      const target: string = candidates[idx]!;
      try {
        ws = new WebSocket(target);
        ws.binaryType = 'arraybuffer';

        ws.onopen = () => {
          isConnected.value = true;
          errorMsg.value = '';
          resolve();
        };

        ws.onmessage = (event) => {
          try {
            const data = JSON.parse(event.data);

            if (data && typeof data.speaker !== 'undefined') {
              const { type, text, speaker, speaker_changed } = data;

              if (type === '1') {
                interimText.value = text;
              } else if (type === '0') {
                let prefix = '';
                
                if (speaker_changed) {
                  // 仅当说话人切换时，才换行并添加前缀
                  prefix = (resultText.value === '') ? `发言人 ${speaker}: ` : `\n发言人 ${speaker}: `;
                }
                
                resultText.value += prefix + text;
                interimText.value = '';
              }
            }
          } catch (e) {
            console.error('解析消息失败:', e);
          }
        };

        ws.onerror = (e) => {
          isConnected.value = false;
          errorMsg.value = 'WebSocket 连接错误';
          try { ws?.close(); } catch {}
          ws = null;
          if (idx + 1 < candidates.length) {
            tryIndex(idx + 1, resolve, reject);
          } else {
            const err = new Error('网络连接异常：无法建立语音实时录音通道，请检查后端服务是否已启动以及端口配置');
            errorMsg.value = err.message;
            reject(err);
          }
        };

        ws.onclose = () => {
          isConnected.value = false;
          isRecording.value = false;
      isPaused.value = false; // 关闭时重置暂停状态
          isProcessingFile.value = false;
        };
      } catch (e) {
        tryIndex(idx + 1, resolve, reject);
      }
    };

    return new Promise((resolve, reject) => {
      if (ws && ws.readyState === WebSocket.OPEN) {
        resolve();
        return;
      }
      tryIndex(0, resolve, reject);
    });
  };

  // 关闭 WebSocket
  const closeWebSocket = () => {
    if (ws) {
      ws.close();
      ws = null;
    }
    isConnected.value = false;
  };

  // 开始麦克风录音
  const startMicrophone = async () => {
    try {
      if (isRecording.value || isConnecting.value) {
        return;
      }
      isConnecting.value = true;
      resultText.value = '';
      interimText.value = '';
      await connectWebSocket();

      stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      audioContext = new (window.AudioContext || (window as any).webkitAudioContext)();
      
      // 加载 AudioWorklet 模块
      try {
        await audioContext.audioWorklet.addModule('/audio-processor.js');
      } catch (e) {
        console.error('加载 AudioWorklet 模块失败:', e);
        ElMessage.error('加载音频处理模块失败，请刷新页面重试。');
        throw e;
      }

      source = audioContext.createMediaStreamSource(stream);
      workletNode = new AudioWorkletNode(audioContext, 'audio-processor');

      // 监听来自 worklet 的消息（处理后的音频数据）
      workletNode.port.onmessage = (event) => {
        if (isPaused.value || !ws || ws.readyState !== WebSocket.OPEN) return;
        // event.data is the ArrayBuffer of the Int16Array
        ws.send(event.data);
      };
      
      source.connect(workletNode);

      isRecording.value = true;
      isPaused.value = false; // 开始时确保不是暂停状态
    } catch (e: any) {
      console.error('Microphone Error:', e);
      if (e && (e.message === '网络连接异常：无法建立语音实时录音通道，请检查后端服务是否已启动以及端口配置' || e.message === 'WebSocket 连接错误')) {
        ElMessage.closeAll();
        ElMessage.error(e.message);
      } else {
        ErrorHandler.showError(ErrorHandler.handleHttpError(e));
      }
      closeWebSocket();
    } finally {
      isConnecting.value = false;
    }
  };

  // 暂停麦克风
  const pauseMicrophone = () => {
    if (!isRecording.value || isPaused.value) return;
    isPaused.value = true;
    // 发送暂停信令到后端
    if (ws && ws.readyState === WebSocket.OPEN) {
      ws.send(JSON.stringify({ action: 'pause' }));
    }
  };

  // 恢复麦克风
  const resumeMicrophone = () => {
    if (!isRecording.value || !isPaused.value) return;
    isPaused.value = false;
    // 发送恢复信令到后端
    if (ws && ws.readyState === WebSocket.OPEN) {
      ws.send(JSON.stringify({ action: 'resume' }));
    }
  };

  // 停止麦克风录音
  const stopMicrophone = (onStop?: (finalText: string) => void) => {
    if (stream) {
      stream.getTracks().forEach(track => track.stop());
      stream = null;
    }
    if (audioContext) {
      audioContext.close().then(() => {
        audioContext = null;
      });
    }
    source = null;
    workletNode = null;

    isRecording.value = false;
    isPaused.value = false;
    // 清除可能存在的心跳
    if (heartbeatInterval) {
      clearInterval(heartbeatInterval);
      heartbeatInterval = null;
    }
    
    // 发送结束信号
    if (ws && ws.readyState === WebSocket.OPEN) {
      ws.send(JSON.stringify({ is_speaking: false }));
      // 延迟关闭，等待最后结果
      setTimeout(() => {
        if (onStop) {
          onStop(resultText.value);
        }
        closeWebSocket();
      }, 1000);
    } else if (onStop) {
      // 如果 ws 已经关闭，直接回调
      onStop(resultText.value);
    }
  };

  // HTTP 文件上传转写
  const uploadAudioFile = async (file: File, onComplete?: (text: string) => void) => {
    if (isProcessingFile.value) return;
    
    // 调试日志
    console.log('uploadAudioFile 被调用:', file);
    console.log('文件信息:', file.name, file.size, file.type);
    
    try {
      isProcessingFile.value = true;
      resultText.value = '';
      interimText.value = '正在上传并转写中，请稍候...';

      const formData = new FormData();
      formData.append('file', file);
      
      // 验证 FormData
      console.log('FormData 内容:');
      for (const [key, value] of formData.entries()) {
        console.log(key, value);
      }

      // 调用后端 HTTP 接口 (自动鉴权)
      // 注意：Content-Type 由请求拦截器自动处理，不需要手动设置
      const res: any = await request.post('speech/transcribe', formData, {
        timeout: 100000 // 长超时
      });

      // 调试日志
      console.log('后端返回的原始数据:', res);

      // request.ts 已经解包了 data
      // 后端返回结构: { text: "...", url: "...", id: "..." }
      if (res && res.text) {
        resultText.value = res.text;
        interimText.value = '';
        ElMessage.success('转写完成');
        if (onComplete) {
          onComplete(res.text);
        }
      } else {
        throw new Error('未返回有效识别结果');
      }

    } catch (e: any) {
      console.error('Upload Error:', e);
      ErrorHandler.showError(ErrorHandler.handleHttpError(e));
      interimText.value = '';
      errorMsg.value = e.message;
    } finally {
      isProcessingFile.value = false;
    }
  };

  return {
    isConnected,
    isRecording,
    isPaused,
    isConnecting,
    isProcessingFile,
    resultText,
    interimText,
    errorMsg,
    startMicrophone,
    pauseMicrophone,
    resumeMicrophone,
    stopMicrophone,
    uploadAudioFile
  };
}
