---
title: 常见问题（开发指南）
description: 脚本开发排障手册：调试与参数、编码、触发器联动、安装失败等六类常见问题的原因和解决办法。
status: 稳定
docType: reference
audience: 脚本开发者
docVersion: 0.3.0
---

# 常见问题

> **出问题了？按你遇到问题的场景找答案。**

开发盒子脚本时踩坑了，先来这里查——**常见报错的原因与解决办法**按场景归类。这里没有的问题，可以在 [GitHub Issues](https://github.com/bm-qihengzhi/BmScriptsBox/issues) 提交。

---

## 调试与测试

### 如何测试我的脚本？

**推荐方式**：安装到盒子后，在「脚本管理」页面点击「运行」。

**手动调试**：构造一个 JSON 参数文件，在命令行里模拟盒子的调用，这样改代码不用反复打包安装：

```json
{
    "environment": {
        "workspace": "C:/Users/test/AppData/Local/Temp",
        "output_json": "C:/Users/test/AppData/Local/Temp/bms_test.out.json",
        "encoding": "utf-8",
        "api_base": "http://127.0.0.1:9527",
        "task_id": "00000000-0000-0000-0000-000000000000",
        "script_id": "afd522ed-0e2c-45f1-96c9-7ac02bb61639",
        "script_dir": "C:/BmScripts/afd522ed-..."
    },
    "data": {
        "target_paths": ["C:/Users/test/Desktop/test.txt"]
    },
    "params": {
        "language": "auto"
    }
}
```

保存为 `test_params.json`，然后直接跑：

```bash
# Python
python main.py C:/path/to/test_params.json

# PowerShell
powershell -ExecutionPolicy Bypass -File main.ps1 C:/path/to/test_params.json

# Node.js
node main.js C:/path/to/test_params.json

# BAT
main.bat C:/path/to/test_params.json

# AutoHotkey
AutoHotkey64.exe main.ahk C:/path/to/test_params.json
```

### 调试时看不到任何输出，怎么办？

大概率是 `terminal` 设成了 `"never"`——这个模式会把 stdout 全部丢弃。调试期间改成 `"always"`，确认没问题后再改回去。详见 [终端模式详解](./terminal-mode)。

### 脚本一闪而过，来不及看输出？

两个办法：

1. 把 `terminal` 设为 `"always"`，窗口会保留
2. 在脚本末尾加暂停（仅 CLI 交互脚本推荐）：

```python
input("按回车键退出...")
```

### 中文输出乱码？

Python 环境下盒子已自动设置 `PYTHONIOENCODING=utf-8` 和 `PYTHONUTF8=1`，正常不会乱码。如果仍乱码：

- 确认脚本文件本身保存为 **UTF-8** 编码
- 读写文件时显式指定编码：`open(path, 'r', encoding='utf-8')`
- BAT 脚本在开头加 `chcp 65001` 切换到 UTF-8 代码页

---

## 参数与结果

### 脚本如何返回处理结果？

**普通触发时**，直接 `print()` 到 stdout 即可（盒子会捕获并展示），也可以弹窗、写文件、发通知：

```python
print(json.dumps({"status": "ok", "count": 42}, ensure_ascii=False))
```

**被其他脚本联动调用时**，必须把结果写成信封写入 `environment.output_json`：

```python
env = payload["environment"]
with open(env["output_json"], 'w', encoding='utf-8') as f:
    json.dump({"code": 0, "msg": "ok", "subtitle_path": "C:/tmp/a.srt"}, f)
```

信封格式 `{"code": int, "msg": str, ...业务键}`，详见 [脚本联动](./script-linking)。

### 脚本如何获取资源管理器选中的文件路径？

**你不需要自己获取。** 盒子在触发时已通过 Windows COM 接口拿到路径，通过 JSON 参数文件传给你。脚本读 `sys.argv[1]` 即可，详见 [参数注入](./parameter-passing)。

### 我声明了多个 `[[inputs]]`，为什么报错？

当前版本 `inputs` **最多只能声明 1 条**（主数据）。需要传多个文件或多个参数时，用 `params` 的 `str` 类型声明路径参数。详见 [运行参数](./params)。

---

## 配置与格式

### 图标有什么要求？

- **格式**：PNG、SVG 或 ICO
- **尺寸**：建议 256×256（最大 256×256）
- **路径**：在 `info.icon` 中配置，必须是**相对于脚本根目录的相对路径**
- 未配置时显示默认图标

### 版本号格式是什么？

必须是 `x.y.z` 格式（纯数字），遵循语义化版本：

- ✅ `1.0.0`、`2.3.1`、`10.0.0`
- ❌ `1.0`（缺一位）、`v1.0.0`（带 v 前缀）

### `language_version` 如何填写？

必须以比较运算符开头，后跟版本号：

| 正确示例 | 说明 |
| --- | --- |
| `>=3.8` | Python >= 3.8 |
| `==3.10.1` | 精确锁定 Python 3.10.1 |
| `>=v16.0` | Node.js >= 16.0 |
| `>=2.0.0` | AutoHotkey 大版本 2.x |
| `>=0.0.0` | BAT / HTML / EXE 填这个 |

| 错误示例 | 原因 |
| --- | --- |
| `3.8` | 缺少比较运算符 |
| `>= v16.0` | 运算符和版本号之间不能有空格 |
| `>=` | 缺少版本号 |

> 所有语言均为必填项，没有默认版本。

---

## 运行环境

### Python 最低支持版本？

最低 3.8。

### Node.js 最低支持版本？

最低 16.0。

### 可以在脚本中使用 GUI 吗？

可以：

- **Python**：便携版包含 tkinter，可直接使用
- **AutoHotkey**：原生支持 GUI
- **PowerShell**：可使用 .NET WinForms
- **Node.js**：可使用 HTML 或 webview

> GUI 脚本建议把 `terminal` 设为 `"always"`，避免窗口被隐藏。

### 脚本用了第三方库，需要我手动装吗？

不需要。在 `pyproject.toml`（Python）或 `package.json`（Node.js）里声明，盒子安装时自动装好。详见 [环境配置](./environment-config)。

---

## 触发器

### 右键菜单没有出现？

按顺序检查：

1. `context_menu.enabled` 是否为 `true`
2. `targets` 是否包含你右键的位置（文件上选 `files`，文件夹上选 `directory`，空白处选 `background`）
3. 如果配了 `filters`，**所有**选中文件的扩展名都必须匹配，否则菜单不显示
4. 安装完成后是否重启了资源管理器（盒子通常会自动处理，偶尔需要手动重启）

### 快捷键设置后不生效？

具体按键组合在盒子的「热键管理」页面设置，不在 TOML 里。检查：

1. 脚本的 `shortcut.enabled` 是否为 `true`
2. 是否已在热键管理页面绑定按键
3. 该组合键是否被其他脚本占用（后设置的会抢占）

---

## 脚本联动

### 联动调用返回 403「未声明可作为节点」？

被调脚本的 TOML 里没写节点声明。给它加上并重新安装：

```toml
[bmscriptsbox.node]
enabled = true
```

注意：声明 `node` 时必须同时有 ≥1 个 `[[bmscriptsbox.outputs]]`；改配置后要**重新安装**脚本让 `is_node` 生效。节点概念与误区见 [节点](./node)。

### `result.code == -3` 是什么意思？

格式错误。被调脚本没写 `output_json` 信封，或信封缺 `code` / `msg`，或 `code` 不是整数。按契约写全：

```python
json.dump({"code": 0, "msg": "ok", "你的业务键": 值}, f)
```

完整错误码见 [脚本联动](./script-linking)。

---

## 安装与分发

### 脚本安装失败怎么办？

安装日志会显示详细错误。常见原因与对策：

| 现象 | 原因 | 对策 |
| --- | --- | --- |
| 提示配置项不合法 | TOML 语法错误或 Pydantic 校验不通过 | 对照[配置校验错误对照表](./declarative-access#配置校验错误对照表)逐项检查 |
| 卡在下载运行时 | 网络问题 | 盒子会自动重试；持续失败可检查网络或代理设置 |
| `uv sync` / `pnpm install` 报错 | 依赖版本冲突或包名写错 | 检查 `pyproject.toml` / `package.json` 中的依赖声明 |
| 提示权限不足 | 注册右键菜单需要管理员权限 | 以管理员身份运行盒子 |
| 提示「缺少依赖」 | 声明的 `dependencies` 里有脚本未发布到社区 | 确认被依赖脚本已发布，或先手动安装它 |

### 发布到社区后，用户收不到更新？

检查 Webhook 是否配置。Webhook 是开发者推送新版本的**唯一通道**——不配置，用户永远看不到新版本。详见 [发布脚本到社区](./publish-community)。

### 更新后脚本市场页面没变化？

可能是 CDN 缓存导致页面静态内容未实时刷新，稍等或刷新重试。