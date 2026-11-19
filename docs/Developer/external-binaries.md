---
title: 工具托管
description: 脚本依赖 FFmpeg、7-Zip 等命令行工具时，在 TOML 里声明即可：盒子安装时自动下载并把可执行文件路径注入参数文件，也支持直接填 GitHub 下载链接。
status: 稳定
docType: how-to
audience: 脚本开发者
docVersion: 0.3.0
---

# 工具托管

脚本常常要用到外部的命令行工具（FFmpeg、7-Zip、jq……）。你只要在 TOML 里声明一下，盒子在**安装脚本时**自动把它们下载好，并把可执行文件的绝对路径注入参数文件，脚本按路径调用即可，用户不用手动装任何东西。

声明有两种写法：

- **只写工具名**：工具在盒子的资源仓库里，你写个 `name` 就行。
- **自己填 GitHub 链接**：资源仓库里没有的工具，你自己给一个 GitHub 下载地址。

两种都支持多脚本共享——多个脚本依赖同一个工具时只下载一份。

---

## 两种声明方式怎么选

| | 只写工具名（官方清单） | 自己填链接（直连） |
| --- | --- | --- |
| 怎么写 | 只写 `name` | 额外写 `url` |
| 适合 | 资源仓库里已有的常用工具 | 资源仓库里没有的工具 |
| 版本谁维护 | 盒子资源仓库 | 你自己 |
| 默认进 PATH 吗 | 取清单值（多为进） | 否，写 `env_set = true` 才进 |
| 用户要确认吗 | 不用 | 首次要（弹框确认来源） |

---

## 方式一：只写工具名

### 第一步：声明

在 `bm-scripts-box-rc.toml` 的 `[bmscriptsbox.runtime]` 段加 `binaries` 字段：

```toml
[bmscriptsbox.runtime]
binaries = [{ name = "ffmpeg" }, { name = "7zip" }]
```

`binaries` 是数组，每项至少要有 `name`。需要限定版本时加 `version`（比较运算表达式）：

```toml
[bmscriptsbox.runtime]
binaries = [{ name = "ffmpeg", version = ">=6" }]
```

### 第二步：盒子自动安装

安装脚本时，盒子会：查资源仓库清单 → 下载（优先国内镜像，失败切海外）→ 解压 → 记录可执行文件路径（`env_set` 为 `true` 时还会生成命令并加入 PATH）。

### 第三步：脚本里调用

官方清单里多数工具的清单已设 `env_set = true`，脚本里可以直接敲工具名，也可以从参数文件取绝对路径。两种方式见[脚本怎么拿工具路径](#脚本怎么拿工具路径)。

### 资源仓库

工具下载信息托管在 GitHub：

**https://github.com/bm-qihengzhi/BmBinaryResource**

每个工具一个 JSON，文件名与 `name` 对应（如 `ffmpeg.json`）：

```json
{
  "name": "ffmpeg",
  "description": "ffmpeg命令行工具",
  "homepage": "https://ffmpeg.org",
  "version": {
    "8.1": {
      "architecture": {
        "url": "https://github.com/BtbN/FFmpeg-Builds/releases/download/latest/ffmpeg-n8.1-latest-win64-gpl-shared-8.1.zip",
        "url_cn": "https://www.modelscope.cn/datasets/a89913131/BmBinaryResource/resolve/master/ffmpeg-n8.1-latest-win64-gpl-shared-8.1.zip",
        "bin": ["ffmpeg.exe", "ffprobe.exe", "ffplay.exe"],
        "env_set": true,
        "silent_install": false
      }
    }
  }
}
```

| 字段 | 说明 |
| --- | --- |
| `name` | 工具名称，与 TOML 里 `binaries` 的 `name` 对应 |
| `description` | 工具描述 |
| `homepage` | 工具官网地址 |
| `version.<版本>.architecture.url` | 下载地址（海外） |
| `version.<版本>.architecture.url_cn` | 下载地址（国内镜像，优先使用） |
| `version.<版本>.architecture.bin` | 解压后要暴露的可执行文件名（数组） |
| `version.<版本>.architecture.env_set` | 是否生成命令并加入 PATH |
| `version.<版本>.architecture.silent_install` | 是否为安装器、需要静默安装 |

资源仓库里没有你要的工具？Fork 仓库、按上面格式加一个 `<工具名>.json`、提 PR，审核通过后所有盒子用户都能用。

---

## 方式二：自己填 GitHub 链接

你在声明里写上 `url`（**只允许 GitHub 链接**），盒子会下载、校验、解压或安装。默认**不**把工具加进 PATH，而是把可执行文件的绝对路径注入参数文件（见[脚本怎么拿工具路径](#脚本怎么拿工具路径)）；想让它在 PATH 上能用，再加 `env_set = true`。

### 单文件

比如 jq 的 Windows 单文件：

```toml
[bmscriptsbox.runtime]
binaries = [
  { name = "jq",
    url = "https://github.com/jqlang/jq/releases/latest/download/jq-win64.exe",
    extract = false },
]
```

### 归档（解压后暴露里面的可执行文件）

一个归档里有多个 exe 时，用 `bin` 列出要暴露的：

```toml
[bmscriptsbox.runtime]
binaries = [
  { name = "imagemagick",
    url = "https://github.com/owner/repo/releases/latest/download/ImageMagick.zip",
    bin = ["magick.exe", "convert.exe", "identify.exe"] },
]
```

`bin` 决定哪些可执行文件会被暴露出来（默认不进 PATH，但都会注入参数文件供脚本取路径）。

### 固定版本 + 校验指纹

想让版本、内容都锁死时，写死 tag 并附上 `sha256`：

```toml
[bmscriptsbox.runtime]
binaries = [
  { name = "mytool",
    url = "https://github.com/owner/repo/releases/download/v2.1.0/mytool.zip",
    sha256 = "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
    bin = ["mytool.exe"] },
]
```

### exe / msi 安装器

安装包不是归档时，用 `extract = false`，并用 `install` 传静默安装参数（首次会弹框让你确认）：

```toml
[bmscriptsbox.runtime]
binaries = [
  { name = "somerc",
    url = "https://github.com/owner/repo/releases/download/3.25.113.0/setup.exe",
    bin = ["somerc.exe"],
    extract = false,
    install = { command = ["/VERYSILENT", "/SUPPRESSMSGBOXES", "/NORESTART"] } },
]
```

### GitHub 链接怎么写

| 情况 | 写法 |
| --- | --- |
| 资产名不含版本号，且有正式版 | `https://github.com/owner/repo/releases/latest/download/<资产名>` |
| 资产名不含版本号，但只有滚动 tag（如 `latest`） | `https://github.com/owner/repo/releases/download/latest/<资产名>` |
| 资产名里带版本号（每版都变） | `https://github.com/owner/repo/releases/download/<具体tag>/<资产名>` |

推荐第一种：链接固定，永远指向最新正式版，你零维护。盒子会自动跟随跳转、解出真实版本号。

两个前提要注意：

- **资产名不能带版本号**。像 `jq-win64.exe` 这种跨版本不变的名字才能用 `latest`；`DittoPortable_3_25_113_0.zip` 这种每版都变的，只能用第三种、手动钉版本。
- **最新发布必须是正式版**。`/releases/latest` 会跳过预发布（prerelease）和草稿；如果仓库最新发布是 prerelease，只能用第二种字面 tag 写法。

---

## 字段说明

| 字段 | 类型 | 默认 | 说明 |
| --- | --- | --- | --- |
| `name` | 字符串 | 必填 | 工具名 / 命令名 |
| `version` | 字符串 | 空 | 官方模式：版本约束，如 `">=6"` |
| `url` | 字符串 | 无 | 直连模式：GitHub 下载链接（写了它就走直连） |
| `sha256` | 字符串 | 无 | 直连可选：64 位十六进制；写了就严格校验 |
| `bin` | 字符串数组 | 空 | 解压后要暴露的可执行文件名 |
| `extract` | 布尔 | `true` | `true` 解压归档；`false` 当单文件 / 安装器 |
| `install` | 表 | 无 | exe/msi 的静默安装参数 |
| `env_set` | 布尔 | 直连 `false`；官方取清单值 | 是否生成命令并加入 PATH |

---

## 脚本怎么拿工具路径

不管哪种模式，盒子都会把脚本声明过的工具的可执行文件**绝对路径**注入参数文件的 `environment.binaries`，结构是 `{ 声明名: { 命令名: 绝对路径 } }`：

```json
{
  "environment": {
    "binaries": {
      "imagemagick": {
        "magick": "D:/…/BmPackages/downloads/imagemagick/…/magick.exe",
        "convert": "D:/…/BmPackages/downloads/imagemagick/…/convert.exe"
      },
      "jq": { "jq-win64": "D:/…/jq-win64.exe" }
    }
  }
}
```

脚本按下标取路径直接调用：

```python
import json
import sys
import subprocess

payload = json.load(open(sys.argv[1], encoding='utf-8'))
bins = payload["environment"]["binaries"]

magick = bins["imagemagick"]["magick"]      # 绝对路径
subprocess.run([magick, "-version"])
```

- 外层键 = 你声明的 `name`；内层键 = 可执行文件名（去掉 `.exe`）。
- 官方模式若资源清单里有多个 `bin`，也会全部注入。
- 只读取本脚本声明过的工具；未声明的不出现。

---

## 命令名与 PATH

`env_set = true` 时，盒子会为每个可执行文件生成一个命令（Windows 下是一层重定向），并把它所在目录前置进脚本运行进程的 PATH：

- **单文件**：命令名用你写的 `name`。
- **多文件**：每个 exe 各生成一个命令，命令名取真实的文件名（不含 `.exe`）。

两种模式的 PATH 行为由同一个 `env_set` 控制——官方模式的默认值来自资源清单，直连模式默认 `false`（不进 PATH，走上面的参数注入）。

PATH 只在脚本运行时生效，**不改系统环境变量**，也不会污染系统。

---

## 来源与安全

- **只允许 GitHub**：直连的 `url` 必须是 `github.com` 或其资源域名（`*.githubusercontent.com`），其他域名会被拒绝。
- **核心命令名保护**：直连模式下不允许用 `python`、`node`、`uv`、`pwsh`、`git` 等核心命令名，防止被顶替。
- **首次要确认**：脚本第一次用某个直连工具时，安装会弹框显示来源、版本和指纹。拒绝 → 安装失败并回滚；同意 → 继续。
- **完整性校验**：
  - 你写了 `sha256` → 严格比对，不一致就不装。
  - 没写 → 盒子首次下载时记录指纹；以后同一个版本号内容变了会被拦下。滚动版本（如 `latest`）会随上游更新自动放行。
- **信任记忆**：弹框里选“允许并记住”后，同一脚本、同一来源不再询问。信任记录存在 `BmData/BmBinaryTrust.json`，想取消就手动删掉里面的对应条目。

---

## 存储位置

```plaintext
BmScriptsBox/
  ├─ BmPackages/
  │   ├─ downloads/          # 下载并解压的归档
  │   ├─ cli/<工具>/<版本>/   # 安装器类工具的安装目录
  │   └─ bin/                # 命令重定向：<命令名>.exe + <命令名>.target
  └─ BmData/
      ├─ BmPackage.json       # 已装工具清单
      ├─ BmBinaryHashes.json  # 直连工具的指纹记录
      └─ BmBinaryTrust.json   # “记住此来源”的信任记录
```

---

## 常见问题

**Q：直连能用非 GitHub 的链接吗？**
A：不能。直连只允许 `github.com` 及其资源域名。

**Q：用 `latest` 链接为什么下不到文件？**
A：多半是资产名里带了版本号（每版都变），或者最新发布是预发布版。对照[“GitHub 链接怎么写”](#github-链接怎么写)换一种写法。

**Q：为什么安装时弹了个确认框？**
A：这是直连工具首次下载的来源确认。不想每次都点，可以选“允许并记住”。

**Q：直连工具默认不进 PATH，脚本怎么调用？**
A：从参数文件 `environment.binaries` 里取绝对路径来调用，见[脚本怎么拿工具路径](#脚本怎么拿工具路径)。想让它能按命令名调用，就写 `env_set = true`。

**Q：工具会装进系统、污染系统 PATH 吗？**
A：不会。工具放在盒子管理目录，PATH 只在脚本运行时生效。

**Q：多个脚本用同一个工具会重复下载吗？**
A：不会。盒子按 `name` 共享同一份。

---

## 相关文档

- 各语言环境细节 → [环境配置](./environment-config)
- 需要 AI 模型 → [模型管理](./model-download)
