---
title: 超级复制触发
description: 脚本如何响应快速双击 Ctrl+C——quick_copy 配置、ClipboardMonitor 工作流程与适合的脚本类型
status: 稳定
docType: how-to
audience: 脚本开发者
docVersion: 0.3.0
---

# 超级复制触发

该触发机制通过 TOML 配置项 [bmscriptsbox.triggers.quick_copy] 启用。启用后，用户在任意应用内快速双击 Ctrl+C 时，盒子会立即获取当前剪贴板内容，并将其作为参数传递给关联脚本，实现快捷调用。


---

## 配置方式

```toml
[bmscriptsbox.triggers.quick_copy]
enabled = true
```

只有启用和禁用两个状态，没有额外参数。

## 工作流程

```plaintext
用户在任意应用中快速双击 Ctrl+C
  → 盒子的 ClipboardMonitor 检测到该操作
  → 自动读取当前剪贴板内容
  → 将剪贴板文本作为 data 参数传给脚本
```

## 适合这样的脚本

- **翻译工具**：复制文本 → 自动翻译 → 弹出结果
- **格式化工具**：复制代码 → 自动格式化 → 替换剪贴板
- **短链接生成**：复制长链接 → 生成短链接 → 复制结果
- **词典查询**：复制单词 → 查询释义 → 弹出解释

---

## 相关文档

- 触发后参数怎么传 → [参数注入](./parameter-passing)
- 右键菜单触发 → [右键菜单触发](./context-menu)
- 快捷键触发 → [快捷键触发](./hotkey)