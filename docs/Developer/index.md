---
title: 脚本开发指南 - Python / PowerShell 脚本接入
description: 不忙脚本盒子脚本开发总览——7 项能力对应哪篇文档、按任务选读的索引表。
status: 稳定
docType: explanation
audience: 脚本开发者
docVersion: 0.3.0
---

# 脚本开发总览

> **声明脚本的形态、触发方式与参数。盒子负责环境、触发、界面、协作与分发——脚本逻辑之外的部分不需要手写。**

不忙脚本盒子是一款 Windows 跨语言脚本管理软件，支持 Python、Node.js、PowerShell、AutoHotkey、BAT、HTML、EXE 七种脚本形态。它负责脚本运行环境、依赖、触发入口与分发。脚本因此装好就能跑、右键就能用、能定时、能协作、能发布。

---

## 盒子提供的能力一览

| 能力 | 说明 | 相关文档 |
| --- | --- | --- |
| **把脚本变成软件** | 自动装运行时、装依赖，脚本直接可运行 | [5 分钟快速上手](./quick-start) → [脚本运行机制](./run-mechanism) |
| **多场景触发** | 右键菜单、快捷键、超级复制、搜索触发、定时任务，一键接入 | [右键菜单](./context-menu) / [快捷键](./hotkey) / [超级复制](./quick-copy) / [搜索触发](./search-trigger) |
| **免写 GUI** | 声明参数，盒子自动生成运行设置界面 | [自动生成运行界面](./auto-generated-ui) |
| **数据进出** | 选中文件、剪贴板文本自动传进脚本，结果自动回传 | [参数注入](./parameter-passing) → [输入输出契约](./io-contract) |
| **环境一键就绪** | 7 种语言、外部工具、AI 模型全部自动下载配置 | [环境配置](./environment-config) |
| **脚本协作** | 脚本调脚本，组合出复合功能 | [脚本联动](./script-linking) |
| **单实例与并发** | 默认单实例；GUI 脚本可声明 `forward`，由脚本转发后续参数 | [单实例与并发](./single-instance) |
| **交付分发** | ZIP 打包、Git 分发、发布到社区自动更新 | [打包与分发](./packaging-distribution) |

---

## 怎么用这个文档

**不用按顺序读。** 找到你要做的事，读那几篇就够了：

| 我要做什么 | 读这几篇 |
| --- | --- |
| 5 分钟跑通第一个脚本 | [5 分钟快速上手](./quick-start) |
| 搞懂盒子怎么跑我的脚本 | [脚本运行机制](./run-mechanism) |
| 让脚本出现在右键 / 快捷键 | [右键菜单](./context-menu) / [快捷键](./hotkey) → [参数注入](./parameter-passing) |
| 让搜索框内容触发脚本 | [搜索触发](./search-trigger) |
| 控制脚本弹不弹窗口 | [终端模式详解](./terminal-mode) |
| 让 GUI 脚本接收后续触发参数 | [单实例与并发](./single-instance) |
| 让用户运行前配置参数 | [自动生成运行界面](./auto-generated-ui) |
| 用第三方库 / 外部工具 | [环境配置](./environment-config) → [工具托管](./external-binaries) |
| 脚本要用到 AI 模型 | [模型管理](./model-download) |
| 脚本定时自动运行 | [定时任务](./scheduled-task) |
| 把多个脚本串起来 | [节点](./node) → [脚本联动](./script-linking) → [HTTP API](./http-api/) |
| 把脚本发给别人 / 发布到市场 | [打包与分发](./packaging-distribution) → [发布脚本到社区](./publish-community) |
| 看看别人怎么写的 | [完整示例](./examples) |
| 出问题了 | [常见问题](./faq) |

---

## 盒子怎么运行你的脚本

整个机制只有一句话：**盒子启动时，把一个 JSON 参数文件的路径塞进命令行第一个参数。你的脚本读它、干活、退出。**

```bash
# 盒子实际执行的命令，就长这样
python main.py "C:/Users/xxx/AppData/Local/Temp/a1b2c3d4.json"
#              └── 命令行第一个参数 = 参数 JSON 文件的路径
```

没有 SDK，没有 import，没有基类要继承。你的脚本换个地方照样能跑，只是没人给它传参数而已。详细机制见 [脚本运行机制](./run-mechanism)。

---

## 声明式接入

盒子遵循**声明式接入**：只需要一个 `bm-scripts-box-rc.toml` 文件，用纯文本声明"脚本叫什么、用什么语言写、在哪里触发"。剩下的交给盒子。

| 维度 | 传统 SDK / 插件方式 | 不忙脚本盒子（声明式接入） |
| --- | --- | --- |
| 代码侵入 | 需要 import sdk、继承基类、实现固定接口 | 零侵入，原生脚本，无需任何改动 |
| 学习成本 | 需要学习 SDK 的 API 规范 | 会写脚本就会用 |
| 配置文件 | XML / JSON 配置 + 代码注解混合 | 单一 TOML 文件，纯声明，无逻辑 |
| 触发集成 | 需要在代码中注册事件监听 | 在 TOML 中声明 `enabled = true` 即可 |
| 环境管理 | 用户自己装语言、配环境变量 | 盒子全自动处理 |
| 迁移成本 | 换平台需重写接口适配层 | 本身就是标准脚本，随时可独立运行 |

配置文件的所有字段见 [配置文件详解](./declarative-access)。

---

## 还没实现的功能

文档中标 🚧 的条目表示当前版本不可用，属于预留设计：

- 🚧 [工作流](./workflow) — 声明式编排引擎。现在要调用别的脚本，请用 [脚本联动](./script-linking)。

---

如果你发现文档中有错误，欢迎在 [GitHub Issues](https://github.com/bm-qihengzhi/BmScriptsBox/issues) 提交。