---
title: 联动调用 · /api/link
description: POST /api/link 脚本串联——A 调 B（节点），恒为同步拿回结果，含节点门禁与错误响应
status: 稳定
docType: reference
audience: 脚本开发者
docVersion: 0.3.0
---

# POST /api/link

> **脚本 A 在运行中调用脚本 B（节点），恒为同步——等 B 跑完、拿回它的信封结果。**

脚本 A 在运行中调用脚本 B 时使用。**恒为同步**：发起后一直等到 B 跑完并拿到它的信封结果，没有 `sync` 参数，也没有异步模式。

联动完整机制见 [脚本联动](../script-linking)。

与 [/api/execute](./execute) 的区别：`/api/link` **只放行声明为节点的脚本**，专为脚本串联设计；`/api/execute` 可触发任意脚本且支持异步。

---

## 请求参数

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `script_id` | 字符串 | 是 | 被调脚本 B 的 UUID |
| `data` | 对象 | 否 | B 的主数据，键名取 B 的 `inputs[0].name` |
| `params` | 对象 | 否 | B 的运行参数覆盖，未传的用 B 的 TOML 默认值 |

::: warning 节点门禁
`/api/link` 只放行**已声明为节点**（`[bmscriptsbox.node] enabled = true`）的脚本，否则返回 403「未声明可作为节点」。

没声明 `node` 的脚本没有约定的返回能力，调用它没有意义。节点概念见 [节点](../node)。
:::

---

## 请求示例

```bash
curl -X POST http://127.0.0.1:9527/api/link \
  -H "Content-Type: application/json" \
  -d '{"script_id": "your-node-script-uuid",
       "data": {"video_paths": ["C:/videos/a.mp4"]},
       "params": {"language": "zh"}}'
```

响应结构与 [/api/execute](./execute) 的同步响应相同（`status` / `message` / `exit_code` / `success` / `timed_out` / `stdout` / `stderr` / `result`），其中 `result` 为 B 写回的信封。

---

## 错误响应

```json
// 缺少参数
{"status": "error", "message": "缺少script_id参数"}

// 脚本未找到
{"status": "error", "message": "脚本不存在: xxx"}

// 目标未声明为节点（403）
{"status": "error", "message": "脚本 '字幕提取' 未声明可作为节点，不允许联动调用"}

// 联动链路过深，超过 8 层（400）
{"status": "error", "message": "联动链路过深（超过 8 层），已拦截"}
```

更多错误排查见 [脚本联动](../script-linking) 的错误排查表。

---

## 相关文档

- 联动完整机制 → [脚本联动](../script-linking)
- 被调方怎么声明 → [节点](../node)