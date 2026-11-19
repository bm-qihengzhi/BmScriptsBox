---
title: HTTP API
description: 盒子本地 HTTP 服务（127.0.0.1:9527）的 5 个接口一览，覆盖触发脚本、串联调用、查模型路径与发送通知。
status: 稳定
docType: reference
audience: 脚本开发者
docVersion: 0.3.0
---

# HTTP API

> **盒子在本地开了一个 HTTP 服务（`127.0.0.1:9527`），你的脚本可以直接调它——触发其他脚本、查模型路径、发通知。**

盒子启动时会运行一个本地 HTTP 服务（Flask，默认端口 **9527**）。你的脚本在运行期间可以通过它触发其他脚本、查询模型路径、给用户发通知。

> 接口仅供本地调用，默认不监听外部网络，也**不需要任何令牌**。
>
> 统一 Base URL：`http://127.0.0.1:9527`

---

## 接口一览

| 接口 | 方法 | 说明 | 谁会用到 |
| --- | --- | --- | --- |
| [/api/execute](./execute) | POST | 触发任意脚本执行，支持同步和异步 | 外部程序、定时任务、脚本自调 |
| [/api/link](./link) | POST | 脚本串联专用，只放行节点，恒为同步 | 脚本 A 调脚本 B |
| [/api/model/path](./model-path) | GET | 查询已下载模型的文件夹路径 | 用到 AI 模型的脚本 |
| [/api/notify](./notify) | POST | 发送桌面气泡通知 | 静默执行的脚本告知用户结果 |
| [/api/health](./health) | GET | 健康检查 | 确认盒子服务是否在跑 |

---

## 怎么用

盒子的地址不用硬编码。每次启动脚本，盒子都会把地址注入参数文件的 `environment.api_base`：

```python
import json, sys, requests

payload = json.load(open(sys.argv[1], encoding='utf-8'))
api_base = payload["environment"]["api_base"]     # http://127.0.0.1:9527

requests.post(f"{api_base}/api/notify", json={"notify_type": "success", "message": "处理完成"})
```

详见 [脚本运行机制](../run-mechanism) 与 [参数注入](../parameter-passing)。

脚本联动（A 调 B）用的是 `/api/link`，完整机制见 [脚本联动](../script-linking)。

---

## 通用约定

- 请求与响应均为 **JSON**（除 `/api/execute` 额外支持 `application/x-www-form-urlencoded`）
- 端口固定 `9527`，目前不可配置
- 所有接口都只在 `127.0.0.1` 上监听，外部机器访问不到

---

## 相关文档

- 脚本联动完整机制 → [脚本联动](../script-linking)
- 参数注入 → [参数注入](../parameter-passing)