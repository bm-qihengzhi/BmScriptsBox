---
title: 发送通知 · /api/notify
description: POST /api/notify 向用户发送桌面气泡通知——请求参数、headers、curl 与脚本内调用示例
status: 稳定
docType: reference
audience: 脚本开发者
docVersion: 0.3.0
---

# POST /api/notify

> **静默脚本跑完了，用一条桌面气泡告诉用户结果——不打扰也不失联。**

向用户发送桌面气泡通知。

这个接口对 `terminal = "never"` 的静默脚本特别有用——脚本在后台跑完，用一条气泡告诉用户结果，不打扰也不失联。

---

## 请求

```bash
POST http://127.0.0.1:9527/api/notify
```

**Headers**

| 字段 | 值 |
| --- | --- |
| Content-Type | `application/json` |

**Body 参数**

| 字段 | 类型 | 必填 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| `notify_type` | 字符串 | 是 | — | 通知类型：`success`、`error`、`info` |
| `message` | 字符串 | 否 | `null` | 通知内容 |
| `duration` | 整数 | 否 | `5000` | 通知显示时长，单位毫秒 |
| `show_close` | 布尔值 | 否 | `false` | 是否显示关闭按钮 |

---

## 请求示例

```bash
curl -X POST http://127.0.0.1:9527/api/notify \
  -H "Content-Type: application/json" \
  -d '{"notify_type": "success", "message": "任务完成"}'
```

**在脚本中调用**

```python
import json, sys, requests

payload = json.load(open(sys.argv[1], encoding='utf-8'))
api_base = payload["environment"]["api_base"]

requests.post(f"{api_base}/api/notify", json={
    "notify_type": "success",
    "message": f"已处理 {count} 个文件",
    "duration": 3000,
})
```

---

## 响应

成功：

```json
{"success": true}
```

请求格式错误（非 JSON）：

```json
{"error": "Content-Type must be application/json"}
```

---

## 相关文档

- 终端模式选择 → [终端模式详解](../terminal-mode)
- 静默通知的推荐用法 → [脚本开发原则](../dev-principles)