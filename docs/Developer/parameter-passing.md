---
title: 参数注入
description: 不忙盒子脚本参数传递机制——JSON 参数文件三段契约（environment/data/params）、各字段说明（含外部工具路径注入）、多语言读取示例
status: 稳定
docType: reference
audience: 脚本开发者
docVersion: 0.3.0
---

# 参数注入


启动时，盒子依据 TOML 中声明的输入项和当前触发方式，智能决定需要传递的数据。触发方式包括右键菜单、快捷键等。数据可能包括**右键选中的文件**、**当前工作目录**、**剪贴板内容**及**外部传入的运行参数**。这些数据统一打包为一个 JSON 文件传递给您的脚本。脚本只需读取该 JSON，即可一次性获取所有输入上下文，无需关心数据来源或手动解析。

---

## 盒子怎么做到的

盒子触发脚本时，生成一个临时 JSON 文件并注入参数，把该文件的路径作为**命令行第一个参数**传入：

```plaintext
盒子触发脚本 → 生成 %TEMP%/{uuid}.json → argv[1] = JSON 文件路径 → 脚本解析 JSON
```

<!-- ### 各触发方式的数据来源

| 启动方式 | 是否传参 | `data` 里是什么 |
| --- | --- | --- |
| 右键菜单 | 必传 | 路径数组（内容取决于 `targets` 配置） |
| 快捷键 | 必传 | 路径数组（内容取决于 `input_type` 配置） |
| 超级复制 | 必传 | 剪贴板纯文本（单元素数组） |
| 定时任务 | 必传 | 用户在 UI 中配置的值 |
| 盒子内点击运行 | 不传 | `data` 为空对象 | -->



<!-- ### 一个脚本可以配置多个触发器

一个脚本可以同时声明多个触发器子段，各自独立生效：

```toml
[bmscriptsbox]
# ... 其他配置 ...

[bmscriptsbox.triggers.context_menu]
enabled = true
targets = ["files"]

[bmscriptsbox.triggers.shortcut]
enabled = true
input_type = "files"
```

每次触发时，盒子按触发方式自动构造对应参数。如果脚本只希望通过盒子主界面手动点击运行，省略触发器相关字段即可；盒子默认所有触发器为 `enabled = false`，不会注册任何菜单或快捷键。

**脚本兼容性建议**

同一脚本可能被不同方式触发（右键或盒内运行），两种方式传递的 JSON 字段可能不同。建议脚本在开头检测 JSON 中的 `data` 字段是否为空：

- **有数据**（`data` 非空）→ 直接处理，执行自动化批处理；
- **无数据**（`data` 为空）→ 唤起图形界面，或进入交互式命令行。

--- -->

## 参数文件的三段契约

参数文件固定分三段：`environment`（盒子保留，脚本只读）、`data`（主数据）、`params`（运行参数）。

### 完整结构

```json
{
    "environment": {
        "workspace": "C:/Users/xxx/AppData/Local/Temp",
        "output_json": "C:/Users/xxx/AppData/Local/Temp/bms_xxxx.out.json",
        "encoding": "utf-8",
        "api_base": "http://127.0.0.1:9527",
        "task_id": "a1b2c3d4-...",
        "script_id": "afd522ed-0e2c-45f1-96c9-7ac02bb61639",
        "script_dir": "D:/BmScripts/afd522ed-...",
        "binaries": {
            "imagemagick": { "magick": "D:/BmPackages/downloads/imagemagick/.../magick.exe" }
        },
        "invoke_mode": "manual"
    },
    "data": {
        "video_paths": ["C:/videos/a.mp4"]
    },
    "params": {
        "language": "auto",
        "format": "srt"
    }
}
```

### environment 段（盒子保留区，脚本只读）

由盒子自动填充，编码固定为 `utf-8`。**脚本不应修改这一段的任何值。**

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `workspace` | 字符串 | 系统临时目录 `%TEMP%` |
| `invoke_mode` | 字符串 | 当前调用方式：`"manual"` 手动触发 / `"scheduled"` 定时任务触发 / `"node"` 以节点形式被调用。脚本据此判断自己该走交互还是自动化流程 |
| `output_json` | 字符串或 null | 结果回传文件路径。**需要脚本回写结果时才非空**：被节点调用（`invoke_mode=node`）、或被定时任务调度用于记录执行结果时；普通手动触发为 `null` |
| `encoding` | 字符串 | 固定为 `utf-8`，所有文件读写统一用此编码 |
| `api_base` | 字符串 | 盒子本地 HTTP 地址 `http://127.0.0.1:9527` |
| `task_id` | 字符串 | 本次执行的唯一任务 ID |
| `script_id` | 字符串 | 本脚本的 UUID |
| `script_dir` | 字符串 | 本脚本的安装目录绝对路径 |
| `binaries` | 对象（可省略） | 脚本声明过外部二进制（`runtime.binaries`）时才出现；结构 `{声明名: {命令名: 绝对路径}}`，脚本按绝对路径调用。详见 [工具托管 · 脚本怎么拿工具路径](./external-binaries#脚本怎么拿工具路径) |

> `invoke_mode` 是你判断"这次要不要按节点自动运行并写回信封"的依据，共三个值：
>
> - `"manual"`（右键 / 快捷键 / 超级复制 / 点击运行 / `/api/execute` 异步）→ 按你方便的方式展示结果
> - `"scheduled"`（定时任务触发）→ 按你方便的方式展示结果
> - `"node"`（被 `/api/link` 调用`）→ 无人值守跑完，把信封写进 `output_json`

### data 段（业务数据）

**键名从哪来**：`data` 里的键名 = 你的 TOML 中 `[[bmscriptsbox.inputs]]` 的 `name` 字段。

```toml
# TOML 配置
[[bmscriptsbox.inputs]]
name = "video_paths"
type = "list"
```

```json
// 生成的 JSON
"data": {
    "video_paths": ["C:/videos/a.mp4"]
}
```

脚本用同名 key 取值即可。**`data` 段的值恒为字符串数组**：`list` 类型可能有多条，`str` 类型是单元素数组。

#### type 数据类型映射

| `type` | 说明 | `data` 段取值 |
| --- | --- | --- |
| `list` | 数组（多个路径、多个文本） | `["C:/a.txt", "D:/b.md"]` |
| `str` | 单条文本（剪贴板内容、单个路径） | `["你好"]`（单元素数组） |

#### ⚠️ inputs 最多只能声明 1 条

当前版本**最多声明 1 条 `[[bmscriptsbox.inputs]]`**（主数据）。需要传多个文件或多个参数时，改用 `params` 的 `str` 类型声明路径参数。声明多条 `inputs` 会在安装时校验报错。

#### 不声明 inputs 会怎样

盒子跳过参数构造，`data` 为空对象，直接启动脚本。适合不需要外部输入的脚本（如清空回收站、打开某个工具）。

### params 段（运行参数）

`params` 是脚本的运行选项（如 `language`、`format`），在 TOML 中用 `[[bmscriptsbox.params]]` 声明：

```toml
[[bmscriptsbox.params]]
name = "language"
type = "str"
default = "auto"
choices = ["auto", "zh", "en", "ja"]
```

- 普通触发时，`params` 取 TOML 里声明的 `default` 值
- 被联动调用时，`params` 由调用方覆盖，未传的用默认值
- 只有 TOML 里声明过的参数名会出现在 `params` 段

详见 [运行参数](./params)。

<!-- ---

## 各触发场景的数据来源

### 右键菜单

| 配置 `targets` | `data` 数据来源 |
| --- | --- |
| `["files"]` | 选中的文件路径数组 |
| `["directory"]` | 选中的文件夹路径数组 |
| `["background"]` | 当前资源管理器标签页路径（单元素数组） |

### 快捷键

| `input_type` | `data` 数据来源 |
| --- | --- |
| `files` | 选中的文件数组 |
| `folders` | 选中的文件夹数组 |
| `active` | 当前文件夹标签页路径（单元素数组） |
| `items` | 文件和文件夹混合路径数组 |
| `""` | 不传任何路径 |

### 超级复制

`data` 存剪贴板纯文本，单元素数组。 -->

---

## 临时参数文件管理

盒子帮你管理临时文件，不需要你操心清理。

- **存储位置**：系统临时目录 `%TEMP%`
- **文件名**：`{uuid}.json`（全局唯一，避免冲突）
- **生命周期**：脚本执行完毕后，盒子自动删除

---

## 多语言读取示例

无论用哪种语言，读取逻辑都一致：**读命令行第一个参数 → 以 UTF-8 打开 JSON 文件 → 解析 `data` 拿业务数据。**

### Python

```python
import sys
import json

def main():
    json_file = sys.argv[1]
    with open(json_file, "r", encoding="utf-8") as f:
        params = json.load(f)
    paths = params["data"]["video_paths"]
    lang = params["params"].get("language", "auto")     # 运行参数
    api_base = params["environment"]["api_base"]        # 需要联动时使用
    workspace = params["environment"]["workspace"]
    bins = params["environment"].get("binaries", {})    # 外部工具路径（声明过才有）

if __name__ == "__main__":
    main()
```

### PowerShell

```powershell
param($paramPath)
$paramObj = Get-Content $paramPath -Encoding UTF8 | ConvertFrom-Json
$paths = $paramObj.data.video_paths
$lang  = $paramObj.params.language
```

### Node.js

注意：Node.js 的 `argv` 偏移一位，JSON 路径在 `process.argv[2]`。

```javascript
const fs = require("fs");
const jsonPath = process.argv[2];
const params = JSON.parse(fs.readFileSync(jsonPath, "utf8"));
const paths = params.data.video_paths;
const lang = params.params.language;
```

### BAT 批处理

BAT 自身没有 JSON 解析能力，借助 PowerShell 辅助：

```batch
@echo off
set "jsonPath=%1"
powershell -Command "$p = Get-Content '%jsonPath%' -Utf8 | ConvertFrom-Json; $p.data.video_paths"
```

### AutoHotkey v2

需要引入 JSON.ahk 库：

```autohotkey
#Requires AutoHotkey v2.0
paramPath := A_Args[1]
fileContent := FileRead(paramPath)
jsonData := JSON.parse(fileContent)
paths := jsonData["data"]["video_paths"]
```

---

## 开发速查

- **参数载体**：临时 UUID JSON 文件，编码 `utf-8`
- **入参位置**：命令行第一个参数 = JSON 文件路径（Node.js 是第二个）
- **三段契约**：`environment` 盒子保留区（含 `api_base`）、`data` 业务数据、`params` 运行参数
- **键名约定**：`[[inputs]].name` → `data` 段键名
- **数据类型**：`list`（路径数组）和 `str`（单条文本，`data` 中恒为单元素数组）
- **inputs 限制**：最多声明 1 条，多条在安装时校验报错
- **底层封装**：Windows COM 获取选中项，脚本无需处理
- **外部工具路径**：声明过 `binaries` 时，`environment.binaries` 给出 `{声明名: {命令名: 绝对路径}}`，详见 [工具托管](./external-binaries)
- **联动**：`environment.api_base` + `/api/link`，详见 [脚本联动](./script-linking)

---

## 常见问题

**Q：为什么 Node.js 读的是 `argv[2]` 而不是 `argv[1]`？**
A：Node.js 的 `argv[0]` 是 node 可执行文件路径，`argv[1]` 是脚本路径，JSON 路径在 `argv[2]`。

**Q：脚本没收到参数？**
A：可能是盒子内点击运行（无参数）或没声明 `inputs`。有参数时 `data` 才有内容。

**Q：能自己写多个 inputs 吗？**
A：不能。`inputs` 最多 1 条（主数据），需要多个文件用 `params` 的 `str` 类型声明路径参数。

---

## 相关文档

- 数据输入输出完整规则 → [输入输出契约](./io-contract)
- 工具托管 → [工具托管](./external-binaries)
- 触发方式配置 → [右键菜单触发](./context-menu)、[快捷键触发](./hotkey)、[超级复制触发](./quick-copy)
- 控制窗口行为 → [终端模式详解](./terminal-mode)