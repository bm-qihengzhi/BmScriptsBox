---
title: TOML 脚本配置参考 - 参数、图标与运行环境
description: 不忙脚本盒子运行参数——[[bmscriptsbox.params]] 声明方式、字段参考、类型系统、各触发场景下的取值规则。
status: 稳定
docType: reference
audience: 脚本开发者
docVersion: 0.3.0
---

# 运行参数

`params` 是脚本的可调运行选项，用于声明除`inputs`数据以外、额外需要的参数、例如输出语言、压缩质量、保存路径。脚本用 JSON 参数文件里的 `params` 段读取，用户在定时任务表单或自动生成界面里配置，调用方在联动时按声明结构传入。

---

## 什么时候需要 params

| 场景 | 谁在用它 |
| --- | --- |
| **定时任务** | 盒子把声明的 `params` 映射到 UI 上，供用户配置，实现灵活的定时执行 |
| **脚本联动** | 调用方按声明的 `params` 结构自行构造参数来启动脚本 |
| **自动生成运行界面** | 盒子把 `params` 转成表单控件，用户填好点「执行」后启动脚本 |


---

## 声明方式

在 `bm-scripts-box-rc.toml` 中用 `[[bmscriptsbox.params]]` 声明，可声明多条：

```toml
[[bmscriptsbox.params]]
name = "language"                  # 参数名（唯一，不能重复；也是 JSON params 的键名）
label = "字幕语言"                  # 表单显示名（选填；留空回退 name）
type = "str"                       # str | int | float | bool | list | dict
default = "auto"                   # 默认值（选填）
required = false                   # 是否必填（选填）
choices = ["auto", "zh", "en"]     # 可选值列表（仅 str 类型有效）
choice_labels = { auto = "自动", zh = "中文", en = "英文" }   # 取值→显示名（仅界面显示，传参仍用取值）
description = "选择字幕识别/生成的语言"   # 参数说明（供开发者参考，不在界面显示，选填）
secret = false                     # 是否敏感参数（选填）
```

---

## 字段参考

| 字段 | 类型 | 必填 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| `name` | 字符串 | 是 | — | 参数名，作为 JSON `params` 段的键名，**不能重复** |
| `label` | 字符串 | 否 | `""` | 参数**显示名**（表单上显示的标签）；留空则回退显示 `name` |
| `type` | 字符串 | 是 | `"str"` | JSON 数据类型之一：`str` / `int` / `float` / `bool` / `list` / `dict` |
| `default` | 任意 | 否 | `null` | 默认值（按 `type` 强转） |
| `required` | 布尔值 | 否 | `false` | 是否必填；联动调用时缺省会报错 |
| `choices` | 字符串列表 | 否 | `[]` | 可选值白名单，**仅对 `str` 类型有效**（其他类型声明会校验报错） |
| `choice_labels` | 对象 | 否 | — | `choices` 取值 → 显示名映射（如 `{ smart = "智能", second = "按秒" }`）。**仅影响界面显示**：下拉里显示中文，回传脚本的仍是取值（英文 key）。未配的取值回退显示原值；键必须在 `choices` 内，否则校验报错 |
| `description` | 字符串 | 否 | `""` | 参数说明（供开发者/调用方参考，**不在自动生成界面显示**；界面标签用 `label`） |
| `secret` | 布尔值 | 否 | `false` | 是否敏感参数 |
| `when` | 对象 | 否 | — | **联动显隐**：`{field = "另一参数名", eq = <值>}` 或 `{field = "…", in = [..]}`。仅当被依赖参数取值匹配时，本参数才在自动生成的界面上显示（隐藏的参数不注入脚本） |

> **`when` 联动示例**：`mode` 取 `advanced` 时，`batch_size` 才显示：
>
> ```toml
> [[bmscriptsbox.params]]
> name = "mode"
> type = "str"
> default = "simple"
> choices = ["simple", "advanced"]
>
> [[bmscriptsbox.params]]
> name = "batch_size"
> type = "int"
> default = 8
> when = { field = "mode", eq = "advanced" }   # 仅 mode == "advanced" 时显示/收集
> ```
> 用 `in = [...]` 可匹配多个取值：`when = { field = "mode", in = ["advanced", "pro"] }`。
> **揭示型**：省略 `eq`/`in`，仅随被依赖字段的显隐而显隐（父亮我亮、父藏我藏），多兄弟字段跟随同一个开关时不用各写一遍 eq：
> ```toml
> [[bmscriptsbox.params]]
> name = "extra_a"
> type = "str"
> when = { field = "mode", eq = "advanced" }
>
> [[bmscriptsbox.params]]
> name = "extra_b"
> type = "str"
> when = { field = "extra_a" }      # extra_a 可见（即 mode=advanced）则可见
> ```
> 该能力仅在**自动生成的参数界面**（`[bmscriptsbox.params_form]` 弹窗、定时任务表单）生效，无 `when` 的脚本不受影响。

---

## 类型系统

`type` 决定参数的数据类型，以及自动生成界面里对应的控件：

| `type` | 说明 | 生成的控件 |
| --- | --- | --- |
| `str` | 字符串 | 文本输入框；声明了 `choices` 时变为下拉选择框 |
| `int` / `float` | 数字 | 数字输入框 |
| `bool` | 布尔值 | 开关 |
| `list` | 数组 | 多行文本输入 |
| `dict` | 对象 | JSON 输入框 |

- **`choices` 仅 `str` 有效**：对其他类型声明 `choices` 会校验报错
- **`secret = true`**：敏感参数，界面用密码输入框显示
- **`default` 按 `type` 强转**：例如 `type = "int"` 时，`default = 80` 会被强制转为整数

---

## 运行期取值

- **普通触发时**，`params` 取 TOML 里声明的 `default` 值
- **被联动调用时**，`params` 由调用方覆盖，未传的用默认值
- **只有 TOML 里声明过的参数名会出现在 `params` 段**，脚本按声明的 `name` 读取

脚本端读取示例：

```python
import json, sys

payload = json.load(open(sys.argv[1], encoding='utf-8'))
lang = payload["params"].get("language", "auto")     # 用 .get 兜底
quality = payload["params"].get("quality", 80)
```

---

## 各场景的传入方式

| 场景 | params 从哪来 | 谁覆盖 |
| --- | --- | --- |
| 定时任务 | 用户在该任务的表单里填一次，存为 `task_params` | 用户 |
| 自动生成界面 | 用户每次运行前在控件里填，盒子回填上次的值 | 用户 |
| 脚本联动 `/api/link` | 调用方在请求里传 `params` | 调用方脚本 |
| HTTP API `/api/execute` | 外部程序在请求里传 `params` | 外部程序 |

定时任务的完整机制见 [定时任务](./scheduled-task)，联动的覆盖方式见 [脚本联动](./script-linking)。

---

## 多文件路径技巧

`inputs` 最多只能声明 1 条（主数据）。需要传多个文件或多个参数时，用 `str` 类型的 `params` 声明路径参数即可：

```toml
[[bmscriptsbox.params]]
name = "extra_paths"
type = "str"
description = "额外的文件路径，用分号分隔"
```

---

## 常见问题

**Q：普通触发时，为什么我没收到 params？**
A：普通触发（右键 / 快捷键 / 超级复制）盒子只传 `inputs`，不传 `params`。需要用户配置运行选项时，声明 `[bmscriptsbox.params_form]` 让盒子弹出运行界面。

**Q：`choices` 能用于 `int` 类型吗？**
A：不能。`choices` 仅对 `str` 类型有效，对其他类型声明会在安装时校验报错。

**Q：`required = true` 有什么作用？**
A：定时任务表单会在该字段后标 `*` 提示必填；联动调用时缺省会报错。

---

## 相关文档

- params 在配置文件中的完整上下文 → [声明式接入](./declarative-access)
- 参数文件的三段契约 → [参数注入](./parameter-passing)
- 自动生成运行界面 → [自动生成运行界面](./auto-generated-ui)
- 定时任务配参 → [定时任务](./scheduled-task)
- 联动传参 → [脚本联动](./script-linking)