---
title: 声明式接入
description: 在 bm-scripts-box-rc.toml 里声明脚本的形态、触发方式与运行选项——每段配置字段、必填规则、校验错误对照表与真实案例。
status: 稳定
docType: reference
audience: 脚本开发者
docVersion: 0.3.0
---

# 声明式接入

> **松耦合、无侵入式的接入方式**

不忙脚本盒子遵循**声明式接入**：只需要一个 `bm-scripts-box-rc.toml` 文件，用纯文本声明脚本的形态、语言和触发位置等信息、盒子会根据声明的信息对脚本进行适配、配置文件采用 TOML 格式，盒子安装时用 **Pydantic v2** 严格校验


---

## 什么时候用哪个段

先找到你要声明的东西，再往下翻对应章节，不用通读全文。

| 我要声明…… | 用这个段 | 必填吗 | 能力文档 |
| --- | --- | --- | --- |
| 脚本基础信息 | `[bmscriptsbox.info]` | **必填** | — |
| 脚本环境信息 | `[bmscriptsbox.runtime]` | **必填** | [多语言支持](./multi-language)、[终端模式详解](./terminal-mode)、[单实例与并发](./single-instance) |
| 脚本执行入口 | `[bmscriptsbox.triggers]` | 选填 | [右键菜单](./context-menu) / [快捷键](./hotkey) / [超级复制](./quick-copy) / [搜索触发](./search-trigger) |
| 脚本所需数据 | `[[bmscriptsbox.inputs]]` | 选填，最多 1 条 | [输入输出契约](./io-contract) |
| 脚本返回数据 | `[[bmscriptsbox.outputs]]` | 声明节点时必填 | [输入输出契约](./io-contract) |
| 其他运行参数 | `[[bmscriptsbox.params]]` | 选填，可多条 | [运行参数](./params) |
| 调用别的脚本 | `[[bmscriptsbox.dependencies]]` | 联动时必填 | [脚本联动](./script-linking) |
| 允许被其他脚本调用 | `[bmscriptsbox.node]` | 作为节点时必填 | [节点](./node) |
| 允许被定时任务调度 | `[bmscriptsbox.schedule]` | 作为定时任务时必填 | [定时任务](./scheduled-task) |
| 由盒子渲染GUI启动窗口 | `[bmscriptsbox.params_form]` | 选填 | [自动生成运行界面](./auto-generated-ui) |
| 需要外部命令行工具（FFmpeg 等） | `binaries`（在 `runtime` 段内） | 选填 | [工具托管](./external-binaries) |
| 需要 AI 模型 | `[[bmscriptsbox.models]]` | 选填 | [模型管理](./model-download) |
| 工作流编排 | `[bmscriptsbox.workflow]` | 🚧 预留，暂不可用 | [工作流](./workflow) |

---

## 全部配置字段预览

```toml
[bmscriptsbox]

# ====== 1. 基本信息 ======
[bmscriptsbox.info]
id = "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx"   # UUID v4（必填）
name = "脚本名称"                              # 脚本显示名称（必填，至少 1 个字符）
desc = "脚本描述"                              # 描述说明（选填）
icon = "icon/logo.png"                        # 图标路径（相对路径，选填）
version = "1.0.0"                             # 语义化版本号（必填，格式 x.y.z）

# ====== 2. 运行环境 ======
[bmscriptsbox.runtime]
language = "python"               # 脚本语言（必填，见支持列表）
language_version = ">=3.8"        # 语言版本要求（必填，bat/html/exe 可填 >=0.0.0）
entry = "main.py"                 # 入口文件路径（必填，相对路径）
terminal = "always"               # 终端模式（选填，建议始终显式填写）
concurrency = "single"            # 并发策略：single（默认）/ forward（GUI 转发）
binaries = [{name = "7zip"}]      # 依赖的外部二进制工具（选填）

# ====== 3. 触发器配置 ======
[bmscriptsbox.triggers]

  [bmscriptsbox.triggers.context_menu]
  enabled = true
  targets = ["files", "directory"]
  filters = [".txt", ".md"]

  [bmscriptsbox.triggers.shortcut]
  enabled = true
  input_type = "files"
  filters = [".txt"]

  [bmscriptsbox.triggers.quick_copy]
  enabled = false

# ====== 4. 输入参数定义（最多 1 条，主数据） ======
[[bmscriptsbox.inputs]]
name = "target_paths"
type = "list"                                   # list = 路径数组 / str = 单条文本
exts = [".txt", ".md", ".py"]
description = "要处理的源文件"

# ====== 5. 输出参数定义（联动时返回的业务键） ======
[[bmscriptsbox.outputs]]
name = "result"
type = "str"
description = "处理后的结果文件路径"

# ====== 6. 运行参数（脚本运行选项，可多条） ======
[[bmscriptsbox.params]]
name = "language"
type = "str"                                    # str | int | float | bool | list | dict
default = "auto"
choices = ["auto", "zh", "en"]                  # 仅 str 类型有效
description = "字幕语言"

# ====== 7. 脚本依赖（联动调用节点脚本时声明节点脚本ID） ======
[[bmscriptsbox.dependencies]]
id = "afd522ed-0e2c-45f1-96c9-7ac02bb61639"     # 被依赖脚本的 script_id

# ====== 8. 节点声明（被其他脚本联动调用时声明） ======
[bmscriptsbox.node]
enabled = true                                  # 声明可作为节点，须有 ≥1 个 outputs

# ====== 9. 定时任务声明（被盒子定时调度时声明） ======
[bmscriptsbox.schedule]
enabled = true                                  # 声明可被定时任务调度（须能无人值守、仅凭 params 运行）

# ====== 10. 自动生成运行界面（交互式运行时自动弹设置窗） ======
[bmscriptsbox.params_form]
enabled = true                                  # 声明：运行本脚本前自动弹设置界面

# ====== 11. 模型下载 ======
[[bmscriptsbox.models]]
source = "huggingface"                               # 模型下载源：huggingface / modelscope
repo_id = "tencent/Hy-MT2-1.8B-1.25Bit-GGUF"         # 模型 repo_id，网页上可复制
files = ["Hy-MT2-1.8B-1.25Bit.gguf"]                 # 需要下载的模型文件，可多个

# ====== 12. 工作流配置（🚧 预留，见下方说明） ======
[bmscriptsbox.workflow]
workflow_enabled = true
```

> 前两个字段为必填项，其余字段均为可选项，开发者可依据脚本的实际需求灵活扩展。


---

## 基本信息 `[bmscriptsbox.info]`

告诉盒子"你的脚本是谁"。盒子用它标识脚本、展示名称、管理版本。

| 字段 | 类型 | 必填 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| `id` | UUID | 是 | — | 脚本唯一标识，生成后固定。重复安装会覆盖旧版本 |
| `name` | 字符串 | 是 | — | 盒子 UI 中显示的名称，至少 1 个字符 |
| `desc` | 字符串 | 否 | `""` | 脚本描述 |
| `icon` | 字符串 | 否 | `""` | 图标相对路径（相对于脚本根目录） |
| `version` | 字符串 | 是 | — | 语义化版本号，格式 `x.y.z`（纯数字） |

### 版本号规则

必须匹配正则 `^\d+\.\d+\.\d+$`：

- ✅ `1.0.0`、`2.3.1`、`10.0.0`
- ❌ `1.0`（缺一位）、`v1.0.0`（带 v 前缀）

### 图标路径说明

- 路径**相对于脚本根目录**，安装时盒子自动解析为绝对路径
- 留空表示不使用图标，盒子显示默认图标

---

## 运行环境 `[bmscriptsbox.runtime]`

声明脚本用什么语言、从哪个文件启动、终端模式与并发策略。该段必填。

```toml
[bmscriptsbox.runtime]
language = "python"
language_version = ">=3.8"
entry = "main.py"
terminal = "always"
concurrency = "single"        # 选填，默认 single
binaries = [{name = "7zip"}]  # 选填
```

| 字段 | 类型 | 必填 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| `language` | 字符串 | 是 | — | 脚本语言，见 [多语言支持](./multi-language) |
| `language_version` | 字符串 | 是 | — | 语言版本要求；BAT / HTML / EXE 可填 `>=0.0.0` |
| `entry` | 字符串 | 是 | — | 入口文件，相对脚本根目录，不能是绝对路径 |
| `terminal` | 字符串 | 否 | `"always"` | `never` / `always` / `auto` / `inverse`，见 [终端模式详解](./terminal-mode) |
| `concurrency` | 字符串 | 否 | `"single"` | `single` / `forward`，见 [单实例与并发](./single-instance) |
| `binaries` | 数组 | 否 | `[]` | 外部命令行工具声明，见 [工具托管](./external-binaries) |

### 并发策略 `concurrency`

默认 `single`：同一个脚本同时只允许一个进程，重复触发会被拒绝。

自带 GUI 的常驻脚本（翻译、预览、编辑器等）可以声明：

```toml
[bmscriptsbox.runtime]
concurrency = "forward"
```

`forward` 不查重，每次触发都会启动新进程；第二个进程需要由脚本自己通过 IPC 把参数转发给已有窗口。盒子不参与参数注入。完整约定与代码示例见 [单实例与并发](./single-instance)。

> 修改 TOML 后需要重新安装或更新脚本，盒子才会把新配置写入本地脚本库。

详见 [环境配置](./environment-config)。
`terminal` [终端模式详解](./terminal-mode)。

---

## 触发器配置

详见 [右键菜单触发](./context-menu)、[快捷键触发](./hotkey)、[超级复制触发](./quick-copy)、[搜索触发](./search-trigger)。

### 搜索触发（triggers.search）

搜索触发现在是独立触发配置。完整字段、匹配规则与传参方式见 [搜索触发](./search-trigger)。

---

## 输入 / 输出参数

定义脚本接收什么数据、返回什么结果。详见 [输入输出契约](./io-contract)。



---

## 运行参数 `[[bmscriptsbox.params]]`

详见 [运行参数](./params)。

---

## 脚本依赖 `[[bmscriptsbox.dependencies]]`

详见 [脚本联动](./script-linking)。

---

## 节点声明 `[bmscriptsbox.node]`


详见 [脚本节点](./node)

---

## 定时任务声明 `[bmscriptsbox.schedule]`


详见 [定时任务](./scheduled-task)。

---

## 自动生成运行界面 `[bmscriptsbox.params_form]`


详见 [自动生成运行界面](./auto-generated-ui)。

---

## 模型下载

详见 [模型管理](./model-download)。

---

## 工作流

::: danger 🚧 未实现

详见 [工作流](./workflow)。

:::

## 配置校验错误对照表

安装时校验失败会给出错误提示。以下是常见错误及修正方法：

| 字段路径 | 校验规则 | 错误示例 → 修正 |
| --- | --- | --- |
| `info.id` | 标准 UUID v4 格式 | `"123"` → `"a1b2c3d4-e5f6-7890-abcd-ef1234567890"` |
| `info.name` | 至少 1 个字符 | `""` → `"文件分类器"` |
| `info.version` | `x.y.z` 纯数字格式 | `"1.0"` → `"1.0.0"`；`"v1.0.0"` → `"1.0.0"` |
| `info.icon` | 相对路径，不能是绝对路径 | `"C:/icon.png"` → `"icon/logo.png"` |
| `runtime.entry` | 相对路径，不能是绝对路径 | `"D:/main.py"` → `"main.py"` |
| `runtime.concurrency` | 只允许 `single` / `forward` | `"parallel"` → `"single"`，或按需改 `"forward"` |
| `inputs` | 最多声明 1 条 | 声明 2 条 → 只留 1 条主数据，其余改 `params` 的 `str` 路径参数 |
| `inputs.type` | 必须是 `list` / `str` | `"paths"` → `"list"`；`"text"` → `"str"` |
| `params.name` | 同脚本内唯一 | 两个同名 `name` → 改成不同名 |
| `params.type` | 必须是 `str` / `int` / `float` / `bool` / `list` / `dict` | `"string"` → `"str"` |
| `params.choices` | 仅 `str` 类型有效 | 对 `int` 声明 choices → 删除 choices 或改 `str` |
| `node` | 声明节点须 ≥1 个 `outputs` | 只写 node、没写 outputs → 补 `[[bmscriptsbox.outputs]]` |
| `dependencies.id` | 不能依赖自己 / 重复 | 依赖自身 → 删除该条；重复 id → 去重 |

`runtime.language` / `runtime.language_version` 的校验规则见 [多语言支持](./multi-language)。

---

## 真实案例

### 最小配置（只填必填字段就够了）

不需要图标、终端配置、触发器时，这样就行：

```toml
[bmscriptsbox]

[bmscriptsbox.info]
id = "a1b2c3d4-e5f6-7890-abcd-ef1234567890"
name = "Hello 盒子"
version = "1.0.0"

[bmscriptsbox.runtime]
language = "python"
language_version = ">=3.8"
entry = "main.py"
terminal = "always"
```

### 完整配置（真实的 Python 脚本）

```toml
[bmscriptsbox]

[bmscriptsbox.info]
id = "b2c3d4e5-f6a7-8901-bcde-f12345678901"
name = "文件分类器"
desc = "根据文件扩展名自动分类到对应文件夹"
icon = "icon/logo.png"
version = "1.2.0"

[bmscriptsbox.runtime]
language = "python"
language_version = ">=3.8"
entry = "main.py"
terminal = "never"

[bmscriptsbox.triggers.context_menu]
enabled = true
targets = ["files"]

[[bmscriptsbox.inputs]]
name = "target_paths"
type = "list"
```

这样配置后的实际效果：

1. 用户在资源管理器选中文件，右键 → 看到「文件分类器」
2. 盒子把选中的文件路径写进 JSON 参数文件，并把该 JSON 的路径作为命令行第一个参数启动脚本
3. 脚本读 JSON、拿到文件路径、执行分类逻辑

---

## 相关文档

- 配置里声明的每个能力，对应一篇能力文档：见上方「什么时候用哪个段」表
- 语言声明与版本规则 → [多语言支持](./multi-language)、[环境配置](./environment-config)
- 整体能力地图 → [脚本开发总览](./index)