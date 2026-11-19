---
title: 脚本联动
description: A 脚本如何调用 B 脚本（节点）组合出复合功能：依赖声明、传参、输出信封契约、错误码与防循环规则。
status: 稳定
docType: how-to
audience: 脚本开发者
docVersion: 0.3.0
---

# 脚本联动

> **A 脚本在运行中调用 B 脚本、拿回 B 的结果，多个脚本组合出复合功能。**

脚本联动让你把多个脚本串起来，组合出复合功能。A（视频翻译）调用 B（字幕提取），一条链路完成整个工作流。**调用方和被调方都是盒子脚本**，用同样的 JSON 参数机制启动，只是多了一层"脚本调脚本"。

盒子启动时运行一个本地 HTTP 服务（`127.0.0.1:9527`），脚本在运行期间通过它调用其他脚本。这是唯一的联动通道：没有消息中间件、没有 RPC，就是本地 Flask + 同步 HTTP 调用。

---

## 盒子怎么做到的

> 每次启动脚本，盒子都会往它的参数文件 `environment` 段注入 `api_base`（盒子地址）。脚本拿起它，POST 给 `/api/link`，盒子**同步**执行被调脚本——为它重建环境、跑完、把它写进 `output_json` 的结果整个返回给调用方。

```plaintext
A 启动（盒子注入 environment，含 api_base）
  → A 调 /api/link（同步等待）
    → 盒子为 B 重建 environment（生成新的 output_json）
    → 执行 B
    → B 把结果写成信封写入 output_json
    → 盒子读回信封
  → 返回给 A
```

`/api/link` 恒为同步：发起请求后一直等到 B 跑完并拿到它的信封结果，没有 `sync` 参数，也没有异步模式。

---

## 前提条件（两步）

写联动代码前，先确认这两点：

### 1. 被调脚本必须是「节点」

被调脚本（B）必须声明为节点，否则盒子**直接拒绝**（HTTP 403）。节点的概念、为什么要声明、怎么声明，见 [节点](./node)。简单说：只有正式声明过、且有至少 1 个 `outputs` 的脚本，才具备"被调且返回结果"的能力。

```toml
[bmscriptsbox.node]
enabled = true   # 声明本脚本可作为节点被其他脚本联动调用
```

> 声明节点时的 `outputs` 硬要求、`is_node` 落库时机、常见误区，都在 [节点](./node) 里，不再赘述。

### 2. 被调脚本已安装

被调脚本必须已装在盒子里。可以在 TOML 里声明依赖让盒子**自动安装**，也可以让用户提前手动安装。

---

## 被调脚本（B）的声明

B 是被调节点——配置上就是「普通脚本 + `[bmscriptsbox.node] enabled = true` + 至少 1 个 `outputs`」。节点的概念与校验见 [节点](./node)，这里看一个完整的 B 应该长什么样：

```toml
[bmscriptsbox]

[bmscriptsbox.info]
id = "afd522ed-0e2c-45f1-96c9-7ac02bb61639"
name = "字幕提取"
version = "1.0.0"

[bmscriptsbox.runtime]
language = "python"
language_version = ">=3.8"
entry = "main.py"

[[bmscriptsbox.inputs]]
name = "video_paths"
type = "list"                     # list = 路径数组（主数据）
exts = [".mp4", ".mkv", ".avi"]

[[bmscriptsbox.params]]
name = "language"
type = "str"
default = "auto"
choices = ["auto", "zh", "en", "ja"]

[[bmscriptsbox.outputs]]
name = "subtitle_path"            # 节点返回的业务键
type = "list"
description = "提取出的字幕文件绝对路径（.srt）数组"

[bmscriptsbox.node]
enabled = true                    # 声明可作为节点被联动调用
```

B 的 `main.py` 结尾要把结果写成**信封**：

```python
import json, sys

payload = json.load(open(sys.argv[1], encoding='utf-8'))
env = payload["environment"]

# 结果写成信封，写入盒子指定的 output_json
with open(env["output_json"], 'w', encoding='utf-8') as f:
    json.dump({"code": 0, "msg": "ok", "subtitle_path": ["C:/tmp/a.srt"]}, f)
```

---

## 调用方（A）的声明与依赖

A 要调用 B，需要在 TOML 里声明依赖：

```toml
[[bmscriptsbox.dependencies]]
id = "afd522ed-0e2c-45f1-96c9-7ac02bb61639"   # B 的 script_id（仅填 id）
```

**安装 A 时盒子的处理顺序**：

1. 先完整安装 A 本体（装完 A 才知道它依赖谁）
2. 再查本地：B 已安装 → 跳过，提示「B 已安装，跳过」；未安装 → 自动从社区安装 B（B 自身的依赖递归展开）
3. B 安装失败 → B 回滚，A 也回滚并提示「缺少依赖」
4. **B 必须已发布到社区**，否则解析失败、A 安装中止

> 只要脚本需要调用别的脚本，这个依赖声明就必填。

---

## 调用代码（A 的 Python 示例）

A 收到盒子注入的 `environment` 后，用 `requests` 同步调用 B：

```python
import json, sys, requests

payload = json.load(open(sys.argv[1], encoding='utf-8'))
env = payload["environment"]
video = payload["data"]["video_paths"][0]

B_ID = "afd522ed-0e2c-45f1-96c9-7ac02bb61639"

r = requests.post(f"{env['api_base']}/api/link",
                  json={
                      "script_id": B_ID,
                      "data": {"video_paths": [video]},
                      "params": {"language": "zh"},
                  }, timeout=3600)
body = r.json()

if not body.get("success"):
    raise RuntimeError(body.get("message", "联动调用失败"))

result = body["result"]                # B 写的信封
if result.get("code") != 0:
    raise RuntimeError(result.get("msg"))

subtitle_path = result["subtitle_path"]   # B 返回的业务键，在信封顶层平铺
print(f"字幕已生成: {subtitle_path}")
```

请求参数说明：

| 字段 | 说明 |
| --- | --- |
| `script_id` | 被调脚本 B 的 UUID |
| `data` | B 的主数据，键名取 B 的 `inputs[0].name` |
| `params` | B 的运行参数覆盖，未传的用 B 的 TOML 默认值 |

---

## 输出信封契约

被联动调用的脚本，必须把结果写到 `environment.output_json` 指定的文件，内容固定为**信封**：

```json
{
    "code": 0,
    "msg": "ok",
    "subtitle_path": ["C:/tmp/a.srt"],
    "lang": "zh"
}
```

- `code` / `msg` 是**保留字段**，不属于 `outputs` 声明；`outputs` 声明的是业务键
- 业务键在信封**顶层平铺**，不嵌套

`code` 语义：

| code | 含义 |
| --- | --- |
| `0` | 业务成功 |
| 非 `0` | 业务失败（`msg` 说明原因） |
| `-1` | 盒子合成：脚本启动失败 |
| `-2` | 盒子合成：执行超时 |
| `-3` | 盒子合成：格式错误（`output_json` 缺失 / 损坏 / 缺 `code` 或 `msg` / `code` 非 int） |

校验规则：

- **严格校验**：缺 `code` / `msg` 或 `code` 非 int，即使进程退出码是 0，也按格式错误（`-3`）处理
- `success` 统一 = 进程成功（exit 0 且未超时）**且** `result.code == 0`
- 进程层失败时盒子也会合成错误信封，`result` 不会是 `{}`
- 不返回结果的脚本若被联动调用，会被判失败（`-3`）

---

## 防循环

- **调用深度计数**：`/api/link` 进入时盒子把同步调用深度 +1，返回时 -1；**超过 8 层直接拦截**（HTTP 400），杜绝 A 调 B、B 又调 A 的死循环。同步联动天然嵌套（A 等 B、B 等 C），深度即真实链路层数
- **`environment` 由盒子重建**：每次调用被调脚本，盒子都为它重建 `environment`，调用方永远无法传入自定义的 `environment`

> 别把这个 8 层限制和 `dependencies` 的 5 层限制搞混：8 层是**运行期**的联动嵌套深度，5 层是**安装期**的脚本依赖链深度。

---

## 错误排查表

| 现象 | 原因 | 处理 |
| --- | --- | --- |
| HTTP 403「未声明可作为节点」 | B 的 TOML 没写 `[bmscriptsbox.node] enabled = true` | 给 B 加节点声明并重新安装，见 [节点](./node) |
| HTTP 400「联动链路过深」 | 调用链超过 8 层（或形成循环） | 检查是否 A 调 B 又调回 A |
| HTTP 400「缺少必填参数」 | B 的 `required` 参数没传 | 补全 `params` |
| `result.code == -3` | B 没写 `output_json` 信封，或信封格式不对 | 按信封契约写 `{code, msg, ...}` |
| `result.code == -2` | B 执行超时 | 检查 B 是否卡死，或调大 `timeout` |
| `success == false` 且无 result | 进程启动失败 / 非零退出 | 看 `stdout` / `stderr` 排查 |

---

## 任何触发方式都能发起联动

不只是联动链路里的脚本能调别人。**右键菜单、快捷键、超级复制、定时任务**触发的脚本，盒子同样会注入 `api_base`。所以任何脚本都可以作为联动发起方——只要你从 `environment` 取地址。

---

## 相关文档

- 被调方怎么声明 → [节点](./node)
- 接口细节 → [脚本联动 · /api/link](./http-api/link)
- 输入输出契约 → [输入输出契约](./io-contract)