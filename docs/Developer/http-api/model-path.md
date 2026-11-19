---
title: 查询模型路径 · /api/model/path
description: GET /api/model/path 根据 repo_id 查询本地已下载模型的文件夹路径
status: 稳定
docType: reference
audience: 脚本开发者
docVersion: 0.3.0
---

# GET /api/model/path

> **脚本加载模型前，先查一下它下载到哪了——一个 repo_id 就能拿到文件夹路径。**

根据 `repo_id` 查询本地已下载模型的**文件夹路径**。脚本拿到文件夹后，自行拼接具体模型文件名。

模型的声明方式见 [模型管理](../model-download)。

---

## 请求

```bash
GET http://127.0.0.1:9527/api/model/path?repo_id=BAAI/bge-small-zh-v1.5
```

**Query 参数**

| 参数 | 类型 | 必填 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| `repo_id` | 字符串 | 是 | — | 模型仓库 ID，需与 TOML 声明中的 `repo_id` 完全一致 |

**请求示例**

```bash
curl "http://127.0.0.1:9527/api/model/path?repo_id=tencent/Hy-MT2-1.8B-1.25Bit-GGUF"
```

---

## 响应示例

成功：

```json
{
    "code": 200,
    "data": {
        "path": "D:\\BmScriptsBox\\BmModels\\tencent\\Hy-MT2-1.8B-1.25Bit-GGUF",
        "repo_id": "tencent/Hy-MT2-1.8B-1.25Bit-GGUF"
    },
    "message": "模型tencent/Hy-MT2-1.8B-1.25Bit-GGUF路径获取成功",
    "success": true
}
```

模型未下载（404）：

```json
{
    "code": 404,
    "data": {},
    "message": "模型 iic/SenseVoiceSmall 未下载",
    "success": false
}
```

---

## 脚本中使用

```python
import os
import sys
import json
import requests

payload = json.load(open(sys.argv[1], encoding='utf-8'))
api_base = payload["environment"]["api_base"]

# 1. 查询模型所在文件夹
resp = requests.get(f"{api_base}/api/model/path", params={
    "repo_id": "BAAI/bge-small-zh-v1.5"
})
body = resp.json()

if not body.get("success"):
    raise RuntimeError(body.get("message", "模型路径查询失败"))

model_dir = body["data"]["path"]

# 2. 拼接具体文件名后加载
model_file = os.path.join(model_dir, "model.safetensors")
```

::: warning 注意
接口返回的 `path` 是模型所在的**文件夹路径**，不是某个具体模型文件的完整路径。你需要自己拼接文件名，例如 `os.path.join(model_dir, "model.safetensors")`。
:::

---

## 相关文档

- 模型怎么声明与下载 → [模型管理](../model-download)
- HTTP API 总览 → [HTTP API](../http-api/)