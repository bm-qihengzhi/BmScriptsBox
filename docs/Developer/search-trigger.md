---
title: 搜索触发
description: 不忙盒子搜索触发——用 bmscriptsbox.triggers.search 让搜索框内容匹配脚本输入并推荐脚本。
status: 稳定
docType: reference
audience: 脚本开发者
docVersion: 0.3.0
---

# 搜索触发

> **让搜索框里的一段内容（URL、路径、文本、磁力链接）成为脚本输入。用户搜索时，盒子根据规则推荐能处理这段内容的脚本。**

搜索触发是 <code>[bmscriptsbox.triggers.search]</code>，和右键菜单、快捷键、超级复制并列，属于独立触发配置。

它只负责「推荐脚本」，不会自动执行。用户点击或按 Enter 选择后，才把搜索内容作为 <code>data</code> 传给脚本。

---

## 什么时候用

适合：

- 翻译脚本：用户直接粘贴一段文本；
- 视频/文件下载：用户粘贴 URL、磁力链接或 <code>.torrent</code> 路径；
- 格式转换、文本解析：用户输入 JSON、XML、Base64 等内容。

不适合：

- 只靠脚本名触发的普通脚本（用右键、快捷键或直接启动即可）；
- 需要用户先配置大量参数、再决定是否运行的流程（用参数表单或定时任务）。

---

## 快速模板

先复制下面四种之一，改域名 / 格式 / 后缀即可。90% 的脚本不需要看完整字段表。

### URL

~~~toml
[[bmscriptsbox.inputs]]
name = "url"
type = "str"

[bmscriptsbox.triggers.search]
match = [
  { kind = "url", domain = "bilibili.com", path = "/video/*" },
]
~~~

### 文本格式

~~~toml
[[bmscriptsbox.inputs]]
name = "text"
type = "str"

[bmscriptsbox.triggers.search]
match = [
  { kind = "text", format = "json" },
]
~~~

### 本地文件后缀

~~~toml
[[bmscriptsbox.inputs]]
name = "source"
type = "list"

[bmscriptsbox.triggers.search]
match = [
  { kind = "path", ext = ".torrent" },
]
~~~

### 磁力链接

~~~toml
[[bmscriptsbox.inputs]]
name = "source"
type = "str"

[bmscriptsbox.triggers.search]
match = [
  { kind = "magnet" },
]
~~~

> <code>enabled</code> 默认 <code>true</code>，模板里省略了。保存后重新安装/更新脚本即可生效。

---

## 声明结构

~~~toml
[[bmscriptsbox.inputs]]
name = "target"
label = "待处理内容"
type = "str"

[bmscriptsbox.triggers.search]
enabled = true
match = [
  { kind = "url", domain = "bilibili.com", path = "/video/*" },
]
~~~

> <code>match = [...]</code> 与 <code>[[bmscriptsbox.triggers.search.match]]</code> 等价；规则多或含 <code>all</code> / <code>none</code> 时用后者更清楚。

关系：

- <code>inputs</code> 声明脚本接收什么数据；
- <code>triggers.search</code> 声明搜索内容在什么条件下推荐这个脚本。

当前 <code>inputs</code> 最多只能声明 1 条，搜索内容固定写入该输入。

<code>data[name]</code> 始终是数组；<code>inputs.type</code> 只作为 UI / 选择器提示，不决定 JSON 形状。

---

## 字段参考

### bmscriptsbox.triggers.search

| 字段 | 类型 | 必填 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| <code>enabled</code> | bool | 否 | <code>true</code> | 是否参与搜索推荐 |
| <code>match</code> | array | 否 | <code>[]</code> | 匹配规则；<code>kind</code> 支持 url / path / text / magnet |

### match 通用字段

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| <code>kind</code> | string | 必填，url / path / text / magnet |
| <code>weight</code> | int | 排序权重，越大越靠前 |
| <code>ignore_case</code> | bool | 是否忽略大小写，默认 false；域名始终忽略大小写 |

> <code>all</code> / <code>none</code> 属于高级用法，见下方「高级匹配」。

### 各 kind 可用字段

| kind | 字段 |
| --- | --- |
| url | scheme / domain / host / path / query_contains / ext |
| path | path / name / ext / exists / is_file / is_folder |
| text | format / prefix / suffix / contains / equals / min_length / max_length / regex |
| magnet | 无额外字段 |

> **domain vs host**：<code>domain</code> 匹配域名及其子域（<code>bilibili.com</code> 包含 <code>m.bilibili.com</code>）；<code>host</code> 精确匹配主机名。拿不准就用 <code>domain</code>。
>
> 字段含义见 [声明式接入](./declarative-access) 和 [参数注入](./parameter-passing)。

---

## 高级匹配 all / none

普通字段不够时使用；90% 的场景不需要。

~~~toml
[[bmscriptsbox.triggers.search.match]]
kind = "url"
all = [
  { field = "url.host", op = "host_suffix", value = "bilibili.com" },
  { field = "url.path", op = "prefix", value = "/video/" },
]
none = [
  { field = "url.query", op = "contains", value = "p=0" },
]
~~~

- <code>all</code>：组内条件全部满足；
- <code>none</code>：组内条件全部不满足；
- 不能和 <code>domain</code> / <code>path</code> / <code>format</code> 等普通字段混用；
- 常用字段：<code>url.host</code> / <code>url.path</code> / <code>path.full</code> / <code>formats</code> / <code>text</code>；
- 常用操作符：<code>eq</code> / <code>in</code> / <code>prefix</code> / <code>suffix</code> / <code>contains</code> / <code>glob</code> / <code>host_suffix</code> / <code>regex</code>。

---

## 匹配规则

### AND 与 OR

- 单条 <code>match</code> 内部：多个字段是 **AND**；
- 多条 <code>match</code> 之间：是 **OR**。

例如：

~~~toml
[[bmscriptsbox.triggers.search.match]]
kind = "url"
domain = "bilibili.com"
path = "/video/*"
~~~

表示：URL 的域名是 bilibili.com **并且** 路径匹配 <code>/video/*</code>。

~~~toml
[[bmscriptsbox.triggers.search.match]]
kind = "url"
host = "b23.tv"

[[bmscriptsbox.triggers.search.match]]
kind = "url"
domain = "bilibili.com"
~~~

表示：命中 <code>b23.tv</code> **或者** <code>bilibili.com</code> 任意一条即可。

### 输入分类

搜索内容会先归入一种类型，优先级：

~~~text
magnet > url > path > text
~~~

所以一个字符串如果既是合法 URL 又像文件路径，会优先按 URL 处理。

### 高置信与低置信

| 置信度 | 条件 |
| --- | --- |
| 高 | `magnet`；url 写了 `domain` / `host` / `path` / `ext`；path 写了 `path` / `name` / `ext` / `exists` / `is_file` / `is_folder`；text 写了 `format` / `prefix` / `suffix` / `contains` / `equals` / `regex` |
| 低 | 只写 `kind`；只写 `min_length` / `max_length`；没有任何进一步约束 |

> 低置信只在普通搜索结果为空时展示。想让规则稳定出现，补一个高置信条件，例如 `domain` / `ext` / `format`。

### 结果位置

- 普通搜索结果优先；
- 高置信输入匹配追加在普通结果之后；
- 低置信输入匹配仅在普通结果为空时出现；
- 市场推荐是独立能力，不改变搜索触发的匹配规则。

### 去重

同一个脚本命中多条规则时只展示一次，取最高分。

---

## 测试匹配

仓库自带调试脚本：

~~~bash
uv run python tools/input_match_debug.py "https://www.bilibili.com/video/BVxxx"
uv run python tools/input_match_debug.py "一段文本" --high-only
~~~

输出包括输入分类、URL / 路径解析结果、命中脚本、分数、高 / 低置信和匹配原因。

> 调试脚本读取本地已安装脚本库；修改 TOML 后需要重新安装 / 更新脚本。

---

## 传参

用户选择搜索推荐后，搜索内容写入目标输入的 <code>data</code>：

~~~json
{
  "data": {
    "target": ["用户输入的内容"]
  }
}
~~~

<code>data[name]</code> 始终是数组，搜索内容作为单元素数组传入。

脚本读取：

~~~python
import json
import sys
from pathlib import Path

payload = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
text = payload["data"]["target"][0]

print(text)
~~~

> 搜索触发的数据仍在 <code>data</code> 段，不在 <code>params</code>。参数表单、右键、快捷键、超级复制共用同一个 <code>data</code> 契约。

---

## 示例

### 1. B 站视频链接

~~~toml
[[bmscriptsbox.inputs]]
name = "url"
label = "视频链接"
type = "str"

[bmscriptsbox.triggers.search]

[[bmscriptsbox.triggers.search.match]]
kind = "url"
domain = "bilibili.com"
path = "/video/*"

[[bmscriptsbox.triggers.search.match]]
kind = "url"
host = "b23.tv"
~~~

### 2. 通用文本翻译

~~~toml
[[bmscriptsbox.inputs]]
name = "text"
label = "待翻译文本"
type = "str"

[bmscriptsbox.triggers.search]

[[bmscriptsbox.triggers.search.match]]
kind = "text"
min_length = 2
weight = 10
~~~

### 3. 磁力链接 / 种子

~~~toml
[[bmscriptsbox.inputs]]
name = "source"
label = "磁力链接或种子"
type = "str"

[bmscriptsbox.triggers.search]

[[bmscriptsbox.triggers.search.match]]
kind = "magnet"

[[bmscriptsbox.triggers.search.match]]
kind = "path"
ext = ".torrent"

[[bmscriptsbox.triggers.search.match]]
kind = "text"
format = "btih"
~~~

### 4. JSON 文本

~~~toml
[[bmscriptsbox.inputs]]
name = "text"
label = "JSON 文本"
type = "str"

[bmscriptsbox.triggers.search]

[[bmscriptsbox.triggers.search.match]]
kind = "text"
format = "json"
~~~

---

## 校验规则

安装时会校验：

- <code>triggers.search</code> 必须至少有一个 <code>inputs</code>；
- <code>inputs.match</code> 已移除，出现即报错，需要改成 <code>[[bmscriptsbox.triggers.search.match]]</code>；
- <code>match.kind</code> 只能是 <code>url</code> / <code>path</code> / <code>text</code> / <code>magnet</code>；
- <code>all</code> / <code>none</code> 不能和普通字段混用；
- 正则必须可编译，长度受限。

---

## 常见错误

| 现象 | 原因 | 修正 |
| --- | --- | --- |
| 子域不匹配 | 用了 <code>host</code> | 改用 <code>domain</code> |
| <code>ext</code> 不生效 | 写成 <code>torrent</code> | 写成 <code>.torrent</code> |
| 文本规则不出现 | 只写了 <code>kind = "text"</code>，属于低置信 | 补 <code>format</code> / <code>prefix</code> / <code>regex</code> |
| 安装报错 | 还在用 <code>inputs.match</code> | 改成 <code>[[bmscriptsbox.triggers.search.match]]</code> |
| 安装报错 | <code>all</code> / <code>none</code> 和普通字段混用 | 二选一 |

---

## 与其他触发的关系

- 搜索触发只负责「推荐」，不会自动运行脚本；
- 右键、快捷键、超级复制、定时任务仍按各自配置工作；
- 同一个脚本可以同时声明多个触发方式；
- 搜索推荐不改变脚本的 <code>terminal</code> / <code>concurrency</code> 行为。

---

## 相关文档

- TOML 总览 → [声明式接入](./declarative-access)
- JSON 参数结构 → [参数注入](./parameter-passing)
- 输入输出契约 → [输入输出契约](./io-contract)
- 终端模式 → [终端模式详解](./terminal-mode)
- 单实例与并发 → [单实例与并发](./single-instance)