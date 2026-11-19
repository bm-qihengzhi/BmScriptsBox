---
title: 脚本目录结构规范
description: 脚本目录的标准结构与命名规范：入口文件与语言的对应表、配置路径规则、打包时的层级要求。
status: 稳定
docType: reference
audience: 脚本开发者
docVersion: 0.3.0
---

# 脚本目录结构规范

> **盒子按约定识别你的脚本：入口在哪、配置在哪、图标在哪。结构对了，装进去就能跑。**

盒子通过约定的目录结构识别脚本。结构不对，安装会直接失败。

---

## 标准目录结构

```plaintext
your-script-name/
├── bm-scripts-box-rc.toml      # 必须 — 盒子配置文件
├── main.py                     # 入口文件（扩展名取决于语言）
├── pyproject.toml              # Python 脚本必须（声明依赖）
├── package.json                # Node.js 脚本必须（声明依赖）
├── icon/
│   └── logo.png                # 可选 — 脚本图标
└── ...其他资源文件
```

`bm-scripts-box-rc.toml` 建议放在**脚本根目录**。盒子也支持在子目录中递归查找，但放根目录更可靠。

---

## 命名规范

| 项目 | 规范 | 示例 |
| --- | --- | --- |
| 目录名 | 英文小写 + 连字符 | `file-classifier`、`image-compress` |
| 脚本 ID | UUID v4，全局唯一 | `a1b2c3d4-e5f6-7890-abcd-ef1234567890` |
| 版本号 | 语义化版本 `x.y.z` | `1.0.0`、`2.3.1` |
| 图标格式 | PNG、SVG 或 ICO | `icon/logo.png` |
| 图标尺寸 | 建议 256×256（最大 256×256） | — |

---

## 入口文件与语言对应

入口文件的扩展名必须与配置文件中 `runtime.language` 的值匹配，否则安装时校验失败：

| 配置语言标识 | 入口文件扩展名 | 典型入口名 | 需要依赖文件 |
| --- | --- | --- | --- |
| `python` | `.py` | `main.py` | `pyproject.toml` |
| `node.js` | `.js` | `main.js` | `package.json` |
| `powershell` | `.ps1` | `main.ps1` | 无需 |
| `bat` | `.bat` | `main.bat` | 无需 |
| `autohotkey` | `.ahk` | `main.ahk` | 无需 |
| `html` | `.html` | `index.html` | 无需 |
| `exe` | `.exe` | `tool.exe` | 无需 |

入口文件名**不强制**叫 `main.*`，你可以任意命名，只要在配置文件的 `entry` 字段中写对即可。各语言的环境细节见 [环境配置](./environment-config)。

---

## 配置文件中的路径规则

`bm-scripts-box-rc.toml` 中所有涉及文件的字段（`entry`、`icon` 等）都用**相对路径**，相对于脚本根目录。

```toml
# 正确 — 相对路径
entry = "src/main.py"
icon = "icon/logo.png"

# 错误 — 绝对路径，Pydantic 校验会直接拒绝
# entry = "D:/main.py"
# icon = "C:/icon.png"
```

安装时盒子自动把相对路径解析为系统绝对路径，你不需要在路径上做任何额外处理。

---

## 打包时的目录层级

这是最容易踩的坑：**ZIP 包的根目录要直接包含配置文件，不要多套一层文件夹。**

```plaintext
# 正确
hello-box.zip
├── bm-scripts-box-rc.toml
├── main.py
└── pyproject.toml

# 也能装，但不推荐（盒子需要递归查找才能找到配置）
hello-box.zip
└── hello-box/
    ├── bm-scripts-box-rc.toml
    ├── main.py
    └── pyproject.toml
```

两种结构盒子都能识别，但第一种更快也更不容易出错。详见 [打包与分发](./packaging-distribution)。

---

## 常见问题

**Q：必须叫 `main.py` 吗？**
A：不必。只要 `entry` 字段写对相对路径即可。

**Q：图标放哪？**
A：放脚本目录下，`info.icon` 填相对路径，如 `icon/logo.png`。

**Q：依赖文件必须吗？**
A：Python 必须 `pyproject.toml`，Node.js 必须 `package.json`；其余语言无需。

---

## 相关文档

- 配置文件所有字段 → [配置文件详解](./declarative-access)
- 各语言环境细节 → [环境配置](./environment-config)
- 打包注意事项 → [打包与分发](./packaging-distribution)