# API 认证与用户管理测试记录

> 测试时间: 2026-02-04
> 测试环境: trai_31014_whf_trai_pro_20260202
> 测试账号: A0005 (普通用户) / A6666 (超级管理员)

## 1. 用户注册 (Register)

**请求:**
```bash
curl -X POST "http://localhost:5778/api_trai/v1/auth/register" \
     -H "Content-Type: application/json" \
     -d '{
           "username": "A0005",
           "password": "123456",
           "full_name": "测试用户005",
           "email": "test005@example.com",
           "phone": "13800000005"
         }'
```

**响应:**
```json
{"msg":"注册成功，请等待管理员审核","username":"A0005"}
```

## 2. 管理员审核 (Audit)

> 注意: 需要使用超级管理员 (A6666) 的 Token

**请求:**
```bash
# 获取管理员 Token
# curl -X POST "http://localhost:5778/api_trai/v1/auth/login/json" -H "Content-Type: application/json" -d '{"username": "A6666", "password": "123456"}'

curl -X POST "http://localhost:5778/api_trai/v1/users/audit" \
     -H "Content-Type: application/json" \
     -H "Authorization: Bearer <ADMIN_TOKEN>" \
     -d '{
           "username": "A0005",
           "is_active": true,
           "remark": "自动化测试审核通过"
         }'
```

**响应:**
```json
{"msg":"用户 A0005 审核已通过"}
```

## 3. 用户登录 (Login JSON)

**请求:**
```bash
curl -X POST "http://localhost:5778/api_trai/v1/auth/login/json" \
     -H "Content-Type: application/json" \
     -d '{"username": "A0005", "password": "123456"}'
```

**响应:**
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer"
}
```

## 4. 修改密码 (Change Password)

**请求:**
```bash
curl -X POST "http://localhost:5778/api_trai/v1/users/change-password" \
     -H "Content-Type: application/json" \
     -H "Authorization: Bearer <USER_TOKEN>" \
     -d '{
           "old_password": "123456",
           "new_password": "1234567",
           "reason": "定期修改密码"
         }'
```

**响应:**
```json
{"msg":"密码修改成功"}
```

> 注意: 新密码长度至少需要 6 位。

## 5. 获取当前用户信息 (Get Me)

**请求:**
```bash
curl -X GET "http://localhost:5778/api_trai/v1/users/me" \
     -H "Authorization: Bearer <USER_TOKEN>"
```

**响应:**
```json
{
  "username": "A0005",
  "full_name": "测试用户005",
  "email": "test005@example.com",
  "phone": "13800000005",
  "wecom_userid": null,
  "avatar": null,
  "id": "ff33b674-cb2e-41ca-96d5-035d6297a4ba",
  "is_active": true,
  "is_superuser": false,
  "source": "local",
  "created_at": "2026-02-04 01:19:32"
}
```

## 6. 文件上传 (Upload Common)

**请求:**
```bash
curl -X POST "http://localhost:5778/api_trai/v1/upload/common" \
     -H "Authorization: Bearer <USER_TOKEN>" \
     -F "file=@test_upload.txt" \
     -F "module=test"
```

**响应:**
```json
{
  "url": "http://192.168.0.190:12001/trai_images/test/20260204/49fed565ff7147f7afb6de5866523519.txt",
  "filename": "test_upload.txt",
  "size": 28,
  "content_type": "text/plain",
  "local_path": "test/20260204/49fed565ff7147f7afb6de5866523519.txt"
}
```

## 7. 监控 - GPU 环境 (Monitor GPU)

**请求:**
```bash
curl -X POST "http://localhost:5778/api_trai/v1/monitor/env/gpu"
```

**响应:**
```json
{
  "code": 200,
  "msg": "OK",
  "data": {
    "nvidia_smi": {
      "available": true,
      "driver_version": "590.44.01",
      "cuda_version": "13.1",
      "gpu_count": 4,
      "gpus": [
        {
          "product_name": "NVIDIA L20",
          "uuid": "GPU-d68d6686-bf05-6d89-4b10-17290999a680",
          "memory": {
            "total": "46068 MiB",
            "used": "16487 MiB",
            "free": "28974 MiB"
          },
          "utilization": {
            "gpu": "0 %",
            "memory": "0 %"
          },
          "temperature": "70 C"
        },
        // ... (其他 GPU 信息)
      ]
    },
    "torch": {
      "cuda_available": true,
      "device_count": 4,
      "device_name": "NVIDIA L20",
      "version": "2.10.0+cu128"
    },
    "paddle": {
      "available": true,
      "device": "gpu:2",
      "version": "2.5.2"
    },
    "system_cuda": "Not Set"
  },
  "ts": "2026-02-04 09:23:06"
}
```

## 8. 监控 - 系统资源 (Monitor System)

**请求:**
```bash
curl -X POST "http://localhost:5778/api_trai/v1/monitor/env/system"
```

**响应:**
```json
{
  "code": 200,
  "msg": "OK",
  "data": {
    "cpu": {
      "percent": 4.5,
      "cores": 128
    },
    "memory": {
      "total_gb": 1007.01,
      "available_gb": 878.32,
      "percent": 12.8
    },
    "disk": {
      "total_gb": 10239.83,
      "free_gb": 5422.59,
      "used_gb": 4817.24
    }
  },
  "ts": "2026-02-04 09:22:58"
}
```

## 9. AI 对话 (Chat Completions)

**请求:**
```bash
curl -X POST "http://localhost:5778/api_trai/v1/ai/chat/completions" \
     -H "Content-Type: application/json" \
     -H "Authorization: Bearer <USER_TOKEN>" \
     -d '{
           "model": "deepseek-chat",
           "messages": [
             {"role": "user", "content": "你好，请介绍一下你自己"}
           ],
           "temperature": 0.7
         }'
```

**响应:**
```json
{
  "code": 200,
  "msg": "OK",
  "data": {
    "reply": "你好！我是DeepSeek...",
    "model": "deepseek-chat",
    "usage": {
      "prompt_tokens": 9,
      "completion_tokens": 280,
      "total_tokens": 289
    },
    "session_id": "68020a8e-be93-4cef-b3d4-fd2961ff9daf"
  },
  "ts": "2026-02-04 09:27:15"
}
```

## 10. AI 文生图 (Image Generation)

**请求:**
```bash
curl -X POST "http://localhost:5778/api_trai/v1/ai/image/generations" \
     -H "Content-Type: application/json" \
     -H "Authorization: Bearer <USER_TOKEN>" \
     -d '{
           "prompt": "一只在太空中飞翔的猫，赛博朋克风格",
           "size": "1024x1024",
           "n": 1
         }'
```

**响应:**
```json
{
  "code": 200,
  "msg": "OK",
  "data": {
    "created": 1770168493,
    "data": [
      {
        "url": "http://192.168.0.190:12001/trai_images/gen/20260204/26533eec9fb441d5a4f29f44a993c555.png"
      }
    ]
  },
  "ts": "2026-02-04 09:28:13"
}
```

## 11. 客户留资 (Contact Lead)

**请求:**
```bash
curl -X POST "http://localhost:5778/api_trai/v1/contact/lead" \
     -H "Content-Type: application/json" \
     -H "Authorization: Bearer <USER_TOKEN>" \
     -d '{
           "name": "测试客户",
           "phone": "13900000001",
           "product": "AI智能助手",
           "region": "上海",
           "submitTime": "2026-02-04T09:30:00"
         }'
```

**响应:**
```json
{
  "code": 200,
  "msg": "提交成功",
  "data": {
    "id": 15
  }
}
```

## 12. Dify 代理对话 (Chat)

**请求:**
```bash
curl -X POST "http://localhost:5778/api_trai/v1/dify/chat" \
     -H "Content-Type: application/json" \
     -H "Authorization: Bearer <USER_TOKEN>" \
     -d '{
           "query": "你好，请介绍一下你自己 (来自测试)",
           "user": "A0005",
           "app_name": "guanwang"
         }'
```

**响应:**
> (SSE 流式响应，内容较长，截取部分)
```json
data: {"event": "message", "conversation_id": "...", "answer": "你好", ...}
...
data: {"event": "message_end", ...}
```

## 13. 语音转写 (ASR Transcribe)

**请求:**
```bash
curl -X POST "http://localhost:5778/api_trai/v1/speech/transcribe" \
     -H "Authorization: Bearer <USER_TOKEN>" \
     -F "file=@test_audio.wav"
```

**响应:**
> (注: 示例为模拟空音频的响应，实际应返回转写文本)
```json
{"code":500,"msg":"处理失败: stack expects a non-empty TensorList"}
```

## 14. 人人都是品牌官 - GPU 检查 (Check GPU)

**请求:**
```bash
curl -X GET "http://localhost:5778/api_trai/v1/rrdsppg/check_gpu"
```

**响应:**
```json
{
  "code": 200,
  "msg": "OK",
  "data": {
    "torch": {
      "available": true,
      "device_count": 4,
      "device_name": "NVIDIA L20",
      "version": "2.10.0+cu128"
    },
    "paddle": {
      "available": true,
      "device": "gpu:2",
      "version": "2.5.2"
    }
  },
  "ts": "2026-02-04 09:37:08"
}
```

## 15. 人人都是品牌官 - 预测 (Predict)

**请求:**
```bash
curl -X POST "http://localhost:5778/api_trai/v1/rrdsppg/predict" \
     -H "Content-Type: application/json" \
     -d '{
           "taskId": 12345,
           "userId": 67890,
           "type": 1997929948761825282,
           "templatePath": "http://example.com/template.jpg",
           "targetPath": "http://example.com/target.jpg"
         }'
```

**响应:**
```json
{
  "code": 200,
  "msg": "OK",
  "data": {
    "similarity_score": 0.0
  },
  "ts": "2026-02-04 09:37:21"
}
```
