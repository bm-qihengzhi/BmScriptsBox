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
  <img src="https://img.shields.io/badge/license-AGPL--3.0-blue" alt="License">
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

**不忙脚本盒子** 是一款 Windows 跨语言的桌面脚本管理工具，主打**零配置、全场景、易上手、高稳定**，内置了办公、图像、音视频、系统、AI 等各类常用场景的优质脚本，支持多语言脚本一键部署、自动化调度、全局快捷调用，全方位满足日常办公、批量处理、自定义自动化需求。核心功能特性如下：

---

## 功能特性
### 🚀 零门槛上手
> 不用配置、不用学习，打开就能用，轻松实现自动化
* **开箱即用**：图形界面操作，脚本一键安装、一键运行，零基础也能快速上手。
* **优质脚本库**：内置办公、文件、运维等常用脚本，支持搜索，一键部署。
* **声明式接入**：只需一个TOML配置文件即可接入自定义脚本，灵活又省事。

### ⚡ 多模式高效触发
> 想怎么启动就怎么启动，省去手动操作，一键唤起脚本。
* **全局快捷键**：自定义热键，随时随地一键启动，自动传入选中文件路径。
* **右键联动**：在文件或文件夹上右键，直接运行脚本，自动携带路径参数。
* **复制唤起**：按 Ctrl+C+C，自动读取剪贴板内容作为参数，文本处理超方便。
* **定时任务**：支持一次性或每天/每周/每月循环，无人值守自动执行。

### 🛠️ 多语言适配
> 兼容各类编程语言，自动处理环境问题，让脚本运行更稳定、无冲突。
* **语言全覆盖**：支持 Python、JS、PowerShell、Bat、AHK、EXE、HTML 等，满足多样场景
* **智能依赖托管**：自动识别、下载和清理依赖，无需人工维护。
* **独立运行环境**：每个脚本独享虚拟环境，互不干扰，杜绝版本冲突。

### 💾 资源高效利用
> 通过共享与加速机制，减少重复下载，节省存储空间，提升运行效率。。
* **依赖全局共享**：Python、Node.js 依赖硬连接，多脚本共用，避免重复存储，加载更快。
* **工具统一复用**：FFmpeg、Pandoc 等命令行工具全局复用，减少冗余。
* **AI 模型共享**：huggingface、modelscope 等模型一次下载，多脚本共用。
* **自动匹配版本**：自动识别脚本适配版本，精准匹配最优运行环境，无需手动切换配置。
* **GitHub加速下载**：优化海外资源下载，解决下载慢、中断、失败问题，提升部署效率。


## 界面预览

<div style="display: flex; gap: 10px; justify-content: center;">
  <img src="docs/images/ui-1.png" width="30%" alt="主窗口截图">
  <img src="docs/images/ui-2.png" width="30%" alt="主窗口截图">
  <img src="docs/images/ui-3.png" width="30%" alt="主窗口截图">
</div>
<br>
<div style="display: flex; gap: 10px; justify-content: center;">
  <img src="docs/images/ui-4.png" width="30%" alt="主窗口截图">
  <img src="docs/images/ui-5.png" width="30%" alt="主窗口截图">
  <img src="docs/images/ui-6.png" width="30%" alt="主窗口截图">
</div>
<br>
<div style="display: flex; gap: 10px; justify-content: center;">
  <img src="docs/images/ui-7.png" width="30%" alt="主窗口截图">
  <img src="docs/images/ui-8.png" width="30%" alt="主窗口截图">
  <img src="docs/images/ui-9.png" width="30%" alt="主窗口截图">
</div>

### 操作演示

> 提供脚本安装与多类触发运行方式的动画演示，脚本触发逻辑由脚本作者进行声明配置，并在软件专属界面可视化展示；用户日常操作场景下，几乎无需唤起不忙脚本盒子主程序窗口



<p align="center">
  <img src="docs/images/install-gif.gif" width="50%" alt="安装脚本动画演示">
  <br>
  <em>安装脚本动画演示</em>
</p>

<p align="center">
  <img src="docs/images/content-gif.gif" width="50%" alt="右键执行脚本">
  <br>
  <em>右键执行脚本动画演示</em>
</p>

<p align="center">
  <img src="docs/images/kuaijiejian.gif" width="50%" alt="快捷键执行脚本">
  <br>
  <em>快捷键执行脚本动画演示</em>
</p>

<p align="center">
  <img src="docs/images/chaojifuzhi.gif" width="50%" alt="超级复制执行脚本">
  <br>
  <em>超级复制执行脚本动画演示</em>
</p>

<p align="center">
  <img src="docs/images/dingshi.gif" width="50%" alt="定时任务">
  <br>
  <em>定时任务演示</em>
</p>

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
└── LICENSE                     # AGPL-3.0 许可证
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

本项目基于 **GNU Affero General Public License v3 (AGPL-3.0)** 开源。

### 禁止商用

**本项目仅供个人学习、研究及非商业用途。未经作者明确书面授权，任何个人或组织不得将本软件用于任何商业目的，包括但不限于：**

- 将本软件或修改版本直接用于商业产品销售
- 将本软件打包为商业服务的一部分进行收费
- 利用本软件搭建商业服务平台

如需商业授权，请联系作者：[bmscriptsbox@163.com](mailto:bmscriptsbox@163.com)

### 版权

Copyright © 2026 綦恒智 (Qi Hengzhi)

---


