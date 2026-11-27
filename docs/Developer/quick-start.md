---
title: Python 脚本开发入门 - 5 分钟写出第一个脚本
description: 不忙盒子脚本开发快速上手——从零创建 Python 脚本、编写配置、安装到盒子并运行，跑通第一个脚本
status: 稳定
docType: tutorial
audience: 脚本开发者
docVersion: 0.3.0
---

# 5 分钟快速上手


通过一个简单的Python脚本案例、快速了解接入机制


---

## 三步上手

### 第一步：创建项目

创建一个项目文件夹，用 **uv** 初始化：

```bash
mkdir hello-box
cd hello-box
uv init
```

目录结构：

```plaintext
hello-box/
├── pyproject.toml
└── main.py
```

没有装 uv 也没关系，手动创建这两个文件效果一样。

### 第二步：编写配置文件

在项目根目录创建 `bm-scripts-box-rc.toml`（文件名固定，不能改）：

```toml
[bmscriptsbox]

[bmscriptsbox.info]
id = "e1b2c3d4-5678-90ab-cdef-1234567890ab"   # 生成一个唯一 UUID
name = "Hello 盒子"
desc = "一个简单的演示脚本"
version = "1.0.0"                             # 语义化版本号

[bmscriptsbox.runtime]
language = "python"                           # 脚本语言
language_version = ">=3.8"                    # 语言版本要求
entry = "main.py"                             # 入口文件（相对于脚本根目录）
terminal = "always"                           # 终端模式（建议始终显式填写）
```


### 第三步：编写入口文件

创建 `main.py`：

```python
import sys
import json
import time

def main():
    print('脚本启动成功')
    time.sleep(2)
    print('脚本执行完毕')

    input("按回车键退出...")

if __name__ == '__main__':
    main()
```

### 第四步：编写pyproject.toml
>这个文件用于声明 Python 脚本所依赖的第三方包。如果您使用 uv，执行 uv init 会自动生成它；如果不使用 uv，也可以手动在项目根目录下创建此文件。其他语言的脚本可跳过此步。

**如果需要额外的依赖**，在 `pyproject.toml` 中声明：

```toml
[project]
name = "hello-box"
version = "1.0.0"
requires-python = ">=3.8"
dependencies = []    # 示例：["pillow>=10.0", "send2trash>=1.8"]
```

盒子安装时自动读取 `pyproject.toml`，创建虚拟环境并用 `uv sync` 安装依赖。如果 `dependencies` 为空，则跳过虚拟环境创建，直接运行。

---

## 第五步：安装到盒子

把项目目录打包为 `.zip` 文件。注意：**压缩包的根目录要直接包含所有文件**，不要把 `hello-box` 文件夹本身打包进去。

```plaintext
hello-box.zip
├── bm-scripts-box-rc.toml
├── pyproject.toml
└── main.py
```

然后在盒子中安装：

1. 进入「脚本管理」页面
2. 点击 **安装脚本**，选择 `hello-box.zip`
3. 盒子自动完成这些工作：
   - 校验 `bm-scripts-box-rc.toml` 配置
   - 下载对应版本的 Python（便携版，用户无需预装）
   - 创建虚拟环境并安装依赖
   - 写入数据库
   - 安装完成 ✅

---

## 运行并验证

安装成功后，在「脚本管理」页面找到「Hello 盒子」，点击 **运行**。你会看到一个终端窗口）。
> 刚才的示例只是冰山一角。盒子还能实现数据注入、参数传递、自动生成 GUI 等众多能力，且统统通过配置文件搞定，无需额外编码。想深入了解？欢迎移步其他文档继续探索！

---

## 常见问题

**Q：没有装 uv 怎么办？**
A：手动创建 `pyproject.toml` 和 `main.py` 即可，效果一样。

**Q：为什么运行后看不到窗口？**
A：`terminal` 设成了 `"never"` 会把输出丢弃。调试期间用 `"always"`，确认无误再改。

**Q：安装时报配置错误？**
A：对照 [配置文件详解](./declarative-access) 的「配置校验错误对照表」逐项检查。

---

## 相关文档

- [脚本运行机制](./run-mechanism) — 搞懂盒子和脚本之间到底发生了什么
- [配置文件详解](./declarative-access) — 深入了解每个配置项
- [右键菜单触发](./context-menu)、[快捷键触发](./hotkey) — 让脚本通过右键、快捷键等方式触发
- [完整示例](./examples) — 看 6 个真实脚本怎么写