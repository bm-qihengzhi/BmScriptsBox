---
title: 工作流
description: 不忙盒子工作流说明——多脚本串联现通过「脚本联动」实现（代码里调 /api/link），声明式编排为未来计划
status: 未实现
docType: explanation
audience: 脚本开发者
docVersion: 0.3.0
---

# 工作流

> **多脚本串联（A 的输出喂给 B）现在就能用——通过「脚本联动」实现，声明式编排引擎是未来计划。**

::: danger 🚧 未实现
`[bmscriptsbox.workflow]` 是**预留配置**，当前版本**无运行时效果**。

未来计划支持在 TOML 里声明式编排（`workflow.steps`：B→C 顺序 + 参数映射），盒子自动按图执行，无需写联动代码。现在请不要依赖它。
:::

---

## 现在怎么串联脚本

**多脚本串联（A 的输出喂给 B）现在就能用，通过「脚本联动」实现**。A 在代码里同步调用 B，把 B 的结果拿回来继续处理，不需要等任何新功能。

做法三步：

1. 被调脚本声明为[节点](./node)（`[bmscriptsbox.node]` + ≥1 个 `outputs`）
2. A 在 TOML 里[声明依赖](./script-linking)（`[[bmscriptsbox.dependencies]]`），安装时自动带齐 B
3. A 用 `environment.api_base` 调 `/api/link`，拿回 B 写的信封结果

完整教程见 [脚本联动](./script-linking)。

---

## `[bmscriptsbox.workflow]` 预留配置

| 字段 | 类型 | 必填 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| `workflow_enabled` | 布尔值 | 否 | `true` | 是否允许作为工作流节点（预留） |

---

## 对开发者的影响

现在想串联脚本，直接用[脚本联动](./script-linking)即可，不需要声明 `workflow`。`workflow` 段可以先省略，等声明式引擎发布后再启用。

---

## 相关文档

- 现在就用的方案 → [脚本联动](./script-linking)
- 被调方声明 → [节点](./node)