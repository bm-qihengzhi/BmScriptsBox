---
title: 节点
description: 不忙盒子节点机制——什么脚本该声明为节点、怎么声明、如何识别被调用、声明何时生效
status: 稳定
docType: explanation
audience: 脚本开发者
docVersion: 0.3.0
---

# 脚本节点
声明 [bmscriptsbox.node]，即表示该脚本可作为节点，允许被其他脚本通过盒子统一 API 调用。

* 开发者：在 TOML 中声明 [bmscriptsbox.node] 、完善数据返回的代码。

* 用户：使用无感，节点被调用时自动运行并回传结果。

* 运行机制：普通脚本跑完即结束，节点脚本跑完必须将结果按信封格式交回。

* 调用约定：调用方如何发起、信封格式、错误码及防循环规则，[脚本联动](./script-linking)

---

## 该不该声明为节点

一句话判断：**你的脚本有没有被调用的价值**

| 场景 | 是否声明 |
| --- | --- |
| 只给人用（右键 / 快捷键触发），结果自行打印或写入文件 | 不需要 |
| 产出内容有被调用的价值（如提取字幕、转换格式、生成报告等） | 需要 |
| 现在没人调，但设计上就是个「零件」 | 可以声明，无副作用 |

声明节点**不影响**任何人工触发方式——右键、快捷键、超级复制、盒子内点击、定时任务全部照常。它的全部语义只有一条：**允许被脚本调用**。

---

## 怎么声明

两步，都在 `bm-scripts-box-rc.toml` 里。

**① 打开节点开关**

```toml
[bmscriptsbox.node]
enabled = true
```

**② 至少声明 1 个 outputs**

```toml
[[bmscriptsbox.outputs]]
name = "subtitle_path"
type = "str"
description = "提取出的字幕文件绝对路径（.srt）"
```

::: tip 为什么必须有 outputs
节点的全部意义就是「回传结果」。开了 `node` 却不声明返回什么，等于承诺了能力却没说清内容，安装时直接校验报错：

> 声明可作为节点的脚本必须至少声明 1 个 outputs

只校验 `outputs`，不校验 `inputs` / `params`——很多节点不需要输入，但一定得有返回。
:::

---

## 声明后会发生什么

| 维度 | 非节点（不写 `node`） | 节点（声明 `node`） |
| --- | --- | --- |
| 右键 / 快捷键 / 超级复制触发 | 正常 | 正常（不受影响） |
| 盒子内点击运行 | 正常 | 正常（不受影响） |
| 定时任务触发 | 正常 | 正常（不受影响） |
| 被其他脚本 `/api/link` 调用 | 拒绝，HTTP 403 | 放行 |
| 必须声明 `outputs` | 不需要 | 必须 ≥ 1 个 |

`/api/link` 是唯一的串联入口，对节点门禁一票否决：目标 `is_node` 为假 → 返回 `403 未声明可作为节点`，被调脚本**根本不会执行**。

---

## 节点脚本怎么写

被当作节点调用时，脚本必须**无人值守跑通**。三件事：认出自己被调、参数自己兜底、结果写成信封。

### 判断是不是被当作节点

盒子在 `environment` 里注入了一个明确的模式字段 `invoke_mode` 来区分两种触发：

| 触发方式 | `environment.invoke_mode` | 脚本该做什么 |
| --- | --- | --- |
| 右键 / 快捷键 / 超级复制 / 点击运行 | `"manual"` | 按你方便的方式展示结果 |
| 定时任务 | `"scheduled"` | 按你方便的方式展示结果 |
| 被脚本调用（`/api/link`，或 `/api/execute` + `sync`） | `"node"` | 无人值守跑完，把信封写进 `output_json` |

对节点脚本来说，真正的分水岭只有一条：**`invoke_mode == "node"` 就是被脚本调用了**。`"manual"` 和 `"scheduled"` 都算"常规触发"，走你正常的展示逻辑即可：

```python
if env.get("invoke_mode") == "node":
    ...  # 以节点被调：写回信封，不交互
else:
    ...  # manual / scheduled：正常展示（可弹窗）
```

`invoke_mode` 由盒子注入、每次启动都在。靠这**一个**字段，同一个脚本就能既给人用、又当零件服务别的脚本——不用去猜 `output_json` 存不存在。

### 参数一律用默认值兜底

节点模式下没人给你填参数，所有 `params` 用 `.get(name, 默认值)` 读：

```python
lang = payload["params"].get("language", "auto")
```

盒子在调用侧已把 TOML 默认值合并注入，真缺且无默认的必填参数会在 `/api/link` 阶段被 400 拦下，根本到不了脚本。但 `.get()` 兜底仍是必要的习惯——它保证你的脚本在两种模式下都不崩。

### 结果写成信封

信封固定为 `{code, msg, ...outputs 声明的业务键}`，业务键在顶层平铺、不嵌套：

```python
with open(env["output_json"], "w", encoding="utf-8") as f:
    json.dump({
        "code": 0,
        "msg": "字幕提取完成",
        "subtitle_path": subtitle_path,
    }, f, ensure_ascii=False)
```

不写 `output_json`、缺 `code` / `msg`、或 `code` 不是整数——调用方都会拿到 `code = -3`（格式错误）。完整错误码见 [脚本联动](./script-linking)。

::: warning 盒子不校验返回键是否匹配 outputs
返回了 `outputs` 里没声明的键，**不会**被判 `-3`，盒子只校验 `code` 是整数、`msg` 是字符串。

但你声明什么，调用方就按什么取。不按声明返回，调用方只会取到缺失的键（拿到 `None` 或抛 `KeyError`），而且这种错误不会有任何报错提示。把 `outputs` 当作对调用方的承诺来遵守。
:::

### 完整骨架

一个既能给人用、又能当节点的脚本长这样（`extract_subtitle` / `show_dialog` 为业务实现，此处示意）：

```python
import json, sys

payload = json.load(open(sys.argv[1], encoding="utf-8"))
env = payload["environment"]
params = payload.get("params", {})

# 1. 参数兜底：params 取默认值，data 可能为空
lang = params.get("language", "auto")

# data 段不保证有值：手动直启且没选中文件时就是空的，节点模式则由调用方传入
videos = payload.get("data", {}).get("video_paths") or []
if not videos:
    if env.get("invoke_mode") == "node":
        # 节点模式没收到输入：写错误信封，别抛异常（否则调用方只会拿到 -3）
        with open(env["output_json"], "w", encoding="utf-8") as f:
            json.dump({"code": 1, "msg": "未收到视频路径"}, f, ensure_ascii=False)
        sys.exit(0)
    # 手动触发：提示用户先选中文件
    show_dialog("请先选中视频文件再运行")
    sys.exit(0)

video = videos[0]

# 2. 干活
subtitle_path = extract_subtitle(video, lang)

# 3. 分支：以节点被调就写信封，手动触发就弹窗
if env.get("invoke_mode") == "node":
    with open(env["output_json"], "w", encoding="utf-8") as f:
        json.dump({
            "code": 0,
            "msg": "字幕提取完成",
            "subtitle_path": subtitle_path,
        }, f, ensure_ascii=False)
else:
    show_dialog(f"字幕已生成：{subtitle_path}")
```

---

## 上线前自检

- [ ] `[bmscriptsbox.node] enabled = true` 已写
- [ ] 至少有 1 个 `[[bmscriptsbox.outputs]]`
- [ ] 节点模式下没有弹窗、`input()` 或任何等待用户操作
- [ ] 所有 `params` 都用 `.get(name, 默认值)` 读取
- [ ] 信封写全了 `code`（整数）、`msg`、以及 `outputs` 声明过的业务键
- [ ] 改完 TOML 后**重新安装 / 更新**过脚本

---

## 常见问题

**Q：改了 TOML 加了 node，怎么不生效？**
A：`is_node` 是数据库里的列，只在**安装 / 更新脚本时**由 TOML 重新写入。装完脚本才去加 `node`，只改已安装目录里的 TOML **不会生效**。必须重新安装 / 更新。

**Q：声明节点会影响人工触发吗？**
A：完全不影响。右键 / 快捷键 / 超级复制 / 盒子内点击 / 定时任务全部照常，只是多了一个"允许被脚本调用"的通道。

**Q：被调用时返回了未声明的键会怎样？**
A：盒子不校验，不会报 `-3`。但调用方按你声明的 `outputs` 取值，不匹配只会拿到 `None` 或 `KeyError`，且没有提示。

---

## 相关文档

- **调用方视角**：A 怎么调 B、信封契约、错误码、防循环 → [脚本联动](./script-linking)
- **接口细节**：请求参数与响应 → [脚本联动 · /api/link](./http-api/link)
- **字段位置**：`node` 在 TOML 中的完整上下文 → [配置文件详解](./declarative-access)
- **返回键规则**：`outputs` 怎么声明 → [输入输出契约](./io-contract)