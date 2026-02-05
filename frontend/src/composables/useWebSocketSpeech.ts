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

export function useWebSocketSpeech() {
  const isConnected = ref(false);
  const isRecording = ref(false);
  const isProcessingFile = ref(false);
  const resultText = ref('');
  const interimText = ref('');
  const errorMsg = ref('');

  let ws: WebSocket | null = null;
  let audioContext: AudioContext | null = null;
  let processor: ScriptProcessorNode | null = null;
  let stream: MediaStream | null = null;
  let fileReaderInterval: any = null;

  // 初始化 WebSocket
  const connectWebSocket = (): Promise<void> => {
    return new Promise((resolve, reject) => {
      if (ws && ws.readyState === WebSocket.OPEN) {
        resolve();
        return;
      }

      try {
        ws = new WebSocket(WS_URL);
        ws.binaryType = 'arraybuffer';

        ws.onopen = () => {
          console.log('✅ WebSocket Connected');
          isConnected.value = true;
          errorMsg.value = '';
          resolve();
        };

        ws.onmessage = (event) => {
          try {
            const data = JSON.parse(event.data);
            if (data.text) {
              if (data.is_final) {
                resultText.value += data.text; // 累加最终结果
                interimText.value = ''; // 清空临时结果
              } else {
                interimText.value = data.text; // 更新临时结果
              }
            }
          } catch (e) {
            console.error('Failed to parse WebSocket message:', e);
          }
        };

        ws.onerror = (e) => {
          console.error('WebSocket Error:', e);
          errorMsg.value = 'WebSocket 连接错误';
          isConnected.value = false;
          reject(e);
        };

        ws.onclose = () => {
          console.log('WebSocket Closed');
          isConnected.value = false;
          isRecording.value = false;
          isProcessingFile.value = false;
        };
      } catch (e) {
        reject(e);
      }
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

  // 重采样并转换 float32 -> int16
  const downsampleBuffer = (buffer: Float32Array, sampleRate: number, outSampleRate: number): Int16Array => {
    if (outSampleRate === sampleRate) {
      return convertFloat32ToInt16(buffer);
    }
    const compression = sampleRate / outSampleRate;
    const length = buffer.length / compression;
    const result = new Int16Array(length);
    let index = 0;
    let j = 0;
    while (index < length) {
      const temp = buffer[Math.floor(j)] ?? 0; // 简单的最近邻插值，更好的方法是线性插值或滤波
      // floatTo16BitPCM
      let s = Math.max(-1, Math.min(1, temp));
      result[index] = s < 0 ? s * 0x8000 : s * 0x7FFF;
      index++;
      j += compression;
    }
    return result;
  };

  const convertFloat32ToInt16 = (buffer: Float32Array): Int16Array => {
    let l = buffer.length;
    let buf = new Int16Array(l);
    while (l--) {
      const value = buffer[l] ?? 0;
      let s = Math.max(-1, Math.min(1, value));
      buf[l] = s < 0 ? s * 0x8000 : s * 0x7FFF;
    }
    return buf;
  };

  // 开始麦克风录音
  const startMicrophone = async () => {
    try {
      resultText.value = '';
      interimText.value = '';
      await connectWebSocket();

      stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      audioContext = new (window.AudioContext || (window as any).webkitAudioContext)();
      const source = audioContext.createMediaStreamSource(stream);
      
      // 使用 ScriptProcessorNode (已被废弃但兼容性好) 或 AudioWorklet
      // 这里使用 ScriptProcessorNode 简单实现
      processor = audioContext.createScriptProcessor(4096, 1, 1);

      source.connect(processor);
      processor.connect(audioContext.destination);

      processor.onaudioprocess = (e) => {
        if (!ws || ws.readyState !== WebSocket.OPEN) return;
        
        const inputData = e.inputBuffer.getChannelData(0);
        // 重采样到 16000
        const pcm16 = downsampleBuffer(inputData, audioContext!.sampleRate, 16000);
        ws.send(pcm16.buffer);
      };

      isRecording.value = true;
    } catch (e: any) {
      console.error('Microphone Error:', e);
      ErrorHandler.showError(ErrorHandler.handleHttpError(e));
      closeWebSocket();
    }
  };

  // 停止麦克风录音
  const stopMicrophone = () => {
    if (processor && audioContext) {
      processor.disconnect();
      audioContext.close();
      processor = null;
      audioContext = null;
    }
    if (stream) {
      stream.getTracks().forEach(track => track.stop());
      stream = null;
    }
    isRecording.value = false;
    
    // 发送结束信号
    if (ws && ws.readyState === WebSocket.OPEN) {
      ws.send(JSON.stringify({ is_speaking: false }));
      // 延迟关闭，等待最后结果
      setTimeout(() => closeWebSocket(), 1000);
    }
  };

  // HTTP 文件上传转写
  const uploadAudioFile = async (file: File) => {
    if (isProcessingFile.value) return;
    
    try {
      isProcessingFile.value = true;
      resultText.value = '';
      interimText.value = '正在上传并转写中，请稍候...';

      const formData = new FormData();
      formData.append('file', file);

      // 调用后端 HTTP 接口 (自动鉴权)
      const res: any = await request.post('speech/transcribe', formData, {
        headers: {
          'Content-Type': 'multipart/form-data'
        },
        timeout: 100000 // 长超时
      });

      // request.ts 已经解包了 data
      // 后端返回结构: { text: "...", url: "...", id: "..." }
      if (res && res.text) {
        resultText.value = res.text;
        interimText.value = '';
        ElMessage.success('转写完成');
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
    isProcessingFile,
    resultText,
    interimText,
    errorMsg,
    startMicrophone,
    stopMicrophone,
    uploadAudioFile
  };
}
