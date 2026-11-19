---
title: 执行脚本 · /api/execute
description: POST /api/execute 触发任意脚本执行——结构化调用与 temp_file 旧触发流，支持同步返回结果与异步触发
status: 稳定
docType: reference
audience: 脚本开发者
docVersion: 0.3.0
---

# POST /api/execute

> **按脚本 ID 触发任意脚本运行：同步拿结果，或异步触发——给外部程序、定时任务、脚本自调用。**

通过脚本 ID 触发指定脚本运行。支持两种调用方式：**结构化调用**和 **temp_file 旧触发流**（兼容保留）。

与 [/api/link](./link) 的区别：`/api/execute` 可以触发**任意**脚本（不要求是节点），并且可以选择异步；`/api/link` 只放行节点，且恒为同步。

---

## 请求参数

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `script_id` | 字符串 | 是 | 脚本 UUID，对应配置文件中 `info.id` |
| `sync` | 布尔值 | 否 | `true` = 同步执行并返回结果；缺省 = 异步（fire-and-forget） |
| `data` | 对象 | 否 | 主数据，键名取被调脚本 `inputs[0].name`，值为路径数组 |
| `params` | 对象 | 否 | 运行参数覆盖，未传的用被调脚本 TOML 默认值 |
| `temp_file` | 字符串 | 旧流 | 参数 JSON 文件的**绝对路径**（旧触发方式） |

---

## 示例一：结构化调用（同步，拿结果）

```bash
curl -X POST http://127.0.0.1:9527/api/execute \
  -H "Content-Type: application/json" \
  -d '{"script_id": "your-script-uuid", "sync": true,
       "data": {"video_paths": ["C:/videos/a.mp4"]},
       "params": {"language": "zh"}}'
```

同步响应：

```json
{
    "status": "success",
    "message": "ok",
    "exit_code": 0,
    "success": true,
    "timed_out": false,
    "stdout": "",
    "stderr": "",
    "result": {
        "code": 0,
        "msg": "ok",
        "subtitle_path": "C:/tmp/a.srt"
    }
}
```

响应字段说明：

| 字段 | 说明 |
| --- | --- |
| `success` | 进程成功（exit 0 且未超时）**且** `result.code == 0` |
| `exit_code` | 进程退出码 |
| `timed_out` | 是否执行超时 |
| `stdout` / `stderr` | 捕获到的标准输出 / 错误输出 |
| `result` | 脚本写进 `environment.output_json` 的信封。进程失败时盒子会合成错误信封（`code` 为 -1 / -2 / -3） |

> 只有在 `sync: true` 时才会返回 `result`。异步调用不返回执行结果。

---

## 示例二：异步触发（fire-and-forget）

不传 `sync` 即可，盒子立刻返回，脚本在后台跑：

```bash
curl -X POST http://127.0.0.1:9527/api/execute \
  -H "Content-Type: application/json" \
  -d '{"script_id": "your-script-uuid",
       "data": {"target_paths": ["C:/a.txt"]}}'
```

适合耗时长、不需要立刻拿结果的场景。

---

## 示例三：temp_file 旧触发流

直接传入一个参数 JSON 文件的绝对路径（兼容旧版调用方式）：

```bash
curl -X POST http://127.0.0.1:9527/api/execute \
  -H "Content-Type: application/json" \
  -d '{"script_id": "your-script-uuid", "temp_file": "C:/path/to/params.json"}'
```

也支持 `application/x-www-form-urlencoded` 格式：

```bash
curl -X POST http://127.0.0.1:9527/api/execute \
  -d "script_id=your-script-uuid" \
  -d "temp_file=C:/path/to/params.json"
```

---

## 错误响应

```json
// 缺少参数
{"status": "error", "message": "缺少script_id参数"}

// 文件不存在
{"status": "error", "message": "文件不存在: C:/xxx.json"}

// 脚本未找到
{"status": "error", "message": "脚本不存在: your-script-uuid"}
```

---

## 相关文档

- 脚本串联专用接口 → [脚本联动 · /api/link](./link)
- 信封契约与错误码 → [脚本联动](../script-linking)