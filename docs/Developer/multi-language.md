---
title: 多语言支持
description: 不忙脚本盒子多语言支持——7 种语言支持列表、决策表、language 与 language_version 声明规则。
status: 稳定
docType: reference
audience: 脚本开发者
docVersion: 0.3.0
---

# 多语言支持

盒子支持 Python、Node.js、PowerShell、BAT、AutoHotkey、HTML、EXE 七种形态的脚本。安装时自动下载所需运行时并配置环境变量，用户不需要手动安装任何东西。

每种语言的运行环境细节、依赖安装与部署流程见 [环境配置](./environment-config)。

---

## 支持的语言一览

| 语言标识 | 入口扩展名 | 需要依赖文件 | `language_version` | 运行时获取方式 |
| --- | --- | --- | --- | --- |
| `python` | `.py` | `pyproject.toml` | 必填，建议 `>=3.8` | 自动下载 Python |
| `node.js` | `.js` | `package.json` | 必填，建议 `>=16.0` | 自动下载 Node.js |
| `autohotkey` | `.ahk` | 无需 | 必填，填具体大版本号 | 自动下载 AHK 便携版 |
| `powershell` | `.ps1` | 无需 | 必填，建议 `>=5.1` | 调用系统 PowerShell |
| `bat` | `.bat` | 无需 | 必填，可填 `>=0.0.0` | 直接运行 |
| `html` | `.html` | 无需 | 必填，可填 `>=0.0.0` | 浏览器中打开 |
| `exe` | `.exe` | 无需 | 必填，可填 `>=0.0.0` | 直接执行 |

---

## 怎么选：决策表

不确定选哪个？按你的脚本用途对号入座：

| 你的脚本要做什么 | 选 |
| --- | --- |
| 数据处理、科学计算、AI 推理、复杂逻辑自动化 | Python |
| Web 服务、前端构建、npm 生态工具链 | Node.js |
| Windows 系统管理、注册表修改、COM 对象调用 | PowerShell |
| 极简批处理（复制/移动文件、执行几条命令） | BAT |
| 热键、窗口控制、键鼠自动化 | AutoHotkey |
| 纯前端可视化界面（配置面板、图表、控制台），不涉及后端逻辑 | HTML + JavaScript（盒子内嵌 WebView） |
| 已有编译好的 .exe 程序，或追求最快启动速度（无需解释器） | EXE |

---

## 声明语言与版本

在 `bm-scripts-box-rc.toml` 的 `[bmscriptsbox.runtime]` 段声明语言与版本：

```toml
[bmscriptsbox.runtime]
language = "python"           # 脚本语言（必填）
language_version = ">=3.8"    # 语言版本要求（必填）
```

### language 字段

填支持列表中的语言标识（如 `python`、`node.js`、`powershell`）。**入口文件的扩展名必须与 `language` 的值匹配**，否则安装时校验失败。入口文件的完整命名规则见 [脚本目录结构规范](./directory-structure)。

### language_version 字段

必须以比较运算符开头，后跟版本号。校验正则：`^(>=|<=|==|>|<)(?i:v)?\d+(\.\d+)*$`

| 正确 | 错误 |
| --- | --- |
| `>=3.8` | `3.8`（缺少运算符） |
| `==3.10.1` | `>= v16.0`（v 前不能有空格） |
| `>=v16.0` | `>=`（缺少版本号） |
| `>=V16` | — |

> PowerShell 建议填 `>=5.1`（盒子使用系统自带的 PowerShell）。bat、exe、html 可填 `>=0.0.0`。AutoHotkey 填具体大版本号（如 `>=2.0.0`）。

---

## 常见问题

**Q：`language_version` 怎么填？**
A：必须以比较运算符开头，后跟版本号，如 `>=3.8`、`>=v16.0`、`>=2.0.0`。bat / html / exe 可填 `>=0.0.0`。

---

## 相关文档

- 各语言运行环境细节 → [环境配置](./environment-config)
- 配置文件的全部字段 → [声明式接入](./declarative-access)
- 各语言的入口文件规则 → [脚本目录结构规范](./directory-structure)
- 终端窗口行为 → [终端模式详解](./terminal-mode)