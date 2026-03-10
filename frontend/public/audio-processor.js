
// 文件名：frontend/public/audio-processor.js
// 作者：Gemini
// 日期：2026-03-06
// 描述：使用 AudioWorklet 在后台线程处理音频数据，进行重采样和格式转换。

/**
 * 将 Float32Array 转换为 Int16Array (16-bit PCM)
 * @param {Float32Array} buffer - 输入的浮点音频数据
 * @returns {Int16Array} - 输出的16位PCM音频数据
 */
const convertFloat32ToInt16 = (buffer) => {
  let l = buffer.length;
  const buf = new Int16Array(l);
  while (l--) {
    const value = buffer[l] ?? 0;
    let s = Math.max(-1, Math.min(1, value));
    buf[l] = s < 0 ? s * 0x8000 : s * 0x7FFF;
  }
  return buf;
};

/**
 * 对音频数据进行重采样
 * @param {Float32Array} buffer - 输入的浮点音频数据
 * @param {number} inputSampleRate - 输入采样率
 * @param {number} outputSampleRate - 目标采样率
 * @returns {Int16Array} - 重采样并转换为16位PCM后的音频数据
 */
const downsampleBuffer = (buffer, inputSampleRate, outputSampleRate) => {
  if (outputSampleRate === inputSampleRate) {
    return convertFloat32ToInt16(buffer);
  }
  const sampleRateRatio = inputSampleRate / outputSampleRate;
  const newLength = Math.round(buffer.length / sampleRateRatio);
  const result = new Int16Array(newLength);
  let offsetResult = 0;
  let offsetBuffer = 0;
  while (offsetResult < result.length) {
    const nextOffsetBuffer = Math.round((offsetResult + 1) * sampleRateRatio);
    let accum = 0,
      count = 0;
    for (let i = offsetBuffer; i < nextOffsetBuffer && i < buffer.length; i++) {
      accum += buffer[i];
      count++;
    }
    const value = count > 0 ? accum / count : 0;
    let s = Math.max(-1, Math.min(1, value));
    result[offsetResult] = s < 0 ? s * 0x8000 : s * 0x7FFF;
    offsetResult++;
    offsetBuffer = nextOffsetBuffer;
  }
  return result;
};

/**
 * AudioWorklet 处理器
 */
class AudioProcessor extends AudioWorkletProcessor {
  constructor() {
    super();
  }

  /**
   * 系统调用的主处理方法
   * @param {Float32Array[][]} inputs - 输入的音频数据块
   * @param {Float32Array[][]} outputs - 输出的音频数据块
   * @param {Record<string, Float32Array>} parameters - 其他参数
   * @returns {boolean} - 返回 true 以保持处理器活动状态
   */
  process(inputs, outputs, parameters) {
    // 我们只关心第一个输入的第一个声道
    const input = inputs[0];
    if (!input) {
      return true;
    }
    const channelData = input[0];
    if (!channelData) {
      return true;
    }

    // 将音频重采样到 16kHz 并转换为 16-bit PCM
    // sampleRate 是 AudioWorkletGlobalScope 中的一个全局可用变量
    const pcm16 = downsampleBuffer(channelData, sampleRate, 16000);

    // 将处理后的数据发送回主线程
    // 我们传递 buffer 的所有权（Transferable Object），以避免数据拷贝，提高性能
    if (pcm16.buffer.byteLength > 0) {
        this.port.postMessage(pcm16.buffer, [pcm16.buffer]);
    }

    // 返回 true 以便让浏览器继续调用此 process 方法
    return true;
  }
}

// 注册处理器，'audio-processor' 是我们在主线程中创建节点时使用的名称
registerProcessor('audio-processor', AudioProcessor);
