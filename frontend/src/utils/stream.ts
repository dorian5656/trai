// 文件名：frontend/src/utils/stream.ts
// 作者：zcl
// 日期：2026-01-28
// 描述：流式请求工具 (封装 fetch SSE)

import { useChatStore } from '@/stores/chat';

/**
 * 发送流式对话请求
 * @param message 用户输入的消息
 * @param onMessage 接收到片段时的回调
 * @param onDone 完成时的回调
 * @param onError 错误时的回调
 */
export async function streamChat(
  message: string,
  onMessage: (text: string) => void,
  onDone: () => void,
  onError: (err: Error) => void
) {
  const chatStore = useChatStore();
  const controller = new AbortController();
  chatStore.abortController = controller;

  try {
    const token = localStorage.getItem('token') || '';
    const baseURL = (import.meta.env.VITE_APP_SERVER_URL || '') + (import.meta.env.VITE_APP_BASE_URL || '/api');
    
    const response = await fetch(`${baseURL}/ai/chat/completions/stream`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${token}`,
      },
      body: JSON.stringify({
        messages: [{ role: 'user', content: message }], 
        model: 'deepseek-chat', // 默认模型
        stream: true,
      }),
      signal: controller.signal,
    });

    if (!response.ok) {
        const errText = await response.text();
        throw new Error(`Request failed: ${response.status} ${errText}`);
    }

    if (!response.body) {
      throw new Error('ReadableStream not supported in this browser.');
    }

    const reader = response.body.getReader();
    const decoder = new TextDecoder('utf-8');
    let done = false;
    let fullText = '';
    let buffer = '';

    while (!done) {
      const { value, done: doneReading } = await reader.read();
      done = doneReading;
      const chunkValue = decoder.decode(value, { stream: !done });
      buffer += chunkValue;

      const lines = buffer.split('\n');
      buffer = lines.pop() || ''; // 保留未完整的行

      for (const line of lines) {
        if (line.trim() === '') continue;
        
        if (line.startsWith('data: ')) {
          const dataStr = line.slice(6);
          
          if (dataStr === '[DONE]') {
            done = true;
            break;
          }
          
          // 尝试解析 JSON，如果失败则直接作为文本
          // 兼容后端可能返回 JSON ({"content":...}) 或 纯文本
          try {
            const data = JSON.parse(dataStr);
            // 兼容 OpenAI 格式
            const content = data.choices?.[0]?.delta?.content || data.content || '';
            if (content) {
              fullText += content;
              onMessage(fullText);
            }
          } catch (e) {
             // 非 JSON，直接追加文本
             // 注意：如果是纯文本流，dataStr 就是内容
             fullText += dataStr;
             onMessage(fullText);
          }
        }
      }
    }

    onDone();
  } catch (error: any) {
    if (error.name === 'AbortError') {
      console.log('Stream aborted');
    } else {
      onError(error);
    }
  } finally {
    chatStore.abortController = null;
  }
}

/**
 * 发送图片识别流式请求
 * @param params 请求参数 (ImageChatRequest)
 * @param onMessage 接收到消息片段回调 (累加文本)
 * @param onDone 完成回调
 * @param onError 错误回调
 */
export async function streamImageChat(
  params: any, // ImageChatRequest
  onMessage: (text: string) => void,
  onDone: () => void,
  onError: (err: Error) => void
) {
  const chatStore = useChatStore();
  const controller = new AbortController();
  chatStore.abortController = controller;

  try {
    const baseURL = (import.meta.env.VITE_APP_SERVER_URL || '') + (import.meta.env.VITE_APP_BASE_URL || '/api');
    const token = localStorage.getItem('token') || '';
    
    const response = await fetch(`${baseURL}/ai/image/chat/image/stream`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${token}`,
      },
      body: JSON.stringify(params),
      signal: controller.signal,
    });

    if (!response.ok) {
      const errText = await response.text();
      throw new Error(`Request failed: ${response.status} ${errText}`);
    }

    if (!response.body) {
      throw new Error('ReadableStream not supported.');
    }

    const reader = response.body.getReader();
    const decoder = new TextDecoder('utf-8');
    let done = false;
    let fullText = '';
    let buffer = '';

    while (!done) {
      const { value, done: doneReading } = await reader.read();
      done = doneReading;
      const chunkValue = decoder.decode(value, { stream: !done });
      buffer += chunkValue;

      const lines = buffer.split('\n');
      buffer = lines.pop() || '';

      for (const line of lines) {
        if (line.trim() === '') continue;
        
        // 兼容 "data: " 和 "data:" (无空格)
        if (line.startsWith('data:')) {
          // 移除前缀，并保留原始空格（如果有的话，除了 data: 后的第一个空格）
          // data: 这张 -> dataStr = "这张"
          // data:这张 -> dataStr = "这张"
          // data:  这张 -> dataStr = " 这张"
          
          let dataStr = '';
          if (line.startsWith('data: ')) {
             dataStr = line.slice(6);
          } else {
             dataStr = line.slice(5);
          }
          
          if (dataStr === '[DONE]') {
            done = true;
            break;
          }
          
          try {
            // 截图显示后端返回的可能是纯文本（非JSON），且包含 "message" 这样的前缀（但截图里没看到前缀，只看到 Type 是 message）
            // 截图显示 data 就是具体的文本内容，例如 "这张", "图片", "展示" 等
            // 如果后端直接返回的是 data: 文本内容，而不是 data: {"key": "val"}
            // 我们先尝试 JSON 解析，如果解析失败，或者解析出来不是对象，则直接视为文本内容
            
            let content = '';
            // 只有当看起来像 JSON 对象时才尝试解析 (以 { 开头)
            if (dataStr.trim().startsWith('{')) {
               try {
                  const data = JSON.parse(dataStr);
                  content = data.reply || data.content || data.choices?.[0]?.delta?.content || '';
               } catch (jsonErr) {
                  // JSON 解析失败，说明 dataStr 本身就是纯文本内容
                  content = dataStr;
               }
            } else {
               // 不像 JSON，直接作为文本
               content = dataStr;
            }

            if (content) {
              fullText += content;
              onMessage(fullText);
            }
          } catch (e) {
             console.error('Stream parse error:', e);
          }
        }
      }
    }

    onDone();
  } catch (error: any) {
    if (error.name === 'AbortError') {
      console.log('Stream aborted');
    } else {
      onError(error);
    }
  } finally {
    chatStore.abortController = null;
  }
}

/**
 * 模拟流式回复 (无后端时测试用)
 */
export async function mockStreamChat(
  message: string,
  onMessage: (text: string) => void,
  onDone: () => void
) {
  const chatStore = useChatStore();
  const controller = new AbortController();
  chatStore.abortController = controller;

  const responseText = `收到你的消息：“${message}”。\n\n这是一个 **模拟的流式回复**。\n\n这里有一段代码示例：\n\`\`\`python\nprint("Hello World")\n\`\`\`\n\n- 第一点\n- 第二点`;
  let currentText = '';
  
  const chars = responseText.split('');
  
  for (let i = 0; i < chars.length; i++) {
    if (controller.signal.aborted) break;
    
    await new Promise(resolve => setTimeout(resolve, 50)); // 模拟延迟
    currentText += chars[i];
    onMessage(currentText);
  }
  
  if (!controller.signal.aborted) {
    onDone();
  }
  chatStore.abortController = null;
}

/**
 * 发送 Dify 流式对话请求
 * @param params 请求参数
 * @param onMessage 接收到消息片段回调 (累加文本)
 * @param onThought 接收到思考过程回调 (可选)
 * @param onDone 完成回调
 * @param onError 错误回调
 */
export async function streamDifyChat(
  params: {
    query: string;
    user: string;
    conversation_id?: string;
    inputs?: Record<string, any>;
    app_name?: string;
    mode?: string; // 新增 mode
    isPublic?: boolean; // 新增：是否使用公开接口 (无Token)
  },
  onMessage: (text: string, conversationId?: string) => void,
  onDone: () => void,
  onError: (err: Error) => void,
  onThought?: (thought: string) => void
) {
  const chatStore = useChatStore();
  const controller = new AbortController();
  chatStore.abortController = controller;

  try {
    const baseURL = (import.meta.env.VITE_APP_SERVER_URL || '') + (import.meta.env.VITE_APP_BASE_URL || '/api');
    
    // 确定 URL 和 Headers
    const url = params.isPublic ? '/dify/chat/public' : '/dify/chat';
    const headers: Record<string, string> = {
      'Content-Type': 'application/json',
    };

    // 只有非公开接口才需要 Token
    if (!params.isPublic) {
      const token = localStorage.getItem('token') || '';
      if (token) {
        headers['Authorization'] = `Bearer ${token}`;
      }
    }
    
    const response = await fetch(`${baseURL}${url}`, {
      method: 'POST',
      headers: headers,
      body: JSON.stringify({
        query: params.query,
        user: params.user,
        conversation_id: params.conversation_id,
        inputs: params.inputs || {},
        app_name: params.app_name || 'guanwang'
      }),
      signal: controller.signal,
    });

    if (!response.ok) {
      const errText = await response.text();
      throw new Error(`Request failed: ${response.status} ${errText}`);
    }

    if (!response.body) {
      throw new Error('ReadableStream not supported.');
    }

    const reader = response.body.getReader();
    const decoder = new TextDecoder('utf-8');
    let done = false;
    let fullText = '';
    let fullThought = '';
    let buffer = '';

    while (!done) {
      const { value, done: doneReading } = await reader.read();
      done = doneReading;
      const chunkValue = decoder.decode(value, { stream: !done });
      buffer += chunkValue;

      // 后端使用 aiter_lines() 可能会吃掉换行符，或者导致不规则的切分
      // 这里尝试更鲁棒的解析方式：查找 "data: " 标记
      
      // 如果 buffer 中包含 "data: "，则开始处理
      let dataIndex = buffer.indexOf('data: ');
      while (dataIndex !== -1) {
          // 找到下一个 "data: " 的位置
          const nextDataIndex = buffer.indexOf('data: ', dataIndex + 6);
          
          let line = '';
          if (nextDataIndex !== -1) {
              // 截取当前这条 data
              line = buffer.slice(dataIndex, nextDataIndex);
              // 更新 buffer，移除已处理部分
              buffer = buffer.slice(nextDataIndex);
              // 重置 dataIndex 为 0，因为 buffer 已经更新，下一个 data 就在开头
              dataIndex = 0; 
          } else {
              // 如果没有下一个 "data: "，说明当前 buffer 结尾可能是不完整的数据
              // 或者已经是最后一条数据了。
              // 但是我们无法确定是否完整，除非 done 为 true
              if (done) {
                  line = buffer.slice(dataIndex);
                  buffer = '';
                  dataIndex = -1;
              } else {
                  // 数据不完整，等待下一次 chunk
                  break;
              }
          }
          
          // 处理截取出来的 line
          const dataStr = line.trim();
          if (dataStr.startsWith('data: ')) {
             const jsonStr = dataStr.slice(6);
             if (jsonStr === '[DONE]') {
                 done = true;
                 break;
             }
             
             try {
                const data = JSON.parse(jsonStr);
                const event = data.event;
                
                if (event === 'message' || event === 'agent_message') {
                  const answer = data.answer || '';
                  if (answer) {
                    fullText += answer;
                    onMessage(fullText, data.conversation_id);
                  }
                } else if (event === 'agent_thought' && onThought) {
                    const thought = data.thought || '';
                    if (thought) {
                        fullThought += thought;
                        onThought(fullThought);
                    }
                } else if (event === 'message_end') {
                    // 结束
                } else if (event === 'error') {
                    throw new Error(data.message || 'Dify Error');
                }
             } catch (e) {
                 // console.warn('Parse Dify chunk error:', e);
             }
          }
          
          // 继续查找下一个 (如果刚才 break 了这里就不会执行)
          if (nextDataIndex !== -1) {
              dataIndex = buffer.indexOf('data: ');
          } else {
              dataIndex = -1;
          }
      }
    }

    onDone();
  } catch (error: any) {
    if (error.name === 'AbortError') {
      console.log('Stream aborted');
    } else {
      onError(error);
    }
  } finally {
    chatStore.abortController = null;
  }
}
