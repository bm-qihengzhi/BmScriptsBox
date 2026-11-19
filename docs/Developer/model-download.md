---
title: 模型管理
description: 在 TOML 里声明 repo_id，盒子安装时自动下载 AI 模型；涵盖双下载源、文件过滤规则与运行时取路径。
status: 稳定
docType: how-to
audience: 脚本开发者
docVersion: 0.3.0
---

# 模型管理


声明脚本依赖的 AI 模型（Embedding、LLM 等），盒子在安装时自动从 HuggingFace / ModelScope 下载，并通过本地 API 接口向脚本提供模型路径。无需手动下载，支持多平台。

* 开发者：在` [[bmscriptsbox.models]]` 中声明模型来源与版本即可。

* 用户：安装时自动下载，全程无需额外操作。

* 共享机制：多个脚本共用同一模型时只下载一次，统一缓存，避免冗余存储。

* 下载保障：支持断点续传，HuggingFace 模型自动走高速镜像。

---

## 三步上手

### 第一步：声明模型

在 `bm-scripts-box-rc.toml` 的根级添加 `[[bmscriptsbox.models]]` 段：

```toml
[[bmscriptsbox.models]]
source = "modelscope"
repo_id = "BAAI/bge-small-zh-v1.5"
files = ["*.safetensors", "*.json"]
```

### 第二步：盒子自动下载

脚本安装时，`ModelManager` 自动执行：

```plaintext
安装流程
  │
  ├─ 1. 检查 BmModels.json 清单 → 已下载则跳过
  ├─ 2. 检查磁盘剩余空间 → 不足 10GB 终止安装
  ├─ 3. 列出仓库文件 → 按 files 模式过滤
  ├─ 4. 逐个文件下载（每 0.5s 反馈实时进度）
  ├─ 5. 更新 BmModels.json 记录
  └─ 6. 继续后续安装流程
```

关键行为：

- **断点续传**：下载中断后重新安装，从断点处继续，不重复下载已完成的文件
- **实时进度**：ModelScope 和 HuggingFace 下载均有每 0.5s 的速度与百分比反馈，显示在安装进度条上
- **失败回滚**：模型下载失败时，安装流程终止并回滚已创建的目录和数据库记录
- **取消**：文件级别取消，每个文件下载完成后检查取消标志

### 第三步：运行时获取模型路径

脚本通过本地 HTTP API 查询模型路径：

```python
import os
import sys
import json
import requests

payload = json.load(open(sys.argv[1], encoding='utf-8'))
api_base = payload["environment"]["api_base"]     # http://127.0.0.1:9527

# 查询模型所在文件夹
resp = requests.get(f"{api_base}/api/model/path", params={
    "repo_id": "BAAI/bge-small-zh-v1.5"
})
data = resp.json()
model_dir = data["data"]["path"]

# 拼接具体文件名后加载
model_file = os.path.join(model_dir, "model.safetensors")
```

> 接口返回的 `path` 是模型所在的**文件夹路径**，不是具体文件路径。脚本需自行拼接模型文件名。接口详情见 [查询模型路径 · /api/model/path](./http-api/model-path)。

---

## 字段说明

| 字段 | 类型 | 必填 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| `source` | 字符串 | 否 | `"modelscope"` | 模型来源，可选 `modelscope` 或 `huggingface` |
| `repo_id` | 字符串 | 是 | — | 模型仓库 ID，从模型主页复制 |
| `files` | 字符串数组 | 否 | `["*"]` | 需要下载的文件匹配模式，支持通配符 |

**多模型声明：** 一个脚本可以依赖多个模型，每个模型独立声明：

```toml
[[bmscriptsbox.models]]
source = "modelscope"
repo_id = "BAAI/bge-small-zh-v1.5"
files = ["*.safetensors", "*.json"]

[[bmscriptsbox.models]]
source = "huggingface"
repo_id = "Qwen/Qwen2-0.5B-Instruct"
files = ["*.safetensors", "*.json", "tokenizer.*"]
```

---

## 模型来源怎么选

### ModelScope（国内推荐）

国内用户首选。盒子直接调用 ModelScope HTTP API 获取文件列表，用内置下载器下载，无需安装额外 SDK。

适用场景：国内网络环境、模型文件较大需断点续传、不依赖 `huggingface_hub` SDK。

### HuggingFace

通过 `huggingface_hub` SDK 列出文件，下载环节使用盒子内置下载器（支持断点续传和实时进度），自动启用国内镜像加速。

下载链接通过 `hf_hub_url()` 生成，自动拼接 `HF_ENDPOINT` 镜像地址（默认 `https://hf-mirror.com`），无需手动配置代理。

---

## 文件过滤

`files` 字段支持 `fnmatch` 风格的通配符，可以精确指定要下载的文件：

| 模式 | 说明 | 匹配示例 |
| --- | --- | --- |
| `["*"]`（默认） | 下载仓库中的所有文件 | — |
| `["*.safetensors", "*.json"]` | 仅下载模型权重和配置文件 | `model.safetensors`、`config.json` |
| `["tokenizer.*"]` | 仅下载分词器相关文件 | `tokenizer.json` |
| `["model-00001-of-00002.safetensors", ...]` | 精确指定分片文件名 | 多分片模型 |

> 如果 `files` 中**不带通配符**（纯精确文件名），即使 API 返回的文件列表为空，盒子也会尝试按文件名直接下载。

---

## 存储位置

模型文件统一存储在盒子管理目录下：

```plaintext
BmScriptsBox/
  ├─ BmModels/
  │   ├─ BAAI/
  │   │   └─ bge-small-zh-v1.5/
  │   │       ├─ model.safetensors
  │   │       └─ config.json
  │   └─ Qwen/
  │       └─ Qwen2-0.5B-Instruct/
  │           ├─ model-00001-of-00002.safetensors
  │           ├─ model-00002-of-00002.safetensors
  │           ├─ config.json
  │           └─ tokenizer.json
  └─ BmData/
      └─ BmModels.json     # 模型下载清单
```

`BmModels.json` 记录所有已下载模型的信息，盒子据此判断模型是否已下载、是否需要重新下载。

---

## 完整示例

一个需要 Embedding 模型和 LLM 的脚本，声明两个模型来源：

```toml
[bmscriptsbox]

[bmscriptsbox.info]
id = "a1b2c3d4-e5f6-7890-abcd-ef1234567890"
name = "AI 对话助手"
desc = "基于本地模型的智能对话脚本"
version = "1.0.0"

[bmscriptsbox.runtime]
language = "python"
language_version = ">=3.8"
entry = "main.py"
terminal = "always"

# Embedding 模型（ModelScope，国内下载快）
[[bmscriptsbox.models]]
source = "modelscope"
repo_id = "BAAI/bge-small-zh-v1.5"
files = ["*.safetensors", "*.json"]

# LLM 模型（HuggingFace，使用国内镜像加速）
[[bmscriptsbox.models]]
source = "huggingface"
repo_id = "Qwen/Qwen2-0.5B-Instruct"
files = ["*.safetensors", "*.json", "tokenizer.*"]
```

---

## 常见问题

**Q：模型下载失败会影响脚本安装吗？**
A：会。模型下载失败时，安装流程终止并回滚已创建的目录和数据库记录。

**Q：多个脚本用同一个模型，会重复下载吗？**
A：不会。盒子检查 `BmModels.json` 清单，已下载则跳过，共享同一份文件。

**Q：磁盘空间不足会怎样？**
A：盒子检查剩余空间，不足 10GB 会终止安装。

---

## 相关文档

- 查询模型路径接口 → [查询模型路径 · /api/model/path](./http-api/model-path)
- 脚本语言与运行环境 → [环境配置](./environment-config)