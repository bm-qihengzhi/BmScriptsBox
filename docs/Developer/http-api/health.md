---
title: 健康检查 · /api/health
description: GET /api/health 检测盒子 HTTP 服务是否正常运行
status: 稳定
docType: reference
audience: 脚本开发者
docVersion: 0.3.0
---

# GET /api/health

> **调用前先探一下：盒子服务在不在？** 避免盒子没启动时请求失败。

检测盒子的本地 HTTP 服务是否正常运行。

脚本如果需要调用其他接口，可以先探一下这个地址，避免盒子没启动时请求失败。

---

## 请求

```bash
curl http://127.0.0.1:9527/api/health
```

---

## 响应

```json
{"status": "healthy", "service": "BmScriptsBox"}
```

---

## 在脚本中使用

```python
import sys, json, requests

payload = json.load(open(sys.argv[1], encoding='utf-8'))
api_base = payload["environment"]["api_base"]

try:
    requests.get(f"{api_base}/api/health", timeout=3)
except requests.RequestException:
    print("盒子服务未启动，无法调用联动接口")
    sys.exit(1)
```

---

## 相关文档

- 参数注入 → [参数注入](../parameter-passing)
- HTTP API 总览 → [HTTP API](../http-api/)