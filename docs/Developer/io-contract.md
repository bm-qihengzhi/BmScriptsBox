---
title: 输入输出契约
description: 不忙脚本盒子脚本输入输出契约——inputs 定义（name/type/exts/description）、outputs 输出键声明、联动回传信封格式与错误码
status: 稳定
docType: reference
audience: 脚本开发者
docVersion: 0.3.0
---

# 输入输出契约

通过声明`inputs` 和`outputs` ，即脚本能够接收哪些数据，以及执行后可以返回哪些结果，盒子依据这份声明，自动从触发场景中提取所需数据，构造参数并传递给脚本；当脚本作为节点被调用时，也需按契约中声明的输出键，将结果回传给盒子，由盒子按约定返回给调用方。

开发者只需在 TOML 文件中完成声明，盒子便会全程负责数据的自动提取、注入与回传，无需额外编码。

--- 

先分清两者的分工：

| 段 | 方向 | 作用 | 什么时候需要 |
| --- | --- | --- | --- |
| `[[bmscriptsbox.inputs]]` | 进 | 声明脚本接收的业务数据（如选中的文件路径） | 脚本需要外部输入时 |
| `[[bmscriptsbox.outputs]]` | 出 | 声明脚本能返回的业务键 | **作为联动节点时必须声明**（≥1 条） |

---

## 输入定义

在 `bm-scripts-box-rc.toml` 中用 `[[bmscriptsbox.inputs]]` 声明脚本接收什么参数：

```toml
[[bmscriptsbox.inputs]]
name = "source_path"
type = "list"
exts = [".txt", ".csv"]
pick = "files"        # 可选：本输入在自动生成的运行界面里用「文件/文件夹选择器」选本地路径
description = "要处理的源文件"
```

| 字段 | 必填 | 说明 | 可选值 |
| --- | --- | --- | --- |
| `name` | 是 | 参数名称，作为 JSON `data` 段的键名。脚本中通过 `params['data'][name]` 取值 | 自定义字符串 |
| `label` | 否 | 输入**显示名**（自动生成运行界面上的标签）；留空则回退显示 `name` | 自定义字符串 |
| `type` | 是 | 参数数据类型（仅 `list` / `str`，见下文） | `"list"` / `"str"` |
| `exts` | 否 | 扩展名白名单过滤 | `[".txt", ".md"]` |
| `pick` | 否 | **本地路径选择器**：声明后，[自动生成运行界面](./auto-generated-ui)里可本地选取文件路径，按 `exts` 过滤）。不写 = 纯文本多行，可填任意 list | `"files"` / `"folders"` / `"both"` |
| `description` | 否（建议） | 参数说明（供开发者参考，**不在自动生成界面显示**） | 自定义字符串 |

### type 数据类型

`inputs` 与 `outputs` 共用同一套类型，只有两种：

| 值 | 说明 | JSON 中的值类型 | 示例 |
| --- | --- | --- | --- |
| `"list"` | 文件路径、多条文本 | 字符串数组 | `["C:/a.txt", "C:/b.txt"]` |
| `"str"` | 单条文本 | 单元素数组 | `["Hello World"]`（`data` 段恒为数组） |

::: warning 注意事项：
一：inputs / outputs 只支持 str 与 list

二：最多只能声明 1 条 `inputs`（主数据）。需要传多个文件或多个参数时，改用 `params` 的 `str` 类型声明路径参数。声明多条会在安装时校验报错。

:::


### 如果不需要输入

脚本可以不接收外部参数，省略 `inputs` 段即可，盒子会跳过参数构造，直接启动脚本：

```toml
[bmscriptsbox]
# ...其他配置...
# 不写 [[bmscriptsbox.inputs]]
```

---

## 输出定义

`[[bmscriptsbox.outputs]]` 声明脚本能返回的业务键。它有两个用途：

1. **节点校验**：脚本声明 `[bmscriptsbox.node]` 时，盒子要求它至少有 1 个 `outputs`（节点必须具备返回能力，见 [脚本节点](./node)）
2. **取值约定**：联动调用方按这些键名取结果

```toml
[[bmscriptsbox.outputs]]
name = "result"
type = "str"
description = "处理后的结果文件路径"
```

| 字段 | 必填 | 说明 |
| --- | --- | --- |
| `name` | 是 | 输出业务键名称，调用方按此键从信封里取值 |
| `type` | 是 | 输出数据类型，仅 `str` / `list`（见上文警告框） |
| `description` | 否（强烈建议） | 这个键返回的是什么，给调用方开发者看 |

::: tip 一定要写 description
`description` 是**给别的脚本作者看的说明**。帮助调用方开发者理解脚本返回数据

```toml
[[bmscriptsbox.outputs]]
name = "subtitle_path"
type = "str"
description = "提取出的字幕文件绝对路径（.srt）"

[[bmscriptsbox.outputs]]
name = "duration"
type = "str"
description = "视频时长（秒，整数字符串，如 \"125\"）"
```


:::

**声明多个输出：**

```toml
[[bmscriptsbox.outputs]]
name = "report"
type = "str"
description = "生成的报告文件路径（.md）"

[[bmscriptsbox.outputs]]
name = "summary"
type = "str"
description = "报告摘要文本，不超过 200 字"
```

---

## 脚本输出数据的方式

按上文的三段契约，盒子执行脚本时，会将输入数据以 JSON 文件的形式传入（路径为脚本的第一个命令行参数）。脚本需读取该文件获取输入；同时，可通过 environment.output_json 字段获取输出文件的路径。脚本执行完毕后，必须将返回数据按固定信封格式写入该输出 JSON 文件中，供盒子读取回传。



**信封格式**固定如下： 
```json
{
  "code": 0,
  "msg": "ok",
  // ... 业务键（由 outputs 声明）
}

```

- `code` / `msg` 是**保留字段**，不属于 `outputs` 声明
- `code = 0` 表示业务成功，非 0 表示业务失败（`msg` 说明原因）
- 错误码：
    * `-1` 启动失败、
    * `-2` 执行超时、
    * `-3` 格式错误（缺 `code` / `msg`，或 `code` 非 int）
- 业务键在信封顶层平铺，不与 `code` / `msg` 嵌套


**示例(Python)**
```python
import json, sys

payload = json.load(open(sys.argv[1], encoding='utf-8'))
env = payload["environment"]

with open(env["output_json"], 'w', encoding='utf-8') as f:
    json.dump(
        {"code": 0, "msg": "ok", "result": "C:/out.txt"}, 
        f, 
        ensure_ascii=False, 
        indent=2
        )
```


## 常见问题

**Q：`inputs` 能用 `int` / `bool` 类型吗？**
A：不能。`inputs` / `outputs` 只支持 `str` / `list`；`int` / `float` / `bool` / `dict` 是 `params` 专属。

**Q：声明多个 inputs 会怎样？**
A：安装时校验报错。需要多个文件用 `params` 的 `str` 类型声明路径参数。

**Q：返回值的实际类型会被校验吗？**
A：不会。盒子只校验 `code` 是整数、`msg` 是字符串；返回键是否匹配 `outputs` 由你自查。

---

## 相关文档

- 数据怎么传进脚本 → [参数注入](./parameter-passing)
- 节点概念与误区 → [节点](./node)
- 联动调用完整机制 → [脚本联动](./script-linking)