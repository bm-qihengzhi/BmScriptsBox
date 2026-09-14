<p align="center">
  <img src="docs/images/logo.svg" width="30%" alt="安装脚本动画演示">
  <br>
</p>

<h1 align="center">不忙脚本盒子 / BmScriptsBox</h1>

<p align="center">
  <strong>Windows 跨语言脚本调度与管理软件</strong>
  <br>
  零门槛上手 · 全自动化环境部署 · 海量脚本一键运行
</p>

<p align="center">
  <img src="https://img.shields.io/badge/license-MIT%20%2B%20Commons%20Clause-blue" alt="License">
  <img src="https://img.shields.io/badge/python-≥3.8-orange" alt="Python">
  <img src="https://img.shields.io/badge/platform-Windows%2010%2F11-lightgrey" alt="Platform">
  <img src="https://img.shields.io/badge/status-beta-yellow" alt="Status">
</p>
<p align="center">
  <a href="https://www.bm-box.cn">官网</a> ·
  <a href="https://www.bm-box.cn/help">帮助中心</a> ·
  <a href="https://www.bm-box.cn/feedback">需求反馈</a>
  <br>
  <sub>Windows 10/11 · 完全免费 · 无功能限制</sub>
</p>

---

## 简介

不忙脚本盒子是一款 Windows 端跨语言桌面脚本管理工具，主打**零配置、零命令行、开箱即用**

无需编程基础，就可以像管理手机 App 一样，可视化安装各类脚本。平台内置办公、图像、音视频、系统、AI 等多场景脚本资源，支持一键部署、定时自动执行、全局快捷键快速唤起，轻松实现批量处理、日常办公、个性化自动化，满足各类效率需求



---

## 面向普通用户

零命令行、零基础上手，所有脚本可视化操作，轻量化、高效率，大幅降低工具使用门槛。

- **免费无限制**
  完全开源免费，无功能阉割、无使用限制，不限脚本安装数量，可随心拓展各类实用工具。

- **可视化操作**
  脚本安装、启动、管理、卸载全可视化一键操作，体验如同管理手机APP，零基础用户也能轻松上手，无需专业知识。

- **极速便捷唤醒**
  支持鼠标中键单击、双击 Ctrl 快捷键两种唤醒方式，随时随地秒开脚本面板，无需查找桌面图标、文件夹，操作高效省心。

- **内置脚本社区**
  内嵌官方脚本社区，支持一键检索、一键安装优质脚本，已安装脚本自动检测、更新，无需手动维护升级。

- **纯图形化启动**
  全程脱离命令行，点击盒子内脚本卡片即可一键启动，彻底告别繁琐的终端输入操作，便捷性拉满。

- **系统右键启动**
  支持脚本挂载至系统右键菜单，选中文件、文件夹即可右键启动，自动带入文件路径参数，无需手动输入配置。

- **自定义全局热键**
  可为任意脚本绑定专属全局快捷键，全程无需挪动鼠标、离开键盘，一键快速触发脚本运行。

- **超级复制传参**
  选中任意文字，连按两次 Ctrl\+C，自动将剪贴板内容作为参数传入脚本，省去手动复制、粘贴、输入参数的繁琐步骤。

- **无人值守定时任务**
  支持灵活的定时规则配置，涵盖一次性执行、每日、每周、每月循环执行，设置完成后自动运行，无需人工值守操作。

## 面向脚本开发者

脚本接入盒子仅需一份 TOML 声明，零侵入改造，让命令行脚本降低使用门槛，普通人也能轻松上手。[详细脚本开发文档](https://bm-box.cn/help/api)

* **环境依赖自动配置**
  
  * 自动创建虚拟环境，一键完成环境与依赖安装，支持硬链接缓存共享
  * FFmpeg、Pandoc 等工具，声明即可自动下载并注入环境变量，多脚本共用一份资源
  * HuggingFace、ModelScope 模型按需拉取，跨脚本复用，减少重复下载

* **命令行脚本一键生成图形界面**
  
  * TOML 声明即可生成界面
  * 无需学习 UI 框架、不用编写GUI代码，界面自动渲染
  * 终端脚本秒变可视化工具，用户开箱即用，无需掌握命令行

* **定时任务，声明即调度**
  
  * 仅需配置声明，由盒子托管定时触发，到点自动执行脚本
  * 参数配置自动映射到可视化面板，用户填好设置即可生效
  * 开发者无需编写定时调度底层代码

* **多场景脚本参数注入**
  
  * 支持右键菜单、全局快捷键、剪贴板、选中文件路径自动作为参数传入脚本
  * 一份 JSON 三段契约，脚本只读，规则清清楚楚
  * 结果有统一信封和预设错误码，返拿、判错都不用自己造

* **脚本之间轻松协作调用**
  
  * 脚本可调用其他脚本，同步等待执行结果
  * 内置友好 HTTP 调用接口，无需额外开发服务代码
  * 声明依赖脚本，盒子自动安装

* **从开发到分发，盒子全链路支持**
  
  * 三种安装源：本地 ZIP 包、GitHub 仓库、脚本社区
  * 提交 GitHub 仓库地址，一键发布脚本至社区
  * 配置 Webhook，GitHub 代码推送后，社区脚本自动更新

---

### 项目结构

```
BmScriptsBox/
├── app/                        # 核心应用代码
│   ├── cloud/                  # 云端服务（脚本市场、更新）
│   ├── data/                   # 数据层（SQLite 数据库）
│   ├── resources/              # 资源文件（图标、i18n、语言包）
│   ├── servers/                # 后端服务层
│   │   ├── context/            # 右键菜单管理
│   │   ├── environment/        # 运行时环境部署（Python/Node.js/AHK）
│   │   ├── explorer/           # 文件浏览器集成
│   │   ├── http_local/         # 本地 HTTP 接口
│   │   ├── monitor/            # 监控服务
│   │   ├── packages/           # 包管理器（uv/python/node/pnpm 分发）
│   │   ├── scheduled_core/     # 定时任务引擎
│   │   └── scripts/            # 脚本安装/管理
│   ├── utils/                  # 工具函数
│   ├── view/                   # 前端 UI 层
│   │   ├── context_ui/         # 右键菜单 UI
│   │   ├── fast_text_ui/       # 快捷文本 UI
│   │   ├── hotkey_ui/          # 热键设置 UI
│   │   ├── index_ui/           # 主窗口
│   │   ├── scheduled_ui/       # 定时任务 UI
│   │   ├── script_ui/          # 脚本管理 UI
│   │   ├── setting_ui/         # 设置 UI
│   │   └── update_ui/          # 更新 UI
│   └── works/                  # 工作线程
├── main.py                     # 应用入口
├── pyproject.toml              # Python 项目配置
└── LICENSE                     # MIT + Commons Clause 许可证
```

### 核心技术栈

| 组件     | 技术选型                                                          |
| ------ | ------------------------------------------------------------- |
| GUI 框架 | PySide2 (Qt 5.15)                                             |
| UI 组件库 | [XSideUI](https://github.com/bmscriptsbox/xsideui)（PySide美化库） |
| 数据库    | Peewee ORM + SQLite                                           |
| 本地 API | Flask (嵌入式 HTTP 服务)                                           |
| 包管理    | uv (Python 依赖) / pnpm (Node 依赖)                               |
| 运行时分发  | 自研 PackagesManager (自动下载 uv/python/node/pnpm)                 |
| 版本管理   | pydantic 配置模型                                                 |
| 热键监听   | pynput / keyboard                                             |
| 定时调度   | schedule                                                      |

---

## 安装

### 方式一：下载安装包

从 [GitHub Releases](https://github.com/bmscriptsbox/BmScriptsBox/releases) 下载最新的安装包，双击安装即可。

### 方式二：从源码运行

```bash
# 1. 克隆仓库
git clone https://github.com/bmscriptsbox/BmScriptsBox.git
cd BmScriptsBox

# 2. 确保 Python ≥ 3.8
python --version

#3. 创建虚拟环境
uv venv

# 4. 同步依赖
uv sync

# 5. 运行
python main.py
```

> **注意**：首次运行时会自动下载 uv、Python 嵌入式运行时等依赖，请保持网络畅通。

---

## 脚本开发

开发者可以基于 [TOML 声明式配置](https://www.bm-box.cn./help/api/pei-zhi-wen-jian) 编写脚本，实现一键接入：

```toml
[bmscriptsbox]

# ====== 1. 基本信息 ======
[bmscriptsbox.info]
id = "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx"   # UUID v4（必须）
name = "文件分类器"                            # 脚本显示名称（必须，至少1个字符）
desc = "自动按文件类型分类整理"                  # 描述说明（可选）
icon = "icon/logo.png"                        # 图标路径（相对路径，可选）
version = "1.0.0"                             # 语义化版本号（必须，格式: x.y.z）

# ====== 2. 运行环境 ======
[bmscriptsbox.runtime]
language = "python"               # 脚本语言（必须，见支持列表）
language_version = ">=3.8"        # 语言版本要求（所有语言必填，bat/exe 可填 >=0.0.0）
entry = "main.py"                 # 入口文件路径（必须，相对路径）
terminal = "always"               # 终端模式（可选，建议始终显式填写）
binaries = [{name = "7zip"}]      # 依赖的外部二进制工具（可选）

# ====== 3. 触发器配置 ======
[bmscriptsbox.triggers]

  [bmscriptsbox.triggers.context_menu]
  enabled = true
  targets = ["files", "directory", "background"]
  filters = [".txt", ".md"]

  [bmscriptsbox.triggers.shortcut]
  enabled = true
  input_type = "files"
  filters = [".txt"]

  [bmscriptsbox.triggers.quick_copy]
  enabled = false

# ====== 4. 输入参数定义 ======
[[bmscriptsbox.inputs]]
name = "target_paths"
type = "paths"
exts = [".txt", ".md", ".py"]

# ====== 5. 输出参数定义（预留，暂未使用）=====
[[bmscriptsbox.outputs]]
name = "result"
type = "text"

# ====== 6. 工作流配置（预留，暂未使用）=====
[bmscriptsbox.workflow]
workflow_enabled = true
```

详细脚本开发文档请参考 [脚本开发指南](https://www.bm-box.cn/help/api)。

---

## 贡献指南

欢迎贡献脚本、提交 Issue 或 Pull Request！

1. Fork 本仓库
2. 创建特性分支 (`git checkout -b feature/amazing-feature`)
3. 提交改动 (`git commit -m 'Add amazing feature'`)
4. 推送到分支 (`git push origin feature/amazing-feature`)
5. 提交 Pull Request

---

## 许可证与使用限制

### 开源许可

本项目基于 **MIT License + Commons Clause** 开源

### 禁止商用

**本项目仅供个人学习、研究及非商业用途。未经作者明确书面授权，任何个人或组织不得将本软件用于任何商业目的，包括但不限于：**

- 将本软件或修改版本直接用于商业产品销售
- 将本软件打包为商业服务的一部分进行收费
- 利用本软件搭建商业服务平台

如需商业授权，请联系作者：[bmscriptsbox@163.com](mailto:bmscriptsbox@163.com)

### 版权

Copyright © 2026 綦恒智 (Qi Hengzhi)

---


