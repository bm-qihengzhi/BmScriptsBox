---
title: 完整示例
description: 6 个完整可运行的脚本示例（配置 + 代码），覆盖 5 种语言与联动场景，可直接复制作为起点。
status: 稳定
docType: tutorial
audience: 脚本开发者
docVersion: 0.3.0
---

# 完整示例

> **6 个真实脚本，覆盖盒子主要语言形态和典型触发、交互模式——直接复制作为起点。**

每个示例都是完整可运行的脚本（配置 + 代码）。你可以直接复制作为起点，也可以参考其中的配置和代码写法。

| 示例 | 语言 | 覆盖的能力 |
| --- | --- | --- |
| [一、Python 文件整理](#示例一-python-文件整理) | Python | 三种触发方式 + 路径参数处理 + 静默通知 |
| [二、Node.js 图片压缩](#示例二-node-js-图片压缩) | Node.js | 扩展名过滤 + 异步处理 + npm 依赖 |
| [三、BAT 清空回收站](#示例三-bat-清空回收站) | BAT | 无参数脚本 + 静默执行 + 快捷键 |
| [四、PowerShell 系统信息](#示例四-powershell-系统信息) | PowerShell | `str` 类型输入 + WMI 调用 + 文件输出 |
| [五、AutoHotkey 取色器](#示例五-autohotkey-取色器) | AutoHotkey | GUI 交互 + 剪贴板操作 |
| [六、脚本联动](#示例六-脚本联动-视频翻译-a-联动字幕提取-b) | Python + Python | 节点声明 + 依赖 + 信封回传 |

> EXE 和 HTML 不需要示例代码：EXE 直接填 `entry` 指向可执行文件，HTML 指向 `index.html`，在 `entry` 里写对即可。

如果你还在熟悉阶段，从示例一开始——它的配置最完整，注释也最详细。要做多脚本串联，直接看示例六。

---

用法：找需求最像的示例 → 复制它的配置和代码 → 改成你的逻辑 → 打包安装。

---

## 示例一：Python 文件整理

按文件扩展名自动分类整理，支持右键菜单和快捷键触发，处理完用气泡通知用户。

### 目录结构

```plaintext
file-sorter/
├── bm-scripts-box-rc.toml
├── pyproject.toml
├── main.py
└── icon/
    └── logo.png
```

### `bm-scripts-box-rc.toml`

```toml
[bmscriptsbox]

[bmscriptsbox.info]
id = "a1b2c3d4-e5f6-7890-abcd-ef1234567890"
name = "文件整理器"
desc = "按文件类型自动分类整理到对应文件夹"
icon = "icon/logo.png"
version = "1.0.0"

[bmscriptsbox.runtime]
language = "python"
language_version = ">=3.8"
entry = "main.py"
terminal = "never"

[bmscriptsbox.triggers.context_menu]
enabled = true
targets = ["background", "files"]

[bmscriptsbox.triggers.shortcut]
enabled = true
input_type = "items"

[[bmscriptsbox.inputs]]
name = "target_paths"
type = "list"
```

### `pyproject.toml`

```toml
[project]
name = "file-sorter"
version = "1.0.0"
requires-python = ">=3.8"
dependencies = [
    "send2trash>=1.8",
    "requests>=2.31",
]
```

### `main.py`

```python
import sys
import json
from pathlib import Path

import requests

# 文件类型 → 目标文件夹名称的映射
TYPE_MAP = {
    '.jpg': '图片', '.jpeg': '图片', '.png': '图片', '.gif': '图片', '.webp': '图片',
    '.doc': '文档', '.docx': '文档', '.pdf': '文档', '.txt': '文档', '.md': '文档',
    '.mp4': '视频', '.avi': '视频', '.mkv': '视频', '.mov': '视频',
    '.mp3': '音乐', '.wav': '音乐', '.flac': '音乐',
    '.zip': '压缩包', '.rar': '压缩包', '.7z': '压缩包',
    '.py': '代码', '.js': '代码', '.html': '代码', '.css': '代码',
}


def notify(api_base, text, ok=True):
    """terminal = "never" 时看不到终端，用桌面气泡告诉用户结果。"""
    try:
        requests.post(f"{api_base}/api/notify", json={
            "notify_type": "success" if ok else "error",
            "message": text,
            "duration": 3000,
        }, timeout=3)
    except requests.RequestException:
        pass    # 通知失败不影响主流程


def main():
    # 读取盒子传入的 JSON 参数文件
    param_path = sys.argv[1]
    with open(param_path, 'r', encoding='utf-8') as f:
        params = json.load(f)

    api_base = params['environment']['api_base']
    paths = params['data']['target_paths']
    output = {"sorted": [], "errors": []}

    for p in paths:
        src = Path(p)
        if not src.exists():
            output["errors"].append(f"文件不存在: {p}")
            continue

        # 按扩展名分类
        ext = src.suffix.lower()
        target_dir_name = TYPE_MAP.get(ext, '其他')
        dest = src.parent / target_dir_name / src.name
        try:
            dest.parent.mkdir(exist_ok=True)
            src.rename(dest)
            output["sorted"].append(str(dest))
        except OSError as e:
            output["errors"].append(f"{p}: {e}")

    # 通知用户处理完成
    summary = f"已整理 {len(output['sorted'])} 个文件"
    if output["errors"]:
        summary += f"，{len(output['errors'])} 个失败"
    notify(api_base, summary, ok=not output["errors"])

    # 同时打印到 stdout，盒子会捕获并在 UI 中展示
    print(json.dumps(output, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
```

---

## 示例二：Node.js 图片压缩

使用 sharp 库压缩选中的图片，只处理配置中指定的扩展名。

### `bm-scripts-box-rc.toml`

```toml
[bmscriptsbox]

[bmscriptsbox.info]
id = "b2c3d4e5-f6a7-8901-bcde-f12345678901"
name = "图片压缩"
desc = "使用 sharp 库压缩选中图片"
icon = "icon/logo.png"
version = "1.0.0"

[bmscriptsbox.runtime]
language = "node.js"
language_version = ">=v16.0"
entry = "main.js"
terminal = "never"

[bmscriptsbox.triggers.context_menu]
enabled = true
targets = ["files"]
filters = [".jpg", ".jpeg", ".png", ".webp"]

[[bmscriptsbox.inputs]]
name = "target_paths"
type = "list"
exts = [".jpg", ".jpeg", ".png", ".webp"]
```

### `package.json`

```json
{
    "name": "image-compressor",
    "version": "1.0.0",
    "engines": { "node": ">=16.0" },
    "dependencies": { "sharp": "^0.33.0" }
}
```

### `main.js`

```javascript
const fs = require('fs');
const path = require('path');
const sharp = require('sharp');

const paramPath = process.argv[2];
const params = JSON.parse(fs.readFileSync(paramPath, 'utf8'));
const paths = params.data.target_paths;

async function compress(imagePath) {
    const ext = path.extname(imagePath).toLowerCase();
    const dir = path.dirname(imagePath);
    const name = path.basename(imagePath, ext);
    const output = path.join(dir, `${name}_compressed${ext}`);

    if (ext === '.png') {
        await sharp(imagePath).png({ quality: 80 }).toFile(output);
    } else {
        await sharp(imagePath).jpeg({ quality: 80 }).toFile(output);
    }
    return output;
}

(async () => {
    const results = [];
    for (const p of paths) {
        try {
            const output = await compress(p);
            results.push({ input: p, output, status: 'ok' });
        } catch (err) {
            results.push({ input: p, error: err.message, status: 'failed' });
        }
    }
    console.log(JSON.stringify(results));
})();
```

---

## 示例三：BAT 清空回收站

最简单的 BAT 脚本，按快捷键直接触发，不需要任何输入参数。

### `bm-scripts-box-rc.toml`

```toml
[bmscriptsbox]

[bmscriptsbox.info]
id = "c3d4e5f6-a7b8-9012-cdef-123456789012"
name = "清空回收站"
desc = "一键清空 Windows 回收站"
version = "1.0.0"

[bmscriptsbox.runtime]
language = "bat"
language_version = ">=0.0.0"
entry = "main.bat"
terminal = "never"

[bmscriptsbox.triggers.shortcut]
enabled = true
input_type = "active"
```

### `main.bat`

```batch
@echo off
rd /s /q %systemdrive%\$Recycle.Bin 2>nul
```

> 注意：`language_version` 对 BAT 没有实际意义，但它是必填字段，填 `>=0.0.0` 即可。

---

## 示例四：PowerShell 系统信息

获取系统基本信息并保存到文件，演示了 `type = "str"`（单条文本）参数的用法。

### `bm-scripts-box-rc.toml`

```toml
[bmscriptsbox]

[bmscriptsbox.info]
id = "e5f6a7b8-c9d0-1234-efab-345678901234"
name = "系统信息"
desc = "获取操作系统基本信息并保存到桌面"
version = "1.0.0"

[bmscriptsbox.runtime]
language = "powershell"
language_version = ">=5.1"
entry = "main.ps1"
terminal = "never"

[bmscriptsbox.triggers.shortcut]
enabled = true
input_type = "active"

[[bmscriptsbox.inputs]]
name = "output_dir"
type = "str"
```

### `main.ps1`

```powershell
param($paramPath)
$params = Get-Content $paramPath -Encoding UTF8 | ConvertFrom-Json

# str 输入在 data 中是单元素数组，取 [0]；为空时回退到桌面
$outputDir = $params.data.output_dir[0]
if (-not $outputDir) {
    $outputDir = [Environment]::GetFolderPath('Desktop')
}

# 收集系统信息
$info = @{
    ComputerName   = $env:COMPUTERNAME
    OSVersion      = (Get-WmiObject Win32_OperatingSystem).Caption
    LastBoot       = (Get-CimInstance -ClassName Win32_OperatingSystem).LastBootUpTime
    TotalMemoryGB  = [math]::Round((Get-CimInstance Win32_ComputerSystem).TotalPhysicalMemory / 1GB, 2)
    LogicalCores   = (Get-CimInstance Win32_ComputerSystem).NumberOfLogicalProcessors
}

# 保存到文件
$outputFile = Join-Path $outputDir "system-info.json"
$info | ConvertTo-Json | Set-Content $outputFile -Encoding UTF8

Write-Output ($info | ConvertTo-Json)
```

---

## 示例五：AutoHotkey 取色器

点击后拾取鼠标所在位置的屏幕颜色，自动复制到剪贴板。

### `bm-scripts-box-rc.toml`

```toml
[bmscriptsbox]

[bmscriptsbox.info]
id = "d4e5f6a7-b8c9-0123-defa-234567890123"
name = "屏幕取色器"
desc = "点击后拾取鼠标位置的颜色，自动复制到剪贴板"
version = "1.0.0"

[bmscriptsbox.runtime]
language = "autohotkey"
language_version = ">=2.0.0"
entry = "main.ahk"
terminal = "always"
```

### `main.ahk`

```autohotkey
#Requires AutoHotkey v2.0

; 提示用户点击
ToolTip("点击任意位置拾取颜色...")
KeyWait("LButton", "D")
MouseGetPos(&mouseX, &mouseY)
ToolTip("")

; 获取并格式化颜色值
color := PixelGetColor(mouseX, mouseY)
colorHex := "#" . SubStr(color, 3)

; 复制到剪贴板
A_Clipboard := colorHex
MsgBox("颜色: " . colorHex . "`n已复制到剪贴板!", "取色完成")
```

> GUI 脚本记得把 `terminal` 设为 `"always"`，否则窗口可能被隐藏。

---

## 示例六：脚本联动（视频翻译 A 联动字幕提取 B）

两个脚本协作：**B（字幕提取）是节点**，负责从视频提取字幕并把结果写成信封；**A（视频翻译）是调用方**，通过盒子本地 API 同步调用 B，拿到字幕再"翻译"。装 A 时盒子会自动把 B 装好。

### B（字幕提取）—— 被调节点

#### `bm-scripts-box-rc.toml`

```toml
[bmscriptsbox]

[bmscriptsbox.info]
id = "f1a2b3c4-d5e6-4f7a-8b9c-0d1e2f3a4b5c"
name = "字幕提取(B)"
desc = "节点：接收视频路径，提取字幕，结果写入 output_json 信封"
version = "1.0.0"

[bmscriptsbox.runtime]
language = "python"
language_version = ">=3.8"
entry = "main.py"
terminal = "never"

[[bmscriptsbox.inputs]]
name = "video_paths"
type = "list"
exts = [".mp4", ".mkv", ".avi"]

[[bmscriptsbox.params]]
name = "language"
type = "str"
default = "auto"
choices = ["auto", "zh", "en", "ja"]

[[bmscriptsbox.outputs]]
name = "subtitle_path"
type = "str"
description = "提取出的字幕文件绝对路径（.srt）"

[bmscriptsbox.node]
enabled = true        # 声明可作为节点被联动调用（必须有 ≥1 个 outputs）
```

#### `main.py`

```python
import json, sys

payload = json.load(open(sys.argv[1], encoding='utf-8'))
env = payload["environment"]
video = payload["data"]["video_paths"][0]

# 伪实现：模拟提取字幕
subtitle_path = video.rsplit('.', 1)[0] + '.srt'

# 结果写成信封，写入盒子指定的 output_json
with open(env["output_json"], 'w', encoding='utf-8') as f:
    json.dump({"code": 0, "msg": "ok", "subtitle_path": subtitle_path}, f)
```

### A（视频翻译）—— 调用方

#### `bm-scripts-box-rc.toml`

```toml
[bmscriptsbox]

[bmscriptsbox.info]
id = "e2b3c4d5-f6a7-4b8c-9d0e-1f2a3b4c5d6e"
name = "视频翻译(A)"
desc = "联动调用 B(字幕提取) → 模拟翻译"
version = "1.0.0"

[bmscriptsbox.runtime]
language = "python"
language_version = ">=3.8"
entry = "main.py"
terminal = "always"

[bmscriptsbox.triggers.context_menu]
enabled = true
targets = ["files"]
filters = [".mp4", ".mkv", ".avi"]

[[bmscriptsbox.inputs]]
name = "video_paths"
type = "list"

[[bmscriptsbox.params]]
name = "target_lang"
type = "str"
default = "en"
choices = ["zh", "en", "ja"]

[[bmscriptsbox.dependencies]]
id = "f1a2b3c4-d5e6-4f7a-8b9c-0d1e2f3a4b5c"   # 依赖 B：安装 A 时自动装 B

# A 是调用方，不作为被调节点，因此不声明 [bmscriptsbox.node]
```

#### `main.py`

```python
import json, sys, requests

payload = json.load(open(sys.argv[1], encoding='utf-8'))
env = payload["environment"]
video = payload["data"]["video_paths"][0]

B_ID = "f1a2b3c4-d5e6-4f7a-8b9c-0d1e2f3a4b5c"

# 同步调用 B（/api/link 恒为同步）：盒子为 B 重建环境、执行、把信封读回
r = requests.post(f"{env['api_base']}/api/link", json={
    "script_id": B_ID,
    "data": {"video_paths": [video]},
    "params": {"language": "auto"},
}, timeout=3600)
body = r.json()

if not body.get("success"):
    raise RuntimeError(body.get("message", "联动调用失败"))
if body["result"].get("code") != 0:
    raise RuntimeError(body["result"].get("msg"))

subtitle = body["result"]["subtitle_path"]   # B 返回的业务键，信封顶层平铺
print(f"字幕已生成: {subtitle}，开始翻译为 {payload['params'].get('target_lang', 'en')} ...")
```

> A 用到了 `requests`，记得在 `pyproject.toml` 的 `dependencies` 中声明。完整机制（信封契约、防循环、错误码）见 [脚本联动](./script-linking)。
