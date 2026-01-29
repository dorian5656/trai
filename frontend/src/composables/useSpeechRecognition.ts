// 文件名：frontend/src/composables/useSpeechRecognition.ts
// 作者：zcl
// 日期：2026-01-28
// 描述：语音识别组合式函数

import { ref, onUnmounted } from 'vue';
import { ElMessage } from 'element-plus';

export function useSpeechRecognition() {
  const isListening = ref(false);
  const result = ref('');
  const error = ref('');
  
  let recognition: any = null;

  // 初始化识别对象
  const initRecognition = () => {
    if ('webkitSpeechRecognition' in window || 'SpeechRecognition' in window) {
      // @ts-ignore
      const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
      recognition = new SpeechRecognition();
      recognition.continuous = false; // 单次识别
      recognition.interimResults = true; // 实时返回结果
      recognition.lang = 'zh-CN'; // 默认中文

      recognition.onstart = () => {
        isListening.value = true;
        error.value = '';
      };

      recognition.onresult = (event: any) => {
        let finalTranscript = '';
        let interimTranscript = '';

        for (let i = event.resultIndex; i < event.results.length; ++i) {
          if (event.results[i].isFinal) {
            finalTranscript += event.results[i][0].transcript;
          } else {
            interimTranscript += event.results[i][0].transcript;
          }
        }
        
        // 我们主要关注实时结果展示，最终结果在 onend 或手动停止时处理也可以
        // 这里简单将 interim 赋值给 result，如果是 final 则覆盖
        result.value = finalTranscript || interimTranscript;
      };

      recognition.onerror = (event: any) => {
        console.error('Speech recognition error', event.error);
        error.value = event.error;
        isListening.value = false;
        if (event.error === 'not-allowed') {
          ElMessage.error('无法访问麦克风，请检查权限设置');
        } else {
          ElMessage.error('语音识别出错: ' + event.error);
        }
      };

      recognition.onend = () => {
        isListening.value = false;
      };
    } else {
      ElMessage.warning('您的浏览器不支持语音识别功能');
    }
  };

  const startListening = () => {
    if (!recognition) initRecognition();
    if (recognition) {
      try {
        result.value = ''; // 清空之前的结果
        recognition.start();
      } catch (e) {
        console.error(e);
      }
    }
  };

  const stopListening = () => {
    if (recognition) {
      recognition.stop();
      isListening.value = false;
    }
  };

  const toggleListening = () => {
    if (isListening.value) {
      stopListening();
    } else {
      startListening();
    }
  };

  onUnmounted(() => {
    if (recognition) {
      recognition.stop();
    }
  });

  return {
    isListening,
    result,
    error,
    startListening,
    stopListening,
    toggleListening
  };
}
