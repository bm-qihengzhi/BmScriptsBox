---
title: 环境配置
description: 不忙脚本盒子环境配置——每种语言的运行方式、依赖文件、盒子安装流程与注入的环境变量。
status: 稳定
docType: reference
audience: 脚本开发者
docVersion: 0.3.0
---

# 环境配置

> **每种语言装进盒子后，环境是怎么搭起来的：运行时从哪来、依赖怎么声明、盒子安装期做什么。**

语言标识的声明方式与版本规则见 [多语言支持](./multi-language)。本页聚焦运行时、依赖与安装流程。

---

## 运行方式速览

| 语言 | 运行时来源 | 需要依赖文件 | 是否需要用户安装 |
| --- | --- | --- | --- |
| Python | 自动下载便携版 | `pyproject.toml` | 否 |
| Node.js | 自动下载 | `package.json` | 否 |
| PowerShell | 系统自带 | 无 | 否 |
| BAT | 系统自带 | 无 | 否 |
| AutoHotkey | 自动下载便携版 | 无 | 否 |
| HTML | 浏览器打开 | 无 | 否 |
| EXE | 直接执行 | 无 | 否 |

---

## Python

**运行方式**：盒子自动下载匹配版本的便携版 Python，并创建 `.venv` 虚拟环境。

**依赖文件**：需提供 `pyproject.toml`(无依赖时也要提供、只要是python开发的。就要提供这个文件)

```toml
[project]
name = "file-classifier"
version = "1.0.0"
requires-python = ">=3.8"   # 这里声明的版本要与toml文件中的一致
dependencies = [
    "pillow>=10.0",
    "send2trash>=1.8",
]
```

**安装流程**：

1. 检查目录下是否存在 `.venv` 虚拟环境
2. 如果不存在，下载匹配版本的**便携版 Python**（不会注入环境变量）
3. 创建 `.venv` 虚拟环境
4. 如果 `dependencies` 为空，**跳过虚拟环境创建和依赖安装**，直接用便携版 Python 运行
5. 配置 UV 国内镜像和硬链接缓存
6. 使用 `uv sync` 安装依赖
7. 设置环境变量 `PYTHONIOENCODING=utf-8` 和 `PYTHONUTF8=1`，避免中文乱码

**注意事项**：Python 包含 tkinter 支持，脚本可以直接用。Python 版本最低支持 3.8。

---

## Node.js

**运行方式**：盒子自动下载匹配版本的 Node.js，并用 PNPM 安装依赖。

**依赖文件**：需提供 `package.json`(无依赖时也要提供、只要是Node开发的。就要提供这个文件)

```json
{
    "name": "webp-converter",
    "version": "1.0.0",
    "engines": {
        "node": ">=16.0"
    },
    "dependencies": {
        "sharp": "^0.33.0"
    }
}
```

**安装流程**：

1. 下载匹配版本的 Node.js
2. 获取 PNPM 包管理器
3. 生成 `.npmrc` 配置文件（配置国内镜像源和缓存）
4. 执行 `pnpm install` 安装依赖


**注意事项**：Node最低支持>=16  版本号格式建议带 `v` 前缀，如 `>=v16.0`。若用 TypeScript，先编译为 JS，把 `entry` 指向编译产物。

---

## PowerShell

**运行方式**：使用 PowerShell 7运行

**依赖文件**：无需。

**安装流程**：自动下载便携版Powershell 7。

**注意事项**：建议填 `>=5.1`(无论填什么、都用powershell7运行、但是必要要填)。

---

## BAT

**运行方式**：直接运行，无需额外下载。

**依赖文件**：无需。

**安装流程**：无。系统自带，安装即用。

**注意事项**：版本要求可填默认值 `>=0.0.0`。BAT 自身没有解析 JSON 的能力，需要解析参数时在 BAT 中调用 PowerShell 辅助处理（示例见 [参数注入](./parameter-passing)）。

---

## AutoHotkey

**运行方式**：盒子自动下载 AHK 便携版，适合 Windows GUI 自动化。

**依赖文件**：无需。

**安装流程**：自动下载对应大版本的最新 AHK 便携版。

**注意事项**：版本号**不要带 `v` 前缀**，填具体大版本号即可，如 `>=2.0.0`（锁定大版本 2.x）。

---

## HTML

**运行方式**：webview运行（效果像原生GUI）。

**依赖文件**：无需。

**安装流程**：会自动下载webview-cli命令行工具、并通过该工具运行html。实现GUI效果

**注意事项**：无

---

## EXE（Go、Rust、C++、C# 等编译型语言）

**运行方式**：直接执行，盒子不额外下载运行时，安装即用。

**依赖文件**：无需。

**安装流程**：无。

**注意事项**：其他语言开发的脚本、如Rust GO C++ C# 这类语言打包EXE的体积小、可直接打包为单文件exe、接入到盒子中 

---

## 环境变量

脚本执行时，盒子会设置以下环境变量，你不需要在脚本中额外处理。

### 全局设置

| 变量 | 值 | 作用 |
| --- | --- | --- |
| `PATH` | 追加运行时可执行文件目录 | 让脚本能直接调用运行时命令 |
| `PYTHONPATH` | **已清除** | 避免系统 Python 的第三方库污染脚本的模块导入 |

### Python 专用

| 变量 | 值 | 作用 |
| --- | --- | --- |
| `PYTHONIOENCODING` | `utf-8` | 确保 `print()` 等标准输出正确显示中文 |
| `PYTHONUTF8` | `1` | 开启 Python UTF-8 模式，统一文件读写编码 |

---

## 常见问题

**Q：GUI 脚本（tkinter 等）能用吗？**
A：能。便携版 Python 包含 tkinter，AHK 原生支持 GUI。记得把 `terminal` 设为 `"always"`。

**Q：脚本用了第三方库，需要用户手动装吗？**
A：不需要。在 `pyproject.toml`（Python）或 `package.json`（Node.js）里声明，盒子安装时自动装好。

---

## 相关文档

- 语言标识与版本声明 → [多语言支持](./multi-language)
- 依赖外部命令行工具 → [工具托管](./external-binaries)
- 需要 AI 模型 → [模型管理](./model-download)
- 各语言的入口文件规则 → [脚本目录结构规范](./directory-structure)
- 终端窗口行为 → [终端模式详解](./terminal-mode)