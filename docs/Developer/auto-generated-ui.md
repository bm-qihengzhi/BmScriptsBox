---
title: 自动生成运行界面
description: 不忙盒子自动生成运行界面——声明 inputs 与 params，盒子自动生成设置界面，无需手写 GUI
status: 稳定
docType: how-to
audience: 脚本开发者
docVersion: 0.3.0
---

# 自动生成运行界面

> **根据声明的配置为命令行脚本生成GUI启动窗口**

在 bm-scripts-box-rc.toml 中，将 [bmscriptsbox.params_form] 设为 true 后，盒子会在用户启动脚本前，自动弹出一个交互式图形窗口。该窗口依据 TOML 文件中声明的 inputs（数据输入）与 params（运行参数）字段，动态生成对应的表单控件。用户填写完成后点击「执行」，盒子即会以所填参数启动脚本。

---

::: warning 适用边界：只适合弱交互脚本
这个能力**只适合弱交互的脚本**——单界面、字段填完即可运行。

**强交互的脚本无法用它实现**，例如：

- 需要**多个界面**（向导式、多步骤流程）
- 需要实时展示处理进度

这类脚本需要**自己写 GUI**（tkinter / WinForms / HTML），自动生成界面不适用。
:::

---

## 盒子怎么做到的

盒子读取你声明的两类字段，自动生成界面：

```plaintext
你在 TOML 声明字段（inputs / params）
        │  盒子读取声明
        ▼
盒子自动生成运行设置界面（免手写 GUI）
        │  用户填写后点「执行」
        ▼
盒子带这些参数启动你的脚本
```

**界面出现与不出现的场景：**

| 触发方式                     | 是否弹界面 | 说明               |
| ------------------------ | ----- | ---------------- |
| 卡片运行 / 右键菜单 / 快捷键 / 超级复制 | ✅ 弹   | 用户有机会在运行前配置参数    |
| 定时任务 / 脚本联动              | ❌ 不弹  | 无人值守场景，直接按默认参数运行 |

界面弹出时，会把触发携带的数据**预填**进「数据输入」区。右键选中的文件、快捷键路径、剪贴板文本都会预填，用户微调后「执行」即可。

---

## 三步上手

### 第一步：声明数据输入（`inputs`）

`inputs` 是脚本接收的主数据。给 `list` 类型配上 `pick`，界面用**本地路径选择器**接收（点击流量本地文件或文件夹，按 `exts` 过滤）：

```toml
[[bmscriptsbox.inputs]]
name = "target_paths"
type = "list"
pick = "files"          # 界面用文件选择器 / 不声明这个就是普通的输入框 / 具体可看[输入输出契约](./io-contract)文档
exts = [".jpg", ".png"]
```

### 第二步：声明运行参数（`params`）

`params` 是可调选项。控件类型由 `type` 决定，无需额外配置：

```toml
[[bmscriptsbox.params]]
name = "quality"
type = "int"
default = 80
description = "压缩质量（1-100）"
```

### 第三步：打开开关

```toml
[bmscriptsbox.params_form]
enabled = true   # 声明：运行本脚本前自动弹出设置界面
```

> - 不写 `params_form` 段 = 照旧直接运行，不弹界面。
> - 界面会自动回填**上次确认运行**时填写的 `params`；未改动过的字段以 TOML 默认值为准。
> - 改了声明后需**重新安装 / 更新**脚本才会让 UI 生效。

---

## 完整示例

> 一个「图片压缩」伪代码脚本，声明了一个数据输入和三个运行参数，盒子自动生成完整界面。

### 效果演示

![自动生成GUI效果演示](https://static.bm-box.cn/help_imgs/gui/gui-demo.gif)



### 代码文件

```python
import sys
import time
import json

def image_compress(paths:list, quality:int=80, keep_original:bool=True, output_format:str='png'):
    # 图片压缩函数(伪代码)
    print("--正在压缩图片--")
    time.sleep(2)
    print("--压缩完成--")

def main():
    # 启动函数
    if len(sys.argv) < 2:
        sys.exit(1)

    # 读取盒子注入的参数文件，路径由位置参数传入
    param_path = sys.argv[1]
    with open(param_path, "r", encoding="utf-8") as f:
        payload = json.load(f)

    # 从json中解析出数据和参数
    paths = payload.get("data",{}).get("paths", [])
    quality = payload.get("params", {}).get("quality", 80)
    keep_original = payload.get("params", {}).get("keep_original", True)
    output_format = payload.get("params", {}).get("output_format", "png")

    # 执行压缩
    image_compress(paths=paths, quality=quality, keep_original=keep_original, output_format=output_format)

if __name__ == '__main__':
    main()

# 非常简单的伪代码示例脚本、没有写任何GUI

```

### 配置文件

```toml
[bmscriptsbox]
[bmscriptsbox.info]
id = "a1b2c3d4-e5f6-7890-abcd-ef1234567890"
name = "图片压缩-测试"
desc = "选中图片后压缩，自动弹出渲染后的运行窗口、填写好参数后。点击运行即可"
version = "1.0.0"

[bmscriptsbox.runtime]
language = "python"
language_version = ">=3.8"
entry = "main.py"
terminal = "always"

[bmscriptsbox.triggers.context_menu]
enabled = true
targets = ["files"]
filters = [".jpg", ".jpeg", ".png", ".webp"]

# 第一步：数据输入，用户选要压缩的图片
[[bmscriptsbox.inputs]]
name = "paths"
type = "list"
pick = "files"          # 文件选择器(可选值files/folders/both)
description = "图片路径"
exts = [".jpg", ".jpeg", ".png", ".webp"]

# 第三步：打开自动生成界面
[bmscriptsbox.params_form]
enabled = true

# 第二步：运行参数，变成界面里的控件
[[bmscriptsbox.params]]
name = "quality"
type = "int"
default = 80
description = "压缩质量（1-100）"

[[bmscriptsbox.params]]
name = "keep_original"
type = "bool"
default = true
description = "是否保留原图"

[[bmscriptsbox.params]]
name = "output_format"
type = "str"
default = "webp"
choices = ["jpg", "png", "webp"]   # 渲染为下拉框控件
description = "输出格式"
```

### 盒子自动生成的界面

| 字段（控件）               | 来源     | 默认值       | 用户操作   |
| -------------------- | ------ | --------- | ------ |
| `paths`（文件选择器）       | inputs | 预填右键选中的图片 | 可增删图片  |
| `quality`（数字框）       | params | 80        | 调低压缩更小 |
| `keep_original`（开关）  | params | 开         | 可关闭    |
| `output_format`（下拉框） | params | webp      | 可切换格式  |

### 脚本端读取

用户点「执行」后，盒子按这些参数启动脚本，脚本从参数文件读取：

```python
import json, sys

payload = json.load(open(sys.argv[1], encoding='utf-8'))
paths   = payload["data"]["paths"]
quality = payload["params"].get("quality", 80)
keep    = payload["params"].get("keep_original", True)
fmt     = payload["params"].get("output_format", "webp")
```

---

## 控件速查表

| 参数 `type`       | 生成的控件                        |
| --------------- | ---------------------------- |
| `str`           | 文本输入框；声明了 `choices` 时变为下拉选择框 |
| `int` / `float` | 数字输入框                        |
| `bool`          | 开关                           |
| `list`          | 多行文本输入                       |
| `dict`          | JSON 输入框                     |
| `secret`        | 密码输入框（敏感参数）                  |

---

## 常见问题

**Q：不写 `params_form` 会怎样？**
A：照旧直接运行，不弹界面。

**Q：定时任务、脚本联动会弹界面吗？**
A：不会。它们无人值守，直接按默认参数运行，不打断流程。

**Q：界面里的数据从哪来？**
A：右键 / 快捷键 / 超级复制触发时，盒子把携带的数据（文件路径、剪贴板文本）预填进「数据输入」；卡片运行则空白。

**Q：改了声明不生效？**
A：改完 TOML 需要**重新安装 / 更新**脚本，UI 才会刷新。

---

## 相关文档

- 数据输入与 `pick` 本地路径选择器的完整规则 → [输入输出契约](./io-contract)
- 运行参数 `[[bmscriptsbox.params]]` 的所有字段 → [运行参数](./params)
- 不弹窗的自动场景 → [定时任务](./scheduled-task)、[脚本联动](./script-linking)