---
title: 终端模式详解
description: runtime.terminal 四种模式（静默 / 弹窗 / 智能 / 反转）的行为差异、输出捕获编码策略与各语言推荐设置。
status: 稳定
docType: reference
audience: 脚本开发者
docVersion: 0.3.0
---

# 终端模式详解


`runtime.terminal` 决定脚本运行时**终端窗口表现**，建议始终显示的填写`terminal`，不要依赖默认值

---

## 四种模式速览

| 值 | 有输入数据时 | 无输入数据时 | 典型场景 |
| --- | --- | --- | --- |
| `"never"` | 无终端 | 无终端 | 无需交互的CLI脚本 |
| `"always"` | 有终端 | 有终端 | TUI交互脚本 |
| `"auto"` | 无终端 | 有终端 | 既支持自动化调用，又支持手动交互 |
| `"inverse"` | 有终端） | 无终端 | 调用时看进度，手动运行时走 GUI |




::: tip
**判断依据** 是 `json` 参数文件中 `data` 是否为空，而不是脚本是否声明了 `inputs`

开发者可根据此特性、结合脚本实际情况选择适合的终端模式





:::




---

## 常见问题

**Q：调试时看不到输出？**
A：大概率是 `terminal` 设成了 `"never"`。调试期间改成 `"always"`，确认没问题后再改回去。

**Q：脚本一闪而过，来不及看输出？**
A：① 把 `terminal` 设为 `"always"`，窗口会保留 ② 在脚本末尾加 `input("按回车键退出...")`。

**Q：GUI 脚本（tkinter 等）窗口被隐藏？**
A：GUI 脚本请把 `terminal` 设为 `"always"`，避免窗口被隐藏。

---

## 相关文档

- 后台静默通知用户结果 → [发送通知 · /api/notify](./http-api/notify)
- 定时任务静默运行 → [定时任务](./scheduled-task)
- 数据怎么传进脚本 → [参数注入](./parameter-passing)